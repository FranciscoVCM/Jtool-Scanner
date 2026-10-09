"""Read-only, scan-local RGB appearance learned from source-verified triangles.

This is an experimental evidence tool, not a scanner binding or an object
emitter. Existing detections locate hypotheses; their directions are not truth.
No reference maps, stored tilesets, palettes or room identities enter learning.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from math import floor, hypot, sqrt
from pathlib import Path
import sys

from PIL import Image

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage, load_png
from jtool_scanner.spike_shape import VERTICES
from scripts.source_contours import SourceContours

NATIVE_WIDTH, NATIVE_HEIGHT = 800, 608


def _dimensions(type_id: int) -> tuple[int, int]:
    if not 3 <= type_id <= 10:
        raise ValueError("A source glyph needs a full/mini spike ID (3–10)")
    return (16, type_id - 4) if type_id > 6 else (32, type_id)


def _contains(poly, x, y):
    signs = [(bx - ax) * (y - ay) - (by - ay) * (x - ax)
             for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1])]
    return min(signs) >= 0 or max(signs) <= 0


def _bounds(values):
    differences = [(r - g, r - b, g - b) for r, g, b in values]
    return (tuple((min(v[c] for v in values), max(v[c] for v in values)) for c in range(3)),
            tuple((min(v[c] for v in differences), max(v[c] for v in differences)) for c in range(3)))


def _fits(rgb, model):
    r, g, b = rgb
    return all(lo <= v <= hi for v, (lo, hi) in zip(rgb, model[0])) and all(
        lo <= v <= hi for v, (lo, hi) in zip((r - g, r - b, g - b), model[1]))


class _RawContours:
    """Share the existing public RGB contour kernel, without duplicating it."""

    def __init__(self, image, room, contour_field=None):
        if contour_field is not None and (
            contour_field.image is not image or contour_field.room != room
            or contour_field.native_size != (800, 608)
        ):
            raise ValueError("Shared contours must match the original image/room/native frame")
        self.field = contour_field if contour_field is not None else SourceContours(image, room)

    def edge(self, first, second):
        evidence = self.field.edge(first, second)
        return evidence.support, evidence.unknown

    def box_faces(self, x, y):
        return [face.support for face in self.field.rectangle(x, y, 16)]


class SourceGlyphEvidence:
    """Independent raw geometry, competing rectangle and RGB body/corner proof."""

    def __init__(self, image: RGBImage, room: Box, *, contour_field=None):
        self.image, self.room = image, room
        self.raw = _RawContours(image, room, contour_field)
        self.cache = {}

    def sample(self, cx, cy, size=2):
        values = []
        for dy in range(size):
            for dx in range(size):
                x, y = cx - size / 2 + dx + .5, cy - size / 2 + dy + .5
                if not (0 <= x < 800 and 0 <= y < 608):
                    return None
                sx = int(self.room.x + x * self.room.width / 800)
                sy = int(self.room.y + y * self.room.height / 608)
                if not (0 <= sx < self.image.width and 0 <= sy < self.image.height):
                    return None
                values.append(self.image.pixel(sx, sy))
        return values

    def owner(self, type_id, x, y):
        size, direction = _dimensions(type_id)
        key = type_id, x, y
        if key in self.cache:
            return self.cache[key]
        self.cache[key] = None
        poly = [(x + a * size / 32, y + b * size / 32) for a, b in VERTICES[direction]]
        triangle = [self.raw.edge(poly[i], poly[(i + 1) % 3]) for i in range(3)]
        if any(count < 9 or unknown for count, unknown in triangle):
            return None
        corners = [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]
        rectangle = [self.raw.edge(corners[i], corners[(i + 1) % 4]) for i in range(4)]
        if all(count >= 9 and not unknown for count, unknown in rectangle):
            return None
        margin = size / 8
        points = [(x + margin, y + margin), (x + size - margin, y + margin),
                  (x + size - margin, y + size - margin), (x + margin, y + size - margin)]
        exterior = [p for p in points if not _contains(poly, *p)]
        if len(exterior) != 2:
            return None
        patches = [self.sample(*p, size=2 if size == 16 else 4) for p in exterior]
        if any(p is None for p in patches):
            return None
        models = [_bounds(p) for p in patches]
        body = []
        for weights in ((.25, .5, .25), (.25, .25, .5), (.5, .25, .25), (1 / 3, 1 / 3, 1 / 3)):
            cx = sum(w * p[0] for w, p in zip(weights, poly))
            cy = sum(w * p[1] for w, p in zip(weights, poly))
            values = self.sample(cx, cy)
            if values is None:
                return None
            body.append(not any(all(_fits(rgb, m) for rgb in values) for m in models))
        if not all(body):
            return None
        row = dict(key=[type_id, x, y], poly=poly, triangle_faces=triangle,
                   competing_rectangle_faces=rectangle, source_exterior_corners=exterior,
                   source_body_separate_from_both_corners=body)
        self.cache[key] = row
        return row


class FilledSourceEvidence:
    """Alternative source-filled silhouette, preserving source-pixel independence."""

    def __init__(self, field: SourceGlyphEvidence):
        self.field, self.cache = field, {}

    def evidence(self, type_id, x, y):
        size, direction = _dimensions(type_id)
        key = type_id, x, y
        if key in self.cache:
            return self.cache[key]
        tip, *ends = poly = [(x + a * size / 32, y + b * size / 32) for a, b in VERTICES[direction]]
        cx, cy = sum(a for a, _ in poly) / 3, sum(b for _, b in poly) / 3
        margin = size / 8
        corners = [(x + margin, y + margin), (x + size - margin, y + margin),
                   (x + size - margin, y + size - margin), (x + margin, y + size - margin)]
        exterior = [p for p in corners if not _contains(poly, *p)]
        corner_values = [self.field.sample(*p, size=2 if size == 16 else 4) for p in exterior]
        bodies = []
        for weights in ((.25, .5, .25), (.25, .25, .5), (.5, .25, .25), (1 / 3, 1 / 3, 1 / 3)):
            bx = sum(w * p[0] for w, p in zip(weights, poly))
            by = sum(w * p[1] for w, p in zip(weights, poly))
            bodies.append(self.field.sample(bx, by))
        if any(p is None for p in corner_values + bodies):
            return dict(passed=False, unknown=True, reason="clipped source samples")
        means = [tuple(sum(v[c] for v in p) / len(p) for c in range(3)) for p in corner_values]
        body = tuple(sum(v[c] for p in bodies for v in p) / sum(map(len, bodies)) for c in range(3))
        separation = min(hypot(*(a - b for a, b in zip(body, m))) for m in means)
        disagreement = hypot(*(a - b for a, b in zip(*means)))
        if separation <= disagreement:
            answer = dict(passed=False, unknown=False, reason="competing exterior source materials",
                          body_corner_separation=separation, corner_disagreement=disagreement)
            self.cache[key] = answer
            return answer
        background = tuple((a + b) / 2 for a, b in zip(*means))
        vector = tuple(a - b for a, b in zip(body, background))
        energy = sum(v * v for v in vector)
        if not energy:
            return dict(passed=False, unknown=False, reason="no source material separation")
        def foreground(values):
            mean = tuple(sum(v[c] for v in values) / len(values) for c in range(3))
            return sum((v - b) * d for v, b, d in zip(mean, background, vector)) > .5 * energy
        slopes = []
        for end in ends:
            tx, ty = end[0] - tip[0], end[1] - tip[1]
            length = hypot(tx, ty)
            nx, ny = -ty / length, tx / length
            inward = 1 if (cx - tip[0]) * nx + (cy - tip[1]) * ny > 0 else -1
            support, unknown = set(), False
            for i in range(12):
                margin = max(.15, 4 / size)
                q = margin + (1 - 2 * margin) * i / 11
                px, py = tip[0] + q * tx, tip[1] + q * ty
                inner = self.field.sample(px + inward * 4 * nx, py + inward * 4 * ny)
                outer = self.field.sample(px - inward * 4 * nx, py - inward * 4 * ny)
                if inner is None or outer is None:
                    unknown = True
                    continue
                if foreground(inner) and not foreground(outer):
                    support.add((int(self.field.room.x + px * self.field.room.width / 800),
                                 int(self.field.room.y + py * self.field.room.height / 608)))
            slopes.append(dict(support=len(support), unknown=unknown, source_positions=sorted(support)))
        base = self.field.raw.edge(ends[0], ends[1])
        corners = [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]
        rectangle = [self.field.raw.edge(corners[i], corners[(i + 1) % 4])[0] for i in range(4)]
        answer = dict(passed=all(r["support"] >= 9 and not r["unknown"] for r in slopes)
                      and base[0] >= 9 and not base[1] and min(rectangle) < 9,
                      unknown=False, slopes=slopes, raw_base=base, competing_rectangle_faces=rectangle,
                      body_corner_separation=separation, corner_disagreement=disagreement)
        self.cache[key] = answer
        return answer


class SourceGlyphLibrary:
    """Transient native-size prototypes; outputs are evidence, never map edits."""

    def __init__(self, image: RGBImage, room: Box, spikes, *,
                 contour_field=None, pixel_cache_limit=0):
        if room.width <= 0 or room.height <= 0:
            raise ValueError("Room dimensions must be positive")
        if room.x < 0 or room.y < 0 or room.x + room.width > image.width or room.y + room.height > image.height:
            raise ValueError("The room must lie inside the original source image")
        if not isinstance(pixel_cache_limit, int) or isinstance(pixel_cache_limit, bool) or pixel_cache_limit < 0:
            raise ValueError("Pixel cache limit must be a nonnegative integer")
        self._pixel_cache_limit = pixel_cache_limit
        self._pixel_results = OrderedDict()
        self.pixel_cache_hits = self.pixel_cache_misses = self.pixel_cache_peak = 0
        self.raw = SourceGlyphEvidence(image, room, contour_field=contour_field)
        self.filled = FilledSourceEvidence(self.raw)
        raster = Image.frombytes("RGB", (image.width, image.height), image.data)
        self.pixels = raster.crop((room.x, room.y, room.x + room.width, room.y + room.height)).resize(
            (800, 608), Image.Resampling.BILINEAR).tobytes()
        self.signatures, self.anchors = {}, []
        self._support_results = {}
        hypotheses = set()
        for type_id, x, y in spikes:
            size, _ = _dimensions(type_id)
            for direction in (3, 4, 5, 6):
                hypotheses.add((direction + (4 if size == 16 else 0), x, y))
        for key in sorted(hypotheses):
            strict, filled = self.raw.owner(*key), self.filled.evidence(*key)
            if strict is None and not filled["passed"]:
                continue
            self.anchors.append(dict(key=key, size=_dimensions(key[0])[0],
                                     signature=self.signature(*key),
                                     independent_source_proof="raw" if strict else "filled"))
        self.pitch = 800 / room.width, 608 / room.height
        self.models, self.pair_scores = [], {}
        seen = set()
        def matches(a, b):
            if (a, b) not in self.pair_scores:
                score = sum(u * v for u, v in zip(self.anchors[a]["signature"], self.anchors[b]["signature"]))
                self.pair_scores[a, b] = self.pair_scores[b, a] = score
            return self.pair_scores[a, b] >= .9
        for seed, anchor in enumerate(self.anchors):
            eligible = [i for i, other in enumerate(self.anchors)
                        if other["size"] == anchor["size"] and matches(seed, i)]
            group = []
            for i in sorted(eligible, key=lambda i: (-self.pair_scores[seed, i], self.anchors[i]["key"])):
                if all(matches(i, j) for j in group):
                    group.append(i)
            regions = {(self.anchors[i]["key"][1] // 32, self.anchors[i]["key"][2] // 32) for i in group}
            identity = tuple(sorted(group))
            if len(regions) < 3 or identity in seen:
                continue
            seen.add(identity)
            prototype = tuple(sum(self.anchors[i]["signature"][c] for i in group) / len(group)
                              for c in range(len(anchor["signature"])))
            length = sqrt(sum(v * v for v in prototype))
            self.models.append(dict(native_size=anchor["size"],
                                    signature=tuple(v / max(1e-12, length) for v in prototype),
                                    original_source_witnesses=[self.anchors[i]["key"] for i in group],
                                    independent_regions=len(regions), all_source_pairs_mutually_correlated=True))

    def pixel(self, x, y):
        if not self._pixel_cache_limit:
            return self._measure_pixel(x, y)
        key = x, y
        if key in self._pixel_results:
            self.pixel_cache_hits += 1
            self._pixel_results.move_to_end(key)
            return self._pixel_results[key]
        self.pixel_cache_misses += 1
        answer = self._measure_pixel(x, y)
        self._pixel_results[key] = answer
        if len(self._pixel_results) > self._pixel_cache_limit:
            self._pixel_results.popitem(last=False)
        self.pixel_cache_peak = max(self.pixel_cache_peak, len(self._pixel_results))
        return answer

    def _measure_pixel(self, x, y):
        u, v = x - .5, y - .5
        ix, iy = floor(u), floor(v)
        dx, dy = u - ix, v - iy
        values = []
        for ox, oy, weight in ((0, 0, (1-dx)*(1-dy)), (1, 0, dx*(1-dy)),
                              (0, 1, (1-dx)*dy), (1, 1, dx*dy)):
            px, py = max(0, min(799, ix + ox)), max(0, min(607, iy + oy))
            offset = (py * 800 + px) * 3
            values.append((weight, self.pixels[offset:offset + 3]))
        return tuple(sum(weight * rgb[c] for weight, rgb in values) for c in range(3))

    def signature(self, type_id, x, y):
        size, direction = _dimensions(type_id)
        key = type_id, x, y
        if key in self.signatures:
            return self.signatures[key]
        values = []
        for j in range(16):
            for i in range(16):
                u, v = (i + .5) * size / 16, (j + .5) * size / 16
                a, b = ((u, v) if direction == 3 else (size-v, u) if direction == 4
                        else (v, size-u) if direction == 5 else (size-u, size-v))
                values.append((i - 7.5, j - 7.5, self.pixel(x + a, y + b)))
        mean = tuple(sum(rgb[c] for _, _, rgb in values) / 256 for c in range(3))
        dx, dy = sum(u*u for u, _, _ in values), sum(v*v for _, v, _ in values)
        sx = tuple(sum(u*rgb[c] for u, _, rgb in values) / dx for c in range(3))
        sy = tuple(sum(v*rgb[c] for _, v, rgb in values) / dy for c in range(3))
        residual = tuple(rgb[c] - mean[c] - sx[c]*u - sy[c]*v
                         for u, v, rgb in values for c in range(3))
        length = sqrt(sum(z*z for z in residual))
        answer = tuple(z / max(1e-12, length) for z in residual)
        self.signatures[key] = answer
        return answer

    def support(self, type_id, x, y):
        """Memoize source-local queries without sharing mutable proof results.

        Models are fixed at construction; queries never add training examples.
        The cache belongs to this image/room instance, not a global tileset store.
        """
        _dimensions(type_id)
        key = type_id, x, y
        if key not in self._support_results:
            self._support_results[key] = self._measure_support(type_id, x, y)
        return deepcopy(self._support_results[key])

    def _measure_support(self, type_id, x, y):
        size, _ = _dimensions(type_id)
        models = [m for m in self.models if m["native_size"] == size]
        best = dict(passed=False, model=None, correlation=None, query_phase=None,
                    native_size=size, original_source_witnesses_only=True)
        for dx in (0, -self.pitch[0], self.pitch[0]):
            for dy in (0, -self.pitch[1], self.pitch[1]):
                if not (0 <= x+dx <= 800-size and 0 <= y+dy <= 608-size):
                    continue
                query = self.signature(type_id, x+dx, y+dy)
                for model in models:
                    score = sum(a*b for a, b in zip(query, model["signature"]))
                    if best["correlation"] is None or score > best["correlation"]:
                        best = dict(passed=score >= .9, model={k: v for k, v in model.items() if k != "signature"},
                                    correlation=score, query_phase=[dx, dy], native_size=size,
                                    bounded_by_one_original_source_pixel=True, original_source_witnesses_only=True)
        return best


def probe(source: Path, result_path: Path, queries) -> dict:
    """Use cached poses only as locators; verify source and coordinate identity."""
    source_bytes, result_bytes = source.read_bytes(), result_path.read_bytes()
    result = json.loads(result_bytes)
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != result["inputs"]["source_sha256"]:
        raise ValueError("Source image does not match the cached result's SHA-256")
    if result["source_grid"] != [25, 19]:
        raise ValueError("Compact/nonstandard source-grid mapping is not qualified")
    spikes = [(d["type_id"], d["x"], d["y"]) for d in result["detections"] if 3 <= d["type_id"] <= 10]
    library = SourceGlyphLibrary(load_png(source), Box(**result["room_box"]), spikes)
    rows = [dict(key=list(key), evidence=library.support(*key)) for key in queries]
    return dict(format="source-glyph-prototype-probe-v1", complete=True, read_only=True,
                source_sha256=digest, cached_result_sha256=hashlib.sha256(result_bytes).hexdigest(),
                native_size=[800, 608], rows=rows,
                source_anchors=[{k: v for k, v in a.items() if k != "signature"} for a in library.anchors],
                source_models=[{k: v for k, v in m.items() if k != "signature"} for m in library.models],
                not_object_emission_map_edit_or_accuracy_certification=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--query", action="append", required=True, help="type_id,x,y in native top-left coordinates")
    args = parser.parse_args(argv)
    try:
        queries = [tuple(int(v) for v in value.split(",")) for value in args.query]
        if any(len(q) != 3 for q in queries):
            raise ValueError("Each query must contain type_id,x,y")
        print(json.dumps(probe(args.source, args.result, queries), indent=2))
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
