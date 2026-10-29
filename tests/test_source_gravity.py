"""Late source-arrow integration and exact legacy colour-score preservation."""
from dataclasses import asdict, replace
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.gravity_shape import original_rgb_patch, source_query_axes
from jtool_scanner.image import RGBImage


def scene(x=160, y=160, size=(800, 608)):
    raster = Image.new('RGB', size, (35, 55, 75))
    draw = ImageDraw.Draw(raster)
    draw.polygon(((x + 16, y + 1), (x + 3, y + 18), (x + 28, y + 18)),
                 fill=(235, 100, 130))
    draw.rectangle((x + 11, y + 17, x + 20, y + 30), fill=(235, 100, 130))
    return raster, RGBImage(*size, raster.tobytes())


def result(image, objects=(), *, extent=None, grid=(25, 19)):
    return scanner.ScanResult(
        image_width=image.width, image_height=image.height,
        room_box=Box(0, 0, image.width, image.height), detections=list(objects),
        infinite_jump=1, dot_kid=1, recognized_text='preserve', source_grid=grid,
        source_extent=extent, structural_warnings=['earlier'] if objects else [],
        dense_miniblock_room=True,
    )


def apply(before, image, packets, *, working=None, extent=None):
    working = image if working is None else working
    return scanner._recover_source_gravity_arrows(
        before, image, packets, sample_image=working,
        sample_room=Box(0, 0, working.width, working.height), source_extent=extent,
    )


