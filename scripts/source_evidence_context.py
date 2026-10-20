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
from scripts.source_glyph_prototypes import SourceGlyphEvidence, SourceGlyphLibrary, _dimensions


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
        self._raw_growth_calibration = self._qualified_growth = None
        self._growth_originals = self._growth_texture = self._growth_sizing = None
        self._growth_edges = {}

    def record_material_calibration(self, labels, centers, selected, expanded_proof, tips, backs):
        """Save ORIGINAL calibration before a material-result cache can warm.

        This sidecar never replaces the old expanded roles or diagnostics. Native
        calibration depends only on this context's frozen source/spike locators,
        not pattern mode, water overlays, new proposals or cache capacity.
        """
        self.validate(self._original, self._room)
        value = dict(labels=dict(labels), centers=tuple(tuple(c) for c in centers),
                     selected=frozenset(selected), proof=deepcopy(expanded_proof),
                     tips=dict(tips), backs=dict(backs))
        if self._raw_growth_calibration is None:
            self._raw_growth_calibration = value
        elif self._raw_growth_calibration != value:
            raise ValueError('Original source material calibration changed')

    def begin_growth(self, detections):
        """Bind every ORIGINAL Detection, including nonterrain exclusion boxes."""
        self._validate_growth_originals(detections)
        self._growth_texture = self._growth_sizing = None

    def _validate_growth_originals(self, detections):
        originals = tuple(detections)
        spikes = [(d.type_id, d.x, d.y) for d in originals if 3 <= d.type_id <= 10]
        self.validate(self._original, self._room, spikes)
        if self._growth_originals is None:
            self._growth_originals = deepcopy(originals)
        elif originals != self._growth_originals:
            raise ValueError('Source growth original detections changed; proposals cannot teach')

    def record_growth_sizing(self, detections, proposed, retired):
        self._validate_growth_originals(detections)
        self._growth_sizing = frozenset(proposed), frozenset(retired)

    def record_growth_texture(self, detections, library):
        # The default/bypass path does not bind a growth consumer or retain a
        # second library. On the explicit path this is the ALREADY built original
        # full-pose library, not a constructor callback or generated teacher set.
        if self._growth_originals is not None:
            self._validate_growth_originals(detections)
            self._growth_texture = library

    def record_filled_source(self, detections, frame, evidence):
        """Retain the actual original-stage evidence, never build a second copy."""
        self._validate_growth_originals(detections)
        from scripts.source_filled_pipeline import FilledGlyphEvidence
        if (not frame.matches_source(self._original, self._room) or frame.extent != self._room
                or not isinstance(evidence, FilledGlyphEvidence) or evidence.frame is not frame
                or evidence.original_spikes != tuple(k for k in self._spikes if 3 <= k[0] <= 6)):
            raise ValueError('Filled source evidence must share the original frame and detections')
        existing = getattr(self, '_filled_source', None)
        if existing is not None and (existing[0] is not frame or existing[1] is not evidence):
            raise ValueError('Original filled source evidence cannot be replaced')
        self._filled_source = frame, evidence

    def filled_source(self, detections, frame):
        """Validate every reuse of the original stage's single evidence instance."""
        self._validate_growth_originals(detections)
        saved = getattr(self, '_filled_source', None)
        if saved is None:
            raise ValueError('Missing original filled source evidence')
        if saved[0] is not frame:
            raise ValueError('Original filled source frame changed')
        self.record_filled_source(detections, frame, saved[1])
        return saved[1]

    def growth_evidence(self, detections):
        """Lazy, scan-local qualification; cache hits still validate originals."""
        self._validate_growth_originals(detections)
        if self._qualified_growth is None and self._raw_growth_calibration is not None:
            from scripts.source_growth_confidence import OriginalForegroundQuery, qualify_source_roles
            raw = self._raw_growth_calibration
            field = self.rectangles(self._original, self._room, self._spikes)
            approved, _, observations = qualify_source_roles(
                field, raw['selected'], raw['proof'], self._growth_originals,
                edge_memo=self._growth_edges)
            query = OriginalForegroundQuery(field, approved, raw['centers'], raw['tips'], raw['backs'])
            self._qualified_growth = (dict(labels=raw['labels'], approved=approved), query, observations)
        if self._growth_sizing is None:
            raise ValueError('Missing original sizing provenance for source growth')
        if self._qualified_growth is None:
            calibrations, queries, observations = (), (), []
        else:
            calibration, query, observations = self._qualified_growth
            calibrations, queries = (deepcopy(calibration),), (query,)
        libraries = () if self._growth_texture is None else (self._growth_texture,)
        return dict(calibrations=calibrations, original_foreground_queries=queries,
                    original_texture_libraries=libraries, sizing=self._growth_sizing[0],
                    sizing_retired=self._growth_sizing[1], observations=deepcopy(observations))

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

    def glyph_field(self, image: RGBImage, room: Box, spikes):
        """Raw original ownership, sharing the physical contour cache lazily."""
        self.validate(image, room, spikes)
        if self._glyphs is not None:
            return self._glyphs.raw
        if getattr(self, '_glyph_field', None) is None:
            self._glyph_field = SourceGlyphEvidence(self._source, self._room,
                                                    contour_field=self.contours())
        return self._glyph_field

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
