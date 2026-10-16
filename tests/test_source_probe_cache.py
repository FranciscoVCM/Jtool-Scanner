"""Exact original-RGB probe reuse: availability, numerical parity and isolation."""
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_compact_rectangles import SourceRectangleContext, source_backing_rectangles
from scripts.source_contours import SourceContours
from scripts.source_grid_frame import frame_from_existing_grid
from tests.test_source_compact_rectangles import scene


def fields(*, size=(777, 534), palette=0, limit=4096, squared=False):
    image, room, originals, frame, query = scene(size=size, palette=palette)
    arguments = dict(source_frame=frame, squared_norm=squared)
    return (image, frame, SourceContours(image, frame.extent, **arguments),
            SourceContours(image, frame.extent, probe_cache_limit=limit, **arguments))


class SourceProbeCacheTests(TestCase):
    def compare(self, original, cached, queries):
        for first, second in queries:
            self.assertEqual(original.edge(first, second), cached.edge(first, second))

    def test_reuse_preserves_all_edge_fields_across_palettes_and_scales(self):
        for palette, size in ((0, (608, 416)), (1, (777, 534)), (2, (319, 218))):
            _, _, original, cached = fields(palette=palette, size=size)
            queries = [((x, y), (x + 32, y)) for x in range(144, 200, 4) for y in range(144, 192, 4)]
            queries += [((x + 32, y), (x, y)) for x in range(144, 200, 4) for y in range(144, 192, 4)]
            self.compare(original, cached, queries)
            self.assertGreater(cached.probe_cache_hits, 0)
            self.assertLessEqual(cached.probe_cache_peak, 4096)

    def test_bounded_eviction_does_not_change_results(self):
        _, _, original, cached = fields(limit=3)
        queries = [((160, y), (192, y)) for y in range(150, 194)]
        self.compare(original, cached, queries)
        cached._edges.clear()  # Require recomputation through the evicted probes.
        self.compare(original, cached, reversed(queries))
        self.assertEqual(cached.probe_cache_peak, 3)
        self.assertEqual(len(cached._physical_probes), 3)
        self.assertGreater(cached.probe_cache_misses, 3)

    def test_unknown_padding_is_checked_before_probe_lookup(self):
        _, _, original, cached = fields()
        queries = [((x, 200), (x, 232)) for x in (0, 80, 95, 96, 97, 100, 160, 704, 799)]
        self.compare(original, cached, queries)
        self.assertTrue(cached.edge((80, 200), (80, 232)).unknown)
        for key in cached._physical_probes:
            self.assertTrue(all(cached.source_frame.room.contains(*p) for p in key))

    def test_original_snapshot_not_mutable_caller_wrapper(self):
        image, _, original, cached = fields()
        image.data = bytes(len(image.data))
        self.compare(original, cached, [((160, 160), (192, 160)), ((160, 160), (160, 192))])
        self.assertEqual(cached.image.data, original.image.data)
        self.assertNotEqual(cached.image.data, image.data)

    def test_default_has_no_probe_cache_and_invalid_limits_rejected(self):
        image, frame, original, _ = fields()
        self.assertIsNone(original._physical_probes)
        self.assertEqual(original.probe_cache_hits, 0)
        for limit in (-1, True, 1.5, None):
            with self.assertRaisesRegex(ValueError, 'nonnegative integer'):
                SourceContours(image, frame.extent, source_frame=frame, probe_cache_limit=limit)
        with self.assertRaisesRegex(ValueError, 'immutable original source frame'):
            SourceContours(image, frame.room, probe_cache_limit=1)

    def test_sqrt_and_hypot_modes_do_not_share_phase_results(self):
        for squared in (False, True):
            _, _, original, cached = fields(squared=squared)
            self.compare(original, cached, [((x, 160), (x, 192)) for x in range(150, 194)])

    def test_complete_rectangle_proof_equal_cold_warm_and_parallel_sources(self):
        def evaluate(palette):
            image, room, originals, frame, _ = scene(palette=palette)
            default = source_backing_rectangles(image, room, originals, source_frame=frame)
            context = SourceRectangleContext(image, room, originals, frame, probe_cache_limit=4096)
            first = source_backing_rectangles(image, room, originals, source_frame=frame, source_context=context)
            warm = source_backing_rectangles(image, room, originals, source_frame=frame, source_context=context)
            self.assertEqual(first, default)
            self.assertEqual(first, warm)
            self.assertGreater(context._field.probe_cache_hits, 0)
            self.assertLessEqual(context._field.probe_cache_peak, 4096)
            return context._field._physical_probes
        with ThreadPoolExecutor(max_workers=2) as pool:
            caches = list(pool.map(evaluate, (0, 1)))
        self.assertIsNot(caches[0], caches[1])

    def test_fractional_diagonal_and_one_byte_edges_keep_full_evidence(self):
        for background, foreground in (((128, 128, 128), (129, 128, 128)),
                                       ((0, 130, 0), (255, 0, 0))):
            raster = Image.new('RGB', (800, 608), background)
            ImageDraw.Draw(raster).polygon(((200, 200), (216, 168), (232, 200)), fill=foreground)
            image = RGBImage(800, 608, raster.tobytes())
            room = Box(0, 0, 800, 608)
            normalization = scanner._normalize_room_to_jtool(image, 25, 19)
            frame = frame_from_existing_grid(image, room, (25, 19), normalization)
            original = SourceContours(image, room, source_frame=frame)
            cached = SourceContours(image, room, source_frame=frame, probe_cache_limit=4096)
            queries = [((200 + offset, 200), (216 + offset, 168)) for offset in (0, .125, .5, 1)]
            queries += [(second, first) for first, second in queries]
            self.compare(original, cached, queries)
