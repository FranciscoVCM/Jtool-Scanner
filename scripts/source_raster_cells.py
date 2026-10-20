"""Covered original-pixel RGB cells, not colour boxes or collision halos.

The convex hull of at most four raw colours represents local resampling
uncertainty. It does not establish foreground identity or background absence.
"""
from math import dist, floor

from scripts.source_pixel_geometry import original_pixel_bounds


def _sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _cross(a, b):
    return a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]


def _add(a, b, scale=1):
    return tuple(x+scale*y for x, y in zip(a, b))


def _segment(point, a, b):
    vector = _sub(b, a)
    energy = _dot(vector, vector)
    phase = max(0, min(1, _dot(_sub(point, a), vector)/energy)) if energy else 0
    return _add(a, vector, phase)


def _triangle(point, a, b, c):
    u, v, w = _sub(b, a), _sub(c, a), _sub(point, a)
    uu, vv, uv = _dot(u, u), _dot(v, v), _dot(u, v)
    denominator = uu*vv-uv*uv
    if denominator > 1e-12:
        s = (vv*_dot(w, u)-uv*_dot(w, v))/denominator
        t = (uu*_dot(w, v)-uv*_dot(w, u))/denominator
        if s >= 0 and t >= 0 and s+t <= 1:
            return _add(_add(a, u, s), v, t)
    return min((_segment(point, a, b), _segment(point, b, c), _segment(point, c, a)),
               key=lambda value: dist(point, value))


def closest_rgb(point, values):
    """Closest RGB in the exact convex hull of one covered bilinear cell."""
    values = tuple(dict.fromkeys(map(tuple, values)))
    if not values:
        raise ValueError('Known source RGB cell required')
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return _segment(point, *values)
    if len(values) == 3:
        return _triangle(point, *values)
    if len(values) != 4:
        raise ValueError('A physical bilinear cell has at most four colours')
    a, b, c, d = values
    u, v, w, q = _sub(b, a), _sub(c, a), _sub(d, a), _sub(point, a)
    determinant = _dot(u, _cross(v, w))
    if abs(determinant) > 1e-12:
        s = _dot(q, _cross(v, w))/determinant
        t = _dot(u, _cross(q, w))/determinant
        r = _dot(u, _cross(v, q))/determinant
        if min(s, t, r) >= 0 and s+t+r <= 1:
            return tuple(point)
    return min((_triangle(point, a, b, c), _triangle(point, a, b, d),
                _triangle(point, a, c, d), _triangle(point, b, c, d)),
               key=lambda value: dist(point, value))


def source_cell(frame, x, y):
    """Known nonzero bilinear taps at the SAME native point, or unknown.

    Use raw pixel centres, no RGB interpolation, padding, neighbouring-cell
    search or omitted unknown taps. Partial physical squares are unknown too.
    """
    if frame.original_position(x, y) is None:
        return None
    sx = frame.extent.x+x*frame.extent.width/800-.5
    sy = frame.extent.y+y*frame.extent.height/608-.5
    ix, iy = floor(sx), floor(sy)
    xs = (ix,) if sx == ix else (ix, ix+1)
    ys = (iy,) if sy == iy else (iy, iy+1)
    positions = [(a, b) for b in ys for a in xs]
    if any(original_pixel_bounds(frame, *p) is None for p in positions):
        return None
    image = frame.original_snapshot()
    return dict(positions=positions, RGB=[image.pixel(a, b) for a, b in positions])