class SourceGravityTests(unittest.TestCase):
    def test_add_only_preserves_instances_metadata_flags_and_real_overlaps(self):
        _, image = scene()
        old = scanner.Detection('real_embedded_spike', 6, 160, 160, .73,
                                Box(160, 160, 32, 32))
        before = result(image, [old])
        saved = asdict(before)
        raw = original_rgb_patch(image, before.room_box, 160, 160)
        after = apply(before, image, [(160, 160, raw)])
        self.assertEqual(asdict(before), saved)
        self.assertIs(next(d for d in after.detections if d.type_id == 6), old)
        self.assertEqual([(d.type_id, d.x, d.y) for d in after.detections],
                         [(6, 160, 160), (24, 160, 160)])
        for key in saved:
            if key not in ('detections', 'structural_warnings'):
                self.assertEqual(getattr(after, key), getattr(before, key))

    def test_existing_exact_arrow_is_not_replaced_or_rescored(self):
        _, image = scene()
        old = scanner.Detection('old_arrow', 24, 160, 160, .61, Box(160, 160, 32, 32))
        before = result(image, [old])
        raw = original_rgb_patch(image, before.room_box, 160, 160)
        after = apply(before, image, [(160, 160, raw)])
        self.assertIs(after, before)
        self.assertIs(after.detections[0], old)

    def test_repeated_proposals_are_exactly_deduplicated(self):
        _, image = scene()
        before = result(image)
        raw = original_rgb_patch(image, before.room_box, 160, 160)
        self.assertEqual(len(apply(before, image, [(160, 160, raw)] * 2).detections), 1)

    def test_missing_packets_or_grid_abstain(self):
        _, image = scene()
        before = result(image)
        self.assertIs(apply(before, image, []), before)
        self.assertIs(apply(before, image, None), before)
        unknown = replace(before, source_grid=None)
        self.assertIs(apply(unknown, image, [(160, 160, bytes(768))]), unknown)

    def test_low_resolution_cannot_reuse_duplicated_positive_samples(self):
        _, original = scene()
        raw = original_rgb_patch(original, Box(0, 0, 800, 608), 160, 160)
        image = RGBImage(320, 244, bytes((35, 55, 75)) * (320 * 244))
        before = result(image)
        self.assertIs(apply(before, image, [(160, 160, raw)]), before)

    def test_extended_frame_checks_original_even_when_result_has_no_extent(self):
        raster, working = scene()
        clipped = raster.crop((4, 0, 800, 608))
        image = RGBImage(796, 608, clipped.tobytes())
        before = result(image)
        raw = original_rgb_patch(working, Box(0, 0, 800, 608), 160, 160)
        after = apply(before, image, [(160, 160, raw)], working=working,
                      extent=Box(-4, 0, 800, 608))
        self.assertEqual(after.detections[0].image_box, Box(156, 160, 32, 32))
        self.assertIsNone(after.source_extent)

    def test_canonical_positive_cannot_invent_original_arrow(self):
        _, working = scene()
        image = RGBImage(800, 608, bytes((35, 55, 75)) * (800 * 608))
        before = result(image)
        raw = original_rgb_patch(working, Box(0, 0, 800, 608), 160, 160)
        self.assertIs(apply(before, image, [(160, 160, raw)], working=working), before)

    def test_padded_edge_is_unknown_despite_positive_canonical_shape(self):
        raster, working = scene(x=0)
        clipped = raster.crop((4, 0, 800, 608))
        image = RGBImage(796, 608, clipped.tobytes())
        before = result(image, extent=Box(-4, 0, 800, 608))
        raw = original_rgb_patch(working, Box(0, 0, 800, 608), 0, 160)
        self.assertIs(apply(before, image, [(0, 160, raw)], working=working), before)

    def test_compact_source_offset_is_not_padded_original_evidence(self):
        _, image = scene(64, 64, size=(608, 416))
        working = scanner._normalize_room_to_jtool(image, 19, 13).image
        before = result(image, grid=(19, 13))
        raw = scanner._arrow_rgb_patch(working, Box(0, 0, 800, 608), 160, 160)
        after = apply(before, image, [(160, 160, raw)], working=working)
        self.assertEqual([(d.type_id, d.x, d.y, d.image_box) for d in after.detections],
                         [(24, 160, 160, Box(64, 64, 32, 32))])

    def test_invalid_physical_dimensions_abstain(self):
        _, image = scene()
        self.assertIsNone(source_query_axes(image, Box(0, 0, -800, -608),
            Box(0, 0, 800, 608), 32, 32, (800, 608), (0, 0)))

    def test_shared_packet_preserves_exact_old_scores_in_fractional_clipped_frames(self):
        image = RGBImage(131, 127, bytes((i * 71 + 31) % 256 for i in range(131 * 127 * 3)))
        predicates = (lambda r, g, b: r > 140 and r > g + 30 and r > b + 20,
                      lambda r, g, b: b > 130 and b > r + 70 and g > r + 50)
        for room in (Box(0, 0, 131, 127), Box(-3, 1, 134, 127)):
            for x, y in ((0, 0), (16, 32), (768, 576)):
                raw = scanner._arrow_rgb_patch(image, room, x, y)
                for down, predicate in zip((False, True), predicates):
                    with self.subTest(room=room, x=x, y=y, down=down):
                        self.assertEqual(scanner._arrow_color_shape_score(image, room, x, y, predicate, down),
                            scanner._arrow_color_shape_score(image, room, x, y, predicate, down,
                                                             sampled_rgb=raw))

    def test_old_colour_traversal_reads_each_packet_once_for_both_directions(self):
        _, image = scene()
        class CountingImage:
            width, height = image.width, image.height
            calls = 0
            def pixel(self, x, y):
                self.calls += 1
                return image.pixel(x, y)
        counted = CountingImage()
        packets = []
        self.assertEqual(scanner._detect_gravity_flippers(counted,
                         Box(0, 0, 800, 608), packets=packets), [])
        self.assertEqual(len(packets), 1813)
        self.assertEqual(counted.calls, 1813 * 256)

    def test_root_defers_new_arrows_and_respects_colour_and_shape_controls(self):
        _, image = scene()
        room = Box(0, 0, 800, 608)
        raw = original_rgb_patch(image, room, 160, 160)
        for colour, shapes, expected in ((True, True, [24]), (False, True, []), (True, False, [])):
            def colours(image, box, step, anchors, *, gravity_packets=None):
                self.assertEqual(anchors, [])  # No new marker teaches the old traversal.
                if gravity_packets is not None:
                    gravity_packets.append((160, 160, raw))
                return []
            with self.subTest(colour=colour, shapes=shapes), \
                 patch.object(scanner, '_detect_saves', return_value=[]), \
                 patch.object(scanner, '_detect_warps', return_value=[]), \
                 patch.object(scanner, '_detect_dot_kid_marker', return_value=False), \
                 patch.object(scanner, '_detect_color_objects', side_effect=colours):
                scanned = scanner.scan_image(image, room_box=room, source_grid=(25, 19),
                    include_color_objects=colour, _apply_shape_refits=shapes)
                self.assertEqual([d.type_id for d in scanned.detections], expected)
