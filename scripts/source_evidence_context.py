"""Explicit per-source evidence reuse, without globals or constructor patches.

Original poses only locate source hypotheses. Freeze them before any new proposals;
queries must never extend the teacher set. This context does not load references,
emit geometry or bind the application's detector.
"""
from __future__ import annotations

from copy import deepcopy

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_contours import SourceContours
from scripts.source_glyph_prototypes import SourceGlyphLibrary, _dimensions


def _locators(spikes):
    result = tuple(sorted(set(map(tuple, spikes))))
    for key in result:
        if len(key) != 3:
            raise ValueError("Source locators must be type,x,y triples")
        _dimensions(key[0])
    return result


def _copy_material_result(result):
    # Native cells are immutable coordinate tuples. Rebuilding their set during
    # deepcopy changes iteration order (and ordered teacher diagnostics); copy
    # the set's structure while keeping all nested proof data independent.
    cells, proof = result
    return cells.copy(), deepcopy(proof)


class SourceEvidenceContext:
    """One image/room/original-locator snapshot and lazily built shared evidence.

    Uses immutable RGB bytes and a separate image wrapper so a caller cannot
    poison cached evidence by replacing fields on its mutable RGBImage instance.
    Explicit reuse rejects changed frames, changed bytes and new teacher poses.
    Do not keep this context beyond its scan or share it between worker threads.
    """

    def __init__(self, image: RGBImage, room: Box, spikes, *, pixel_cache_limit=0,
                 material_cache_limit=4):
        if not isinstance(image.data, bytes) or len(image.data) != image.width * image.height * 3:
            raise ValueError("Source evidence needs complete immutable RGB bytes")
        if room.width <= 0 or room.height <= 0 or room.x < 0 or room.y < 0 or room.right > image.width or room.bottom > image.height:
            raise ValueError("The room must lie inside the original source image")
        if not isinstance(pixel_cache_limit, int) or isinstance(pixel_cache_limit, bool) or pixel_cache_limit < 0:
            raise ValueError("Pixel cache limit must be a nonnegative integer")
        if not isinstance(material_cache_limit, int) or isinstance(material_cache_limit, bool) or material_cache_limit < 0:
            raise ValueError("Material cache limit must be a nonnegative integer")
        self._original = image
        self._source = RGBImage(image.width, image.height, image.data)
        self._room = room
        self._spikes = _locators(spikes)
        self._pixel_cache_limit = pixel_cache_limit
        self._contours = self._glyphs = None
        self._rectangles = self._native_pixels = None
        self._material_cache_limit = material_cache_limit
        self._material_results = {}
        self._material_builds = self._material_hits = 0
        self.glyph_builds = self.glyph_reuses = 0

    def material_result(self, image, room, spikes, stage, settings, compute):
        """Reuse complete source proofs, never generated cells as teachers.

        Settings include pattern mode and original water boxes at the caller.
        Full capacity falls back to computation, without truncation or eviction.
        Both the stored result and every returned hit are independent copies.
        """
        self.validate(image, room, spikes)
        if stage not in ('eligible', 'intrinsic', 'local', 'distributed'):
            raise ValueError('Unknown source material stage')
        key = stage, settings
        if key in self._material_results:
            self._material_hits += 1
            return _copy_material_result(self._material_results[key])
        self._material_builds += 1
        result = compute()
        if len(self._material_results) < self._material_cache_limit:
            self._material_results[key] = _copy_material_result(result)
        return result

    def material_statistics(self):
        """Separate instrumentation; it cannot change recognition diagnostics."""
        return dict(limit=self._material_cache_limit, entries=len(self._material_results),
                    builds=self._material_builds, hits=self._material_hits)

    def validate(self, image: RGBImage, room: Box, spikes=None):
        if image is not self._original or image.data is not self._source.data or (
            image.width, image.height, room
        ) != (self._source.width, self._source.height, self._room):
            raise ValueError("Source context image/data/room changed")
        if spikes is not None and _locators(spikes) != self._spikes:
            raise ValueError("Source context original locators changed; proposals cannot teach")

    def contours(self):
        self.validate(self._original, self._room)
        if self._contours is None:
            self._contours = SourceContours(self._source, self._room)
        return self._contours

    def glyph_library(self, image: RGBImage, room: Box, spikes):
        self.validate(image, room, spikes)
        if self._glyphs is None:
            self._glyphs = SourceGlyphLibrary(self._source, self._room, self._spikes,
                contour_field=self.contours(), pixel_cache_limit=self._pixel_cache_limit)
            self.glyph_builds += 1
        else:
            self.glyph_reuses += 1
        return self._glyphs

    def statistics(self):
        glyphs = self._glyphs
        return dict(glyph_builds=self.glyph_builds, glyph_reuses=self.glyph_reuses,
            pixel_cache_limit=self._pixel_cache_limit,
            pixel_cache_entries=len(glyphs._pixel_results) if glyphs else 0,
            pixel_hits=glyphs.pixel_cache_hits if glyphs else 0,
            pixel_misses=glyphs.pixel_cache_misses if glyphs else 0,
            pixel_cache_peak=glyphs.pixel_cache_peak if glyphs else 0)

    def rectangles(self, image, room, spikes):
        """Reuse the material kernel with its original sqrt arithmetic."""
        self.validate(image, room, spikes)
        if self._rectangles is None:
            from scripts.source_material_evidence import SourceRectangles
            self._rectangles = SourceRectangles(self._source, self._room)
        return self._rectangles

    def native_pixels(self, image, room):
        """One exact original RGB crop/normalization for material consumers."""
        self.validate(image, room)
        if self._native_pixels is None:
            from PIL import Image
            source = Image.frombytes('RGB', (self._source.width, self._source.height), self._source.data)
            self._native_pixels = source.crop((room.x, room.y, room.right, room.bottom)).resize(
                (800, 608), Image.Resampling.BILINEAR).tobytes()
        return self._native_pixels
