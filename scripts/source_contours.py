"""Read-only, RGB-preserving contour evidence for cached scanner results.

This diagnostic measures image support, not semantic object identity. It never
changes detections, JMaps, fixtures or the application. Compact-frame mappings
are deliberately rejected until their coordinate transform is qualified.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from math import hypot
from pathlib import Path
from statistics import median
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage, load_png
from jtool_scanner.spike_shape import VERTICES


@dataclass(frozen=True)
class EdgeEvidence:
    support: int
    unknown: bool
    independent_source_positions: tuple[tuple[int, int], ...]


class SourceContours:
    """Cache coherent RGB edge support after local-gradient subtraction."""

    def __init__(self, image: RGBImage, room: Box,
                 native_size: tuple[int, int] = (800, 608)):
        if min(room.width, room.height, *native_size) <= 0:
            raise ValueError("Room and native dimensions must be positive")
        self.image, self.room, self.native_size = image, room, native_size
        self._edges: dict[tuple, EdgeEvidence] = {}

    def edge(self, first: tuple[float, float], second: tuple[float, float]) -> EdgeEvidence:
        key = first, second
        if key in self._edges:
            return self._edges[key]
        tx, ty = second[0] - first[0], second[1] - first[1]
        length = hypot(tx, ty)
        if not length:
            raise ValueError("An edge needs two distinct endpoints")
        nx, ny = -ty / length, tx / length
        width, height = self.native_size
        rows = []
        unknown = False
        for i in range(12):
            fraction = .15 + .7 * i / 11
            px, py = first[0] + fraction * tx, first[1] + fraction * ty
            native = [(px + off * nx, py + off * ny) for off in range(-4, 5)]
            if any(not (0 <= x < width and 0 <= y < height) for x, y in native):
                unknown = True
                break
            points = [(int(self.room.x + x * self.room.width / width),
                       int(self.room.y + y * self.room.height / height))
                      for x, y in native]
            if any(not (0 <= x < self.image.width and 0 <= y < self.image.height)
                   for x, y in points):
                unknown = True
                break
            values = [self.image.pixel(*point) for point in points]
            derivatives = []
            for j in range(8):
                spacing = hypot(points[j + 1][0] - points[j][0],
                                points[j + 1][1] - points[j][1])
                derivatives.append(tuple((values[j + 1][c] - values[j][c]) / spacing
                                         for c in range(3)) if spacing else (0., 0., 0.))
            gradient = tuple(median(derivatives[j][c] for j in (0, 1, 6, 7))
                             for c in range(3))
            def departure(value):
                return hypot(*(value[c] - gradient[c] for c in range(3)))
            reference = max(departure(derivatives[j]) for j in (0, 1, 6, 7))
            phases = {j - 3.5 for j in (2, 3, 4, 5)
                      if departure(derivatives[j]) > reference}
            rows.append((phases, points[4]))
        supported: set[tuple[int, int]] = set()
        if not unknown:
            for low in (-1.5, -.5, .5):
                candidate = {point for phases, point in rows
                             if any(low <= phase <= low + 1 for phase in phases)}
                if len(candidate) > len(supported):
                    supported = candidate
        evidence = EdgeEvidence(len(supported), unknown, tuple(sorted(supported)))
        self._edges[key] = evidence
        return evidence

    def triangle(self, type_id: int, x: int, y: int) -> list[EdgeEvidence]:
        if not 3 <= type_id <= 10:
            raise ValueError("Triangle type must be a full or mini spike ID (3–10)")
        size = 16 if type_id > 6 else 32
        direction = type_id - 4 if type_id > 6 else type_id
        points = [(x + a * size / 32, y + b * size / 32)
                  for a, b in VERTICES[direction]]
        return [self.edge(points[i], points[(i + 1) % 3]) for i in range(3)]

    def rectangle(self, x: int, y: int, size: int = 32) -> list[EdgeEvidence]:
        if size <= 0:
            raise ValueError("Rectangle size must be positive")
        points = [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]
        return [self.edge(points[i], points[(i + 1) % 4]) for i in range(4)]


def probe(source: Path, result_path: Path, queries: list[tuple[int, int, int]]) -> dict:
    result_bytes = result_path.read_bytes()
    result = json.loads(result_bytes)
    source_bytes = source.read_bytes()
    source_digest = hashlib.sha256(source_bytes).hexdigest()
    if source_digest != result["inputs"]["source_sha256"]:
        raise ValueError("Source image does not match the cached result's SHA-256")
    if result["source_grid"] != [25, 19]:
        raise ValueError("Compact/nonstandard source-grid mapping is not qualified by this probe")
    field = SourceContours(load_png(source), Box(**result["room_box"]))
    rows = []
    for type_id, x, y in queries:
        faces = field.triangle(type_id, x, y) if 3 <= type_id <= 10 else (
            field.rectangle(x, y, 16 if type_id == 2 else 32)
            if type_id in (1, 2) else None)
        if faces is None:
            raise ValueError("Queries support terrain/spike IDs 1–10 only")
        rows.append(dict(key=[type_id, x, y], faces=[asdict(face) for face in faces],
                         raw_closed=all(face.support >= 9 and not face.unknown for face in faces)))
    return dict(format="source-contour-probe-v1", complete=True, read_only=True,
                source_sha256=source_digest,
                cached_result_sha256=hashlib.sha256(result_bytes).hexdigest(),
                native_size=[800, 608], rows=rows,
                not_object_identity_or_accuracy_certification=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--query", action="append", required=True,
                        help="type_id,x,y in native top-left coordinates; repeat for multiple probes")
    args = parser.parse_args(argv)
    try:
        queries = [tuple(int(v) for v in value.split(",")) for value in args.query]
        if any(len(query) != 3 for query in queries):
            raise ValueError("Each query must contain type_id,x,y")
        print(json.dumps(probe(args.source, args.result, queries), indent=2))
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
