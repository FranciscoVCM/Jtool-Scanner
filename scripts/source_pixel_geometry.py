"""Exact geometric footprints of ORIGINAL source pixels; not sprite ownership.

A pixel centre can lie outside a triangle while part of that pixel square lies
inside it. This component measures that distinction without reading/resampling
RGB, inferring a transform, widening a shape or making a detection decision.
It is not bound to the scanner. Fractions are geometric area, NOT image alpha.
"""
from dataclasses import dataclass
from math import isfinite

from scripts.source_sampling import SourceFrame


def original_pixel_bounds(frame, sx, sy):
    """Native bounds of one whole physical pixel, or None for missing coverage.

    Pixel identities are integer source coordinates. A pixel outside the crop
    or world extent is unknown, even if the full image/canonical raster has RGB
    at that location. No rounding or edge clamping can fabricate evidence.
    """
    if not isinstance(frame, SourceFrame):
        raise ValueError('An existing original SourceFrame is required')
    if any(not isinstance(v, int) or isinstance(v, bool) for v in (sx, sy)):
        raise ValueError('Physical pixel identities must be integers')
    crop, world = frame.room, frame.extent
    if not (crop.x <= sx and sx + 1 <= crop.right and crop.y <= sy and sy + 1 <= crop.bottom
            and world.x <= sx and sx + 1 <= world.right and world.y <= sy and sy + 1 <= world.bottom):
        return None
    return ((sx-world.x)*800/world.width, (sy-world.y)*608/world.height,
            (sx+1-world.x)*800/world.width, (sy+1-world.y)*608/world.height)


def _vertices(values):
    try:
        points = tuple(tuple(p) for p in values)
    except TypeError as error:
        raise ValueError('A finite convex polygon is required') from error
    def finite_number(value):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return isfinite(value)
        except OverflowError:
            return False
    if (len(points) < 3 or any(len(p) != 2 for p in points)
            or any(not finite_number(v) for p in points for v in p)
            or len(set(points)) != len(points)):
        raise ValueError('A finite convex polygon with distinct vertices is required')
    turns = []
    for a, b, c in zip(points, points[1:]+points[:1], points[2:]+points[:2]):
        turn = (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])
        if not finite_number(turn):
            raise ValueError('Polygon arithmetic must remain finite')
        if turn:
            turns.append(turn > 0)
    if not turns or not (all(turns) or not any(turns)):
        raise ValueError('A nondegenerate convex polygon is required')
    # Same-signed local turns alone also admit self-intersecting stars. Every
    # other vertex must lie on the interior side of EVERY supporting edge.
    orientation = 1 if turns[0] else -1
    for a, b in zip(points, points[1:]+points[:1]):
        for c in points:
            cross = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
            if not finite_number(cross) or orientation*cross < 0:
                raise ValueError('A simple convex polygon is required')
    return points


def _unit_square_area(polygon):
    result = polygon
    for axis, bound, side in ((0, 0., 1), (0, 1., -1), (1, 0., 1), (1, 1., -1)):
        current, result = result, []
        if not current:
            return 0.
        previous = current[-1]
        old_inside = (previous[axis]-bound)*side >= 0
        for point in current:
            inside = (point[axis]-bound)*side >= 0
            if inside != old_inside:
                fraction = (bound-previous[axis])/(point[axis]-previous[axis])
                result.append(tuple(previous[i]+fraction*(point[i]-previous[i]) for i in (0, 1)))
            if inside:
                result.append(point)
            previous, old_inside = point, inside
    area = abs(sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(result, result[1:]+result[:1])))/2
    # Only floating arithmetic is bounded here, not recognition confidence.
    return min(1., max(0., area))


@dataclass(frozen=True, init=False)
class PolygonPixelCoverage:
    """One immutable convex native polygon in an existing original source frame.

    A known zero is distinct from unknown (None). Positive area does not label
    an entire mixed pixel foreground/background or authorize object deletion.
    Reuse this prevalidated polygon rather than validating it per sample.
    """
    frame: SourceFrame
    vertices: tuple

    def __init__(self, frame, vertices):
        if not isinstance(frame, SourceFrame):
            raise ValueError('An existing original SourceFrame is required')
        object.__setattr__(self, 'frame', frame)
        object.__setattr__(self, 'vertices', _vertices(vertices))

    def overlap(self, sx, sy):
        """Fraction of this original pixel square intersecting the polygon."""
        bounds = original_pixel_bounds(self.frame, sx, sy)
        if bounds is None:
            return None
        x0, y0, x1, y1 = bounds
        # Local unit coordinates avoid cancellation from large native origins.
        local = [((x-x0)/(x1-x0), (y-y0)/(y1-y0)) for x, y in self.vertices]
        return _unit_square_area(local)
