"""Original-RGB evidence for the shared phase of a short full-tile band.

This offline solver does not emit objects or infer a camera transform. A
rectangular boundary is not proof of gameplay semantics; callers must also
preserve competing objects and source-confirmed occupancy.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_contours import SourceContours


_PHASES = (-16, -8, 0, 8, 16)
_FACE_SUPPORT = 8
_RGB_JUMP = 18
_BODY_DISTANCE = 18


def horizontal_bands(full_origins):
    """Find maximal, short bands; do not search arbitrary sub-runs of walls."""
    keys = set(full_origins)
    for x, y in sorted(keys):
        if (x - 32, y) in keys:
            continue
        count = 1
        while (x + 32 * count, y) in keys and count <= 6:
            count += 1
        if 3 <= count <= 6:
            yield x, y, count


class _OriginalFrame:
    """Only the physical portion of the existing camera mapping is sampled."""

    def __init__(self, image: RGBImage, room: Box, extent: Box):
        if (not isinstance(image.data, bytes) or len(image.data) != 3 * image.width * image.height
                or min(image.width, image.height, room.width, room.height, extent.width, extent.height) <= 0
                or room.x < 0 or room.y < 0 or room.right > image.width or room.bottom > image.height
                or max(room.x, extent.x) >= min(room.right, extent.right)
                or max(room.y, extent.y) >= min(room.bottom, extent.bottom)):
            raise ValueError('Expected an original RGB capture and an overlapping world extent')
        self.room, self.extent = room, extent
        self._original = RGBImage(image.width, image.height, image.data)

    def matches_source(self, image, room):
        return room == self.room and image == self._original

    def original_snapshot(self):
        image = self._original
        return RGBImage(image.width, image.height, image.data)

    def original_position(self, x, y):
        if not (isfinite(x) and isfinite(y) and 0 <= x < 800 and 0 <= y < 608):
            return None
        p = (floor(self.extent.x + x * self.extent.width / 800),
             floor(self.extent.y + y * self.extent.height / 608))
        return p if self.room.contains(*p) else None


@dataclass(frozen=True)
class BandPhase:
    dx: int
    dy: int
    top: tuple[int, ...]
    bottom: tuple[int, ...]
    ends: tuple[int, int]
    body_distances: tuple[float, ...]


class SourceBandEvidence:
    """A scan-local, original-pixel evaluator. No resampling or palette bank."""

    def __init__(self, image: RGBImage, room: Box, *, extent: Box | None = None):
        self.frame = _OriginalFrame(image, room, extent or room)
        self._contours = SourceContours(image, self.frame.extent, source_frame=self.frame)
        self._face_cache = {}

    def _face(self, a, b):
        key = a, b
        if key not in self._face_cache:
            self._face_cache[key] = self._measure_face(a, b)
        return self._face_cache[key]

    def _measure_face(self, a, b):
        evidence = self._contours.edge(a, b)
        if evidence.unknown:
            return None
        # The compared positions are exactly two physical pixels on either
        # side of the axis, not two native pixels at fractional scales.
        ox, oy = (0, 2) if a[1] == b[1] else (2, 0)
        image, crop = self._contours.image, self.frame.room
        strong = 0
        for x, y in evidence.independent_source_positions:
            l, r = (x - ox, y - oy), (x + ox, y + oy)
            if not (crop.contains(*l) and crop.contains(*r)):
                return None
            if max(abs(a - b) for a, b in zip(image.pixel(*l), image.pixel(*r))) >= _RGB_JUMP:
                strong += 1
        return strong

    def _texture(self, x, y, count):
        image = self._contours.image
        seen, tiles = set(), []
        for left in range(x, x + 32 * count, 32):
            positions = [self.frame.original_position(left + i, y + j)
                         for j in range(4, 29, 4) for i in range(4, 29, 4)]
            unique = set(positions)
            if None in unique or len(unique) != 49 or unique & seen:
                return None
            seen.update(unique)
            tiles.append(tuple(image.pixel(*p) for p in positions))
        return tuple(sum(max(abs(a - b) for a, b in zip(p, q)) for p, q in zip(tile, other)) / 49
                     for i, tile in enumerate(tiles) for other in tiles[i + 1:])

    def phase(self, x: int, y: int, count: int) -> BandPhase | None:
        """Return a unique, fully observed nonzero phase, or abstain.

        Do not discard a competing phase solely because its source is clipped.
        A *measured* weak face can exclude that phase. A stationary match must
        compete with shifts even if its interior lacks texture agreement.
        """
        if (any(type(k) is not int for k in (x, y, count)) or not 3 <= count <= 6
                or not (0 <= x <= 800 - 32 * count and 0 <= y <= 576)):
            raise ValueError('Expected three to six full tiles at an in-room native origin')
        choices = []
        for dx in _PHASES:
            for dy in _PHASES:
                left, top = x + dx, y + dy
                right, bottom = left + count * 32, top + 32
                if not (0 <= left < right <= 800 and 0 <= top < bottom <= 608):
                    continue  # an invalid game-space footprint, not source absence
                ends = tuple(self._face((p, top), (p, bottom)) for p in (left, right))
                if any(e is not None and e < _FACE_SUPPORT for e in ends):
                    continue
                tops, bottoms, rejected = [], [], False
                for p in range(left, right, 32):
                    tops.append(self._face((p, top), (p + 32, top)))
                    bottoms.append(self._face((p, bottom), (p + 32, bottom)))
                    if any(e is not None and e < _FACE_SUPPORT for e in (tops[-1], bottoms[-1])):
                        rejected = True
                        break
                if not rejected:
                    choices.append((dx, dy, tuple(tops), tuple(bottoms), ends))
                    if len(choices) > 1:
                        return None
        if not choices:
            return None
        dx, dy, tops, bottoms, ends = choices[0]
        if (dx == dy == 0) or None in tops + bottoms + ends:
            return None
        distances = self._texture(x + dx, y + dy, count)
        if distances is None or max(distances) > _BODY_DISTANCE:
            return None
        return BandPhase(dx, dy, tops, bottoms, ends, distances)
