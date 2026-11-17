"""Original physical pixel eligibility for partial-spike body evidence.

Unbound diagnostic. This removes mixed source samples from an appearance
comparison, not from the image, and does not decide object identity.
"""
from dataclasses import dataclass

from jtool_scanner.spike_shape import VERTICES
from scripts.source_interior_glyphs import INTERIOR_POINTS, _oriented
from scripts.source_partial_visibility import intersects
from scripts.source_pixel_geometry import PolygonPixelCoverage, original_pixel_bounds


@dataclass(frozen=True)
class BodyAperture:
    indices: tuple[int, ...]
    edge_mixed: int
    occluder_mixed: int
    unknown_original: int
    shared_original: int


def whole_source_body_aperture(frame, key, visible_indices, possible_occluders):
    """Keep distinct complete original squares in the visible triangle.

    `visible_indices` and `possible_occluders` come from the original coverage
    proof. The whole square must lie inside the projected triangle and
    outside every possible occluder, not just its sampled native point.
    Callers must still enforce the original minimum independent sample count.
    """
    kind, x, y = key
    area = PolygonPixelCoverage(frame, [(x+a, y+b) for a, b in VERTICES[kind]])
    occluders = tuple(possible_occluders)
    kept = []
    seen = set()
    edge_mixed = occluder_mixed = unknown_original = shared_original = 0
    for i in visible_indices:
        if type(i) is not int or not 0 <= i < len(INTERIOR_POINTS):
            raise ValueError("Invalid original interior sample index")
        a, b = _oriented(kind, *INTERIOR_POINTS[i])
        pixel = frame.original_position(x+a, y+b)
        bounds = None if pixel is None else original_pixel_bounds(frame, *pixel)
        if bounds is None:
            unknown_original += 1
        elif any(intersects(bounds, envelope) for envelope in occluders):
            occluder_mixed += 1
        elif area.overlap(*pixel) < 1 - 1e-8:
            edge_mixed += 1
        elif pixel in seen:
            shared_original += 1
        else:
            kept.append(i)
            seen.add(pixel)
    return BodyAperture(tuple(kept), edge_mixed, occluder_mixed, unknown_original, shared_original)
