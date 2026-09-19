"""Conservative color-gradient direction evidence for covered spike hypotheses.

Possible directions account for rounding in the filtered 8-bit image. They are
an abstention signal, not positive evidence for adding or recovering objects.
"""

from math import hypot, sqrt

from PIL import Image, ImageFilter

from .geometry import Box
from .image import RGBImage


class QuantizedColorSlopeField:
    """Lazily used RGB counterpart to the normalized triangle edge field."""

    def __init__(self, image: RGBImage, room: Box):
        crop = image.crop(room)
        normalized = Image.frombytes("RGB", (crop.width, crop.height), crop.data)
        normalized = normalized.resize((800, 608), Image.Resampling.BILINEAR)
        self.pixels = normalized.filter(ImageFilter.GaussianBlur(.7)).tobytes()
        self.scales: dict[tuple[int, int], float] = {}
        self.scores: dict[tuple, tuple[float, float]] = {}

    def pixel(self, x: int, y: int) -> bytes:
        offset = (min(607, max(0, y)) * 800 + min(799, max(0, x))) * 3
        return self.pixels[offset:offset + 3]

    def gradient(self, x: int, y: int):
        right, left = self.pixel(x + 1, y), self.pixel(x - 1, y)
        below, above = self.pixel(x, y + 1), self.pixel(x, y - 1)
        dx = 1 if x in (0, 799) else 2
        dy = 1 if y in (0, 607) else 2
        return (tuple((right[i] - left[i]) / dx for i in range(3)),
                tuple((below[i] - above[i]) / dy for i in range(3)))

    def patch_scale(self, x: int, y: int) -> float:
        key = x, y
        if key not in self.scales:
            magnitudes = []
            for py in range(y, y + 32):
                for px in range(x, x + 32):
                    gx, gy = self.gradient(px, py)
                    magnitudes.append(sqrt(sum(a*a + b*b for a, b in zip(gx, gy))))
            magnitudes.sort()
            position = (len(magnitudes) - 1) * .90
            lower = int(position)
            upper = min(lower + 1, len(magnitudes) - 1)
            scale = magnitudes[lower] + (magnitudes[upper] - magnitudes[lower]) * (position - lower)
            self.scales[key] = max(1.0, scale)
        return self.scales[key]

    def possible_side_scores(
        self, x: int, y: int, vertices: tuple[tuple[int, int], ...],
    ) -> tuple[float, float]:
        """Fraction of samples compatible with each slope, not confirmed hits.

        A central difference has at most1/2 channel error from quantization of
        its two endpoints; a one-sided border difference has at most1. Bound
        both normal and tangent projections before ruling out an orientation.
        Otherwise low-contrast edges can fail solely because of integer steps.
        """
        key = x, y, vertices
        if key in self.scores:
            return self.scores[key]
        minimum_squared = (self.patch_scale(x, y) * .25) ** 2
        tip, *ends = vertices
        coverages = []
        tangent_ratio = sqrt(1 - .95**2) / .95
        for end in ends:
            tx, ty = end[0] - tip[0], end[1] - tip[1]
            length = hypot(tx, ty)
            nx, ny = -ty / length, tx / length
            hits = 0
            for index in range(12):
                t = .15 + .70 * index / 11
                px, py = x + tip[0] + t * tx, y + tip[1] + t * ty
                for offset in (-2, -1, 0, 1, 2):
                    sx, sy = round(px + offset * nx), round(py + offset * ny)
                    gx, gy = self.gradient(sx, sy)
                    if sum(a*a + b*b for a, b in zip(gx, gy)) < minimum_squared:
                        continue
                    normal = sqrt(sum((a*nx + b*ny)**2 for a, b in zip(gx, gy)))
                    tangent = sqrt(sum((-a*ny + b*nx)**2 for a, b in zip(gx, gy)))
                    ex = 1.0 if sx in (0, 799) else .5
                    ey = 1.0 if sy in (0, 607) else .5
                    normal_error = sqrt(3) * (ex * abs(nx) + ey * abs(ny))
                    tangent_error = sqrt(3) * (ex * abs(ny) + ey * abs(nx))
                    if max(0, tangent - tangent_error) <= (normal + normal_error) * tangent_ratio:
                        hits += 1
                        break
            coverages.append(hits / 12)
        self.scores[key] = coverages[0], coverages[1]
        return self.scores[key]
