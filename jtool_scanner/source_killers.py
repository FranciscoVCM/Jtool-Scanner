"""Original-source cell evidence for compact-room killblock identities.

Padding a compact room to the working canvas can change sample phase. Integrate
the established colour predicate over actual source pixels instead of giving
each resampled probe a whole vote. Crossed dim tiles retain the existing shape
predicate and its physical-sample guards; no reference geometry is consulted.
"""

from array import array
from math import floor

from .geometry import Box
from .image import RGBImage
from .killer_shape import red_cross_shape_supported


class RegisteredCellEvidence:
    """Known, fully captured compact cells; inactive without source quorum."""

    def __init__(self, image: RGBImage, room: Box, grid: tuple[int, int] | None):
        self.image, self.room, self.grid = image, room, grid
        self.ratios: dict[tuple[int, int], float] = {}
        self.colour_positives: set[tuple[int, int]] = set()
        self.active = False
        if grid is None:
            return
        columns, rows = grid
        if not (4 <= columns < 25 and 4 <= rows < 19
                and room.width / columns >= 16 and room.height / rows >= 16):
            return
        if (room.x < 0 or room.y < 0 or room.right > image.width
                or room.bottom > image.height):
            return
        width, height = room.width, room.height
        stride = width + 1
        sums = array('I', [0]) * ((width + 1) * (height + 1))
        for y in range(height):
            count = 0
            for x in range(width):
                r, g, b = image.pixel(room.x + x, room.y + y)
                count += r > 90 and r > g * 1.25 and r > b * 1.30
                sums[(y + 1) * stride + x + 1] = sums[y * stride + x + 1] + count
        self.sums, self.stride = sums, stride
        for cy in range(rows):
            for cx in range(columns):
                x0, x1 = cx * width / columns, (cx + 1) * width / columns
                y0, y1 = cy * height / rows, (cy + 1) * height / rows
                area = (self.prefix(x1, y1) - self.prefix(x0, y1)
                        - self.prefix(x1, y0) + self.prefix(x0, y0))
                ratio = area / ((x1 - x0) * (y1 - y0))
                self.ratios[cx, cy] = ratio
                if ratio >= .97:
                    self.colour_positives.add((cx, cy))
        # Independent original colour observations, not emitted detections.
        self.active = len(self.colour_positives) >= 3

    def prefix(self, x: float, y: float) -> float:
        """Area integral through a fractional source-pixel boundary."""
        ix, iy = floor(x), floor(y)
        dx, dy = x - ix, y - iy
        base = iy * self.stride + ix
        value = self.sums[base]
        if dx:
            value += dx * (self.sums[base + 1] - self.sums[base])
        if dy:
            value += dy * (self.sums[base + self.stride] - self.sums[base])
        if dx and dy:
            value += dx * dy * (self.sums[base + self.stride + 1]
                                - self.sums[base + 1]
                                - self.sums[base + self.stride] + self.sums[base])
        return value

    def samples(self, cx: int, cy: int, size: int):
        columns, rows = self.grid
        xs = tuple(floor(self.room.x + (cx + (i + .5) / size)
                         * self.room.width / columns) for i in range(size))
        ys = tuple(floor(self.room.y + (cy + (i + .5) / size)
                         * self.room.height / rows) for i in range(size))
        return [self.image.pixel(x, y) for y in ys for x in xs], (xs, ys)

    def proof(self, cx: int, cy: int):
        if not self.active:
            return None
        if (cx, cy) in self.colour_positives:
            return dict(colour=True, area_ratio=self.ratios[cx, cy])
        colours, _ = self.samples(cx, cy, 16)
        if sum(r > g * 1.25 and r > b * 1.30 for r, g, b in colours) / 256 < .97:
            return None
        detail, axes = self.samples(cx, cy, 32)
        columns, rows = self.grid
        physical_axes = (axes if self.room.width / columns < 32
                         or self.room.height / rows < 32 else None)
        if not red_cross_shape_supported(colours, detail, physical_axes=physical_axes):
            return None
        return dict(colour=False, area_ratio=self.ratios[cx, cy])
