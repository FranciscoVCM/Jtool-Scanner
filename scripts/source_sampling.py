"""Frozen source/capture coordinates with explicit original-pixel coverage.

A canonical raster may contain repeated edge pixels. Those pixels are useful
for display, but are not independent source observations. This read-only view
keeps the physical source and its coverage separate from the filtered raster.
It neither infers a transform nor changes scanner detections.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, isfinite

from PIL import Image

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage


NATIVE_WIDTH, NATIVE_HEIGHT = 800, 608


def _frozen_image(image):
    if (image.width <= 0 or image.height <= 0 or not isinstance(image.data, bytes)
            or len(image.data) != image.width * image.height * 3):
        raise ValueError('Source sampling requires complete immutable RGB bytes')
    return RGBImage(image.width, image.height, image.data)


def _taps(value):
    """Only nonzero bilinear taps; exact pixel centers need no neighbor."""
    low = floor(value)
    fraction = value - low
    yield low, 1 - fraction
    if fraction:
        yield low + 1, fraction


@dataclass(frozen=True, init=False)
class SourceFrame:
    """Native coordinates -> original source, optionally using an existing view.

    ``room`` is the physical crop; ``extent`` is the world-coordinate footprint
    and can extend beyond it. ``canonical`` must be the already-computed 800x608
    raster for that extent. Nontrivial transforms require it explicitly, so no
    hidden re-inference, second scan or alternate resampler can change phases.
    The RGB wrappers are private snapshots; replacing the caller's fields does
    not change this evidence. Returned pixels retain all three color channels.
    """
    _source: RGBImage = field(repr=False)
    _canonical: RGBImage = field(repr=False)
    room: Box
    extent: Box
    _resize_filter: bool
    _covered_x: tuple[bool, ...] = field(repr=False)
    _covered_y: tuple[bool, ...] = field(repr=False)

    def __init__(self, image: RGBImage, room: Box, *, extent=None, canonical=None):
        source = _frozen_image(image)
        if (room.width <= 0 or room.height <= 0 or room.x < 0 or room.y < 0
                or room.right > source.width or room.bottom > source.height):
            raise ValueError('Physical source room must lie inside the image')
        extent = room if extent is None else extent
        if extent.width <= 0 or extent.height <= 0:
            raise ValueError('Source extent must have positive dimensions')
        resized = canonical is None
        if resized:
            if extent != room:
                raise ValueError('A capture extent requires its existing canonical raster')
            raster = Image.frombytes('RGB', (source.width, source.height), source.data)
            data = raster.crop((room.x, room.y, room.right, room.bottom)).resize(
                (NATIVE_WIDTH, NATIVE_HEIGHT), Image.Resampling.BILINEAR).tobytes()
            canonical = RGBImage(NATIVE_WIDTH, NATIVE_HEIGHT, data)
        canonical = _frozen_image(canonical)
        if (canonical.width, canonical.height) != (NATIVE_WIDTH, NATIVE_HEIGHT):
            raise ValueError('Canonical source view must be 800x608')
        object.__setattr__(self, '_source', source)
        object.__setattr__(self, '_canonical', canonical)
        object.__setattr__(self, 'room', room)
        object.__setattr__(self, 'extent', extent)
        object.__setattr__(self, '_resize_filter', resized)
        def coverage(origin, length, count, crop_low, crop_high):
            radius = max(1., length / count) if resized else 1.
            result = []
            for index in range(count):
                center = origin + (index + .5) * length / count - .5
                if radius > 1:
                    available = crop_low <= center - radius + 1 and center + radius < crop_high
                else:
                    available = all(crop_low <= p < crop_high for p, _ in _taps(center))
                result.append(available)
            return tuple(result)
        object.__setattr__(self, '_covered_x', coverage(extent.x, extent.width, 800, room.x, room.right))
        object.__setattr__(self, '_covered_y', coverage(extent.y, extent.height, 608, room.y, room.bottom))

    @property
    def pitch(self):
        return NATIVE_WIDTH / self.extent.width, NATIVE_HEIGHT / self.extent.height

    def matches_source(self, image, room):
        return (room == self.room and (image.width, image.height, image.data)
                == (self._source.width, self._source.height, self._source.data))

    def original_snapshot(self):
        """An independent wrapper over immutable physical source RGB bytes."""
        return RGBImage(self._source.width, self._source.height, self._source.data)

    @property
    def canonical_rgb(self):
        return self._canonical.data

    def original_position(self, x, y):
        """Physical pixel identity, or unknown. Floor must precede bounds checks.

        In particular, -0.2 must not truncate to pixel 0 and fabricate support.
        No image-edge or crop-edge clamping is permitted.
        """
        if not (isfinite(x) and isfinite(y) and 0 <= x < 800 and 0 <= y < 608):
            return None
        sx = floor(self.extent.x + x * self.extent.width / 800)
        sy = floor(self.extent.y + y * self.extent.height / 608)
        return (sx, sy) if self.room.contains(sx, sy) else None

    def original_pixel(self, x, y):
        position = self.original_position(x, y)
        return None if position is None else self._source.pixel(*position)

    def original_sample(self, x, y):
        """Return physical identity and frozen RGB with one unchanged mapping.

        Callers needing both values must not repeat the coordinate conversion.
        Unknown native/crop coverage remains ``(None, None)``; no canonical
        padding, caller-mutable wrapper or alternate rounding supplies evidence.
        """
        position = self.original_position(x, y)
        return position, None if position is None else self._source.pixel(*position)

    def original_patch(self, cx, cy, size=2):
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError('Patch size must be a positive integer')
        values = []
        for dy in range(size):
            for dx in range(size):
                rgb = self.original_pixel(cx - size / 2 + dx + .5,
                                          cy - size / 2 + dy + .5)
                if rgb is None:
                    return None
                values.append(rgb)
        return values

    def _canonical_available(self, x, y):
        if not (0 <= x < 800 and 0 <= y < 608):
            return False
        # Separability permits exact per-axis coverage reuse, not another scan.
        # EXTENT uses two source taps; resize widens its downsampling filter.
        return self._covered_x[x] and self._covered_y[y]

    def pixel(self, x, y):
        """Filtered RGB only when EVERY contributing tap is original-covered."""
        if not (isfinite(x) and isfinite(y) and 0 <= x < 800 and 0 <= y < 608):
            return None
        values = []
        for px, wx in _taps(x - .5):
            for py, wy in _taps(y - .5):
                if not self._canonical_available(px, py):
                    return None
                values.append((wx * wy, self._canonical.pixel(px, py)))
        return tuple(sum(weight * rgb[c] for weight, rgb in values) for c in range(3))

    def rectangle_available(self, x, y, width, height, *, margin=0):
        """Conservative full support for teacher/signature footprints."""
        return all(self.pixel(px, py) is not None
                   for px in (x - margin + .5, x + width + margin - .5)
                   for py in (y - margin + .5, y + height + margin - .5))
