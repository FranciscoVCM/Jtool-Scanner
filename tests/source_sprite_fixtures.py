"""Geometry-first synthetic sprites for tests, never scanner input templates.

Coordinates describe pixel *boundaries*. Classify pixel centres explicitly so
an even-width Pillow line centred at x=size/y=size cannot silently lose a face
when a sprite is clipped to its native tile. These are deliberately simple
fixtures, not claims to reproduce every game's sprite artwork.
"""
from math import hypot

from PIL import Image

from jtool_scanner.spike_shape import VERTICES


def hollow_triangle_tile(direction, size, *, background, ink, interior,
                         stroke_width=2):
    """Rasterize a closed native16/32 triangle inside exactly one sprite tile.

    Stroke width is measured about the mathematical triangle edges; only pixel
    centres inside the triangle are painted. No neighbour's pixel is modified.
    """
    if isinstance(direction, bool) or direction not in VERTICES:
        raise ValueError('A full-spike direction3..6 is required')
    if isinstance(size, bool) or size not in (16, 32):
        raise ValueError('A native16 or32 tile is required')
    if (isinstance(stroke_width, bool) or not isinstance(stroke_width, (int, float))
            or not 0 < stroke_width <= size/4):
        raise ValueError('A finite positive stroke no wider than a quarter tile is required')
    polygon = [(u*size/32, v*size/32) for u, v in VERTICES[direction]]
    edges = tuple(zip(polygon, polygon[1:]+polygon[:1]))
    tile = Image.new('RGB', (size, size), background)
    pixels = tile.load()
    for y in range(size):
        for x in range(size):
            cx, cy = x+.5, y+.5
            crosses = [(b[0]-a[0])*(cy-a[1])-(b[1]-a[1])*(cx-a[0])
                       for a, b in edges]
            if not (all(c >= 0 for c in crosses) or all(c <= 0 for c in crosses)):
                continue
            distance = min(abs(c)/hypot(b[0]-a[0], b[1]-a[1])
                           for c, (a, b) in zip(crosses, edges))
            pixels[x, y] = ink if distance <= stroke_width/2 else interior
    return tile
