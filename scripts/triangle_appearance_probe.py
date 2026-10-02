"""Deterministic source-size-helper diagnostics, not whole-scanner certification.

Keep geometry fixed while varying rendering. Known coordinates score results;
they are never reference inputs to the production detector. Intentionally seed
one coarse alias and omit the small triangle, exposing recovery/false-positive
behavior rather than measuring an already complete proposal list.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jtool_scanner.corpus import implementation_identity
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from jtool_scanner.spike_size import contour_size_changes

STYLES = ('uniform-filled', 'uniform-outlined', 'shaded-thin', 'shaded-thick', 'empty-gap')
SCALES = (1.0, 1.25)


def create_scene(style: str, scale: float = 1.0):
    """Return pixels, independent truth, coarse hypotheses and solid masks."""
    if style not in STYLES or scale <= 0:
        raise ValueError('unsupported style or nonpositive capture scale')
    raster = Image.new('RGB', (800, 608), (140, 165, 163))
    draw = ImageDraw.Draw(raster)
    draw.rectangle((304, 352, 415, 383), fill=(83, 49, 47))
    fulls = [(3, 320, 320), (3, 368, 320)]
    mini = (7, 352, 336)
    truth = fulls + ([] if style == 'empty-gap' else [mini])
    hypotheses = fulls + [(3, 336, 320)]
    for type_id, x, y in truth:
        size = 16 if type_id > 6 else 32
        direction = type_id - 4 if type_id > 6 else type_id
        points = [(x + a * size / 32, y + b * size / 32)
                  for a, b in VERTICES[direction]]
        draw.polygon(points, fill=(215, 217, 221))
        if style in ('shaded-thin', 'shaded-thick'):
            mask = Image.new('L', (800, 608), 0)
            ImageDraw.Draw(mask).polygon(points, fill=255)
            shaded = Image.new('RGB', (800, 608), (215, 217, 221))
            ImageDraw.Draw(shaded).rectangle((x, y, x + size / 2, y + size),
                                             fill=(132, 137, 144))
            raster.paste(shaded, (0, 0), mask)
            draw = ImageDraw.Draw(raster)
        if style != 'uniform-filled':
            draw.line(points + [points[0]], fill=(45, 48, 53),
                      width=2 if style == 'shaded-thick' else 1)
    raster = raster.resize((round(800 * scale), round(608 * scale)),
                           Image.Resampling.BILINEAR)
    return (RGBImage(raster.width, raster.height, raster.tobytes()), truth,
            hypotheses, [(304, 352, 112, 32)])


def measure_spec(style: str, scale: float):
    image, truth, hypotheses, solids = create_scene(style, scale)
    started = perf_counter()
    added, removed = contour_size_changes(
        image, Box(0, 0, image.width, image.height), hypotheses, solids)
    seconds = perf_counter() - started
    seen = Counter(hypotheses)
    seen.subtract(removed)
    seen += Counter()  # Discard zero/negative Counter entries.
    seen.update(added)
    expected = Counter(truth)
    row = dict(style=style, scale=scale, expected=len(truth),
               expected_objects=truth, coarse_hypotheses=hypotheses,
               image_rgb_sha256=sha256(image.data).hexdigest(),
               exact=sum((expected & seen).values()),
               mini_recovered=(7, 352, 336) in added if style != 'empty-gap' else None,
               added=sorted(added), removed=sorted(removed),
               misses=sorted((expected - seen).elements()),
               extras=sorted((seen - expected).elements()), helper_seconds=seconds)
    return image, row


def run_probe(out_dir: Path, specs=None):
    """Require a fresh destination; never replace previous evidence."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    specs = list(specs) if specs is not None else [
        (style, scale) for style in STYLES for scale in SCALES]
    identity = implementation_identity()
    definition = dict(implementation=identity, ordinary=False, helper_only=True,
                      probe_source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                      coordinates_used_for_evaluation_only=True,
                      fixed_geometry=True, specs=specs)
    (out_dir / 'definition.json').write_text(json.dumps(definition, indent=2), encoding='utf-8')
    rows = []
    for style, scale in specs:
        image, row = measure_spec(style, scale)
        image_path = out_dir / f'{style}-{scale}.png'
        Image.frombytes('RGB', (image.width, image.height), image.data).save(image_path)
        row['image_png_sha256'] = sha256(image_path.read_bytes()).hexdigest()
        rows.append(row)
        print(json.dumps(row), flush=True)
    assert implementation_identity() == identity, 'implementation changed during probe'
    payload = dict(definition=definition, rows=rows)
    (out_dir / 'results.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', required=True, type=Path,
                        help='new ignored directory for reproducible generated evidence')
    args = parser.parse_args()
    run_probe(args.out_dir)


if __name__ == '__main__':
    main()
