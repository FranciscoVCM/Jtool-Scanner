"""Read-only, source-local full-block appearance evidence.

Original block poses are only locators. Every teacher needs four independently
qualified16px source cells and no source-confirmed glyph pixels. This module
neither loads reference maps nor emits objects or changes scanner defaults.
"""
from __future__ import annotations

from copy import deepcopy
from math import ceil, floor, sqrt

from scripts.source_glyph_prototypes import SourceGlyphLibrary, _contains


def _glyph_pixels_in_frame(x, y, bounded_polygons):
    """Reject only polygons containing an actual32-frame pixel centre.

    Bounding-box pruning is an exact shortcut, not overlap-based object removal.
    A polygon merely touching a boundary supplies no covered pixel.
    """
    for poly, x0, y0, x1, y1 in bounded_polygons:
        left, right = max(0, ceil(x0-x-.5)), min(31, floor(x1-x-.5))
        top, bottom = max(0, ceil(y0-y-.5)), min(31, floor(y1-y-.5))
        if left > right or top > bottom:
            continue
        if any(_contains(poly, x+i+.5, y+j+.5)
               for j in range(top, bottom+1) for i in range(left, right+1)):
            return True
    return False


class SourceBlockLibrary:
    """Transient32px prototypes; source ambiguity stays an abstention.

    ``fulls`` must contain only original poses, not newly proposed objects.
    ``textured`` must be independently source-qualified16px cell origins.
    ``polygons`` are independently source-confirmed glyph footprints.
    """

    def __init__(self, library: SourceGlyphLibrary, fulls, textured, polygons):
        self.library = library
        self.results, self.models, self.teachers = {}, [], []
        textured = set(textured)
        bounded = [(p, min(x for x, y in p), min(y for x, y in p),
                    max(x for x, y in p), max(y for x, y in p)) for p in polygons]
        for x, y in sorted(set(fulls)):
            if not (0 <= x <= 768 and 0 <= y <= 576):
                continue
            cells = {(x, y), (x+16, y), (x, y+16), (x+16, y+16)}
            if cells <= textured and not _glyph_pixels_in_frame(x, y, bounded):
                self.teachers.append((x, y))
        seen = set()
        for seed in self.teachers:
            signature = library.signature(3, *seed)
            group = []
            for point in self.teachers:
                other = library.signature(3, *point)
                if sum(a*b for a, b in zip(signature, other)) < .9:
                    continue
                if all(sum(a*b for a, b in zip(other, library.signature(3, *p))) >= .9
                       for p in group):
                    group.append(point)
            identity = tuple(group)
            if len({(x//32, y//32) for x, y in group}) < 3 or identity in seen:
                continue
            seen.add(identity)
            mean = tuple(sum(library.signature(3, *p)[k] for p in group)/len(group)
                         for k in range(768))
            length = sqrt(sum(v*v for v in mean))
            self.models.append(dict(source_teachers=group,
                                    signature=tuple(v/max(1e-12, length) for v in mean)))

    def support(self, x, y):
        """Return an isolated proof; a query never teaches or emits terrain."""
        if (x, y) not in self.results:
            best = dict(passed=False, correlation=None, source_teachers=[], phase=None)
            for dx in (0, -self.library.pitch[0], self.library.pitch[0]):
                for dy in (0, -self.library.pitch[1], self.library.pitch[1]):
                    if not (0 <= x+dx <= 768 and 0 <= y+dy <= 576):
                        continue
                    query = self.library.signature(3, x+dx, y+dy)
                    for model in self.models:
                        score = sum(a*b for a, b in zip(query, model['signature']))
                        if best['correlation'] is None or score > best['correlation']:
                            best = dict(passed=score >= .9, correlation=score,
                                        source_teachers=model['source_teachers'], phase=[dx, dy],
                                        entire_source_frame_unmasked=True,
                                        independent_source_teachers_only=True)
            self.results[x, y] = best
        return deepcopy(self.results[x, y])
