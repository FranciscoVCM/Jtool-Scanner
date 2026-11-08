"""Physical RGB transition evidence, independent of a sprite or wall model.

The caller supplies already established endpoint roles and a fixed physical
normal. A witnessed mixture does not assert solid occupancy, prove an
occluder, or authorize an object. This helper is not bound to the scanner.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from scripts.source_sampling import SourceFrame


@dataclass(frozen=True, slots=True)
class RGBBracket:
    """An observed middle color between two distinct original source pixels."""

    first: tuple[tuple[int, int], tuple[int, int, int]]
    middle: tuple[tuple[int, int], tuple[int, int, int]]
    last: tuple[tuple[int, int], tuple[int, int, int]]
    alpha_numerator: int
    denominator: int
    residual_numerator: int

    @property
    def alpha(self) -> float:
        return self.alpha_numerator / self.denominator

    @property
    def max_rgb_residual(self) -> float:
        return self.residual_numerator / self.denominator


def _role(values):
    rgb = tuple(values)
    if len(rgb) != 3 or any(
        isinstance(v, bool) or not isinstance(v, (int, float))
        or not isfinite(v) or not 0 <= v <= 255 for v in rgb
    ):
        raise ValueError("An endpoint role must contain three finite RGB channels")
    return rgb


def _difference(a, b):
    return max(abs(x - y) for x, y in zip(a, b, strict=True))


def bracket_original_rgb(
    frame: SourceFrame,
    first_point: tuple[float, float],
    middle_point: tuple[float, float],
    last_point: tuple[float, float],
    *,
    first_role: tuple[float, float, float],
    last_role: tuple[float, float, float],
) -> RGBBracket | None:
    """Check one fixed, axis-aligned wall/ink bracket in the original capture.

    The three points are native coordinates in physical order along the
    supplied normal. Only distinct original pixels on the same physical
    row/column count, with at most two physical pixels on either side of
    the middle. Unavailable pixels, uncertain endpoint roles, reversed
    roles, and a middle sample outside the observed RGB segment abstain.
    Segment decisions use integer dot products; only reporting uses floats.
    """
    if not isinstance(frame, SourceFrame):
        raise TypeError("RGB bracketing requires an original SourceFrame")
    first_role, last_role = _role(first_role), _role(last_role)
    if _difference(first_role, last_role) < 36:
        return None
    native = first_point, middle_point, last_point
    positions = tuple(frame.original_position(*point) for point in native)
    if any(position is None for position in positions) or len(set(positions)) != 3:
        return None
    a, b, c = positions
    if not any(
        a[1 - axis] == b[1 - axis] == c[1 - axis]
        and min(a[axis], c[axis]) < b[axis] < max(a[axis], c[axis])
        and max(abs(a[axis] - b[axis]), abs(c[axis] - b[axis])) <= 2
        for axis in (0, 1)
    ):
        return None
    first, middle, last = (frame.original_pixel(*point) for point in native)
    if _difference(first, first_role) > 16 or _difference(last, last_role) > 16:
        return None

    delta = tuple(t - s for s, t in zip(first, last, strict=True))
    offset = tuple(p - s for p, s in zip(middle, first, strict=True))
    denominator = sum(d * d for d in delta)
    numerator = sum(d * o for d, o in zip(delta, offset, strict=True))
    if not denominator or not denominator <= 10 * numerator <= 9 * denominator:
        return None
    residual = max(abs(o * denominator - d * numerator) for d, o in zip(delta, offset, strict=True))
    if residual > 8 * denominator:
        return None
    return RGBBracket((a, first), (b, middle), (c, last), numerator, denominator, residual)
