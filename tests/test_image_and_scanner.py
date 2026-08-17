from __future__ import annotations

from pathlib import Path
import unittest

from jtool_scanner.constants import (
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_JUMP_REFRESHER,
    OBJ_PLAYER_START,
    OBJ_SAVE,
    OBJ_SPIKE_UP,
    OBJ_WALLJUMP_LEFT,
    OBJ_WATER_2,
    OBJ_WARP,
)
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage, load_png
from jtool_scanner.jmap import JMap, JMapObject
from jtool_scanner.render_overlay import render_detection_overlay
from jtool_scanner.scanner import (
    _detect_bounded_cool_water,
    _detect_saves,
    _matches_spatial_background_field,
    _patch_color_profile,
    _spatial_background_field,
    _detect_red_body_header_saves,
    _detect_weak_active_save_patches,
    _normalize_room_to_jtool,
    _text_indicates_infinite_jump,
    scan_image,
)


class ImageAndScannerTests(unittest.TestCase):
    def test_infinite_jump_phrase_variants_are_recognized_conservatively(self) -> None:
        positive = (
            "You can jump many times!!",
            "You can infinity jump",
            "You can jump infinitely",
            "Unlimited jumps",
            "Jump forever",
        )
        for text in positive:
            with self.subTest(text=text):
                self.assertTrue(_text_indicates_infinite_jump(text))
        self.assertFalse(_text_indicates_infinite_jump("You can jump twice"))
        self.assertFalse(_text_indicates_infinite_jump("Infinite lives"))

    def test_scan_result_carries_infinite_jump_into_jmap(self) -> None:
        result = scan_image(
            _synthetic_room(),
            room_box=Box(0, 0, 800, 608),
            recognized_text="You can jump infinitely",
        )

        self.assertEqual(result.infinite_jump, 1)
        self.assertEqual(result.to_jmap().infinite_jump, 1)

    def test_scan_result_detects_dotkid_visibility_ring(self) -> None:
        result = scan_image(
            _synthetic_dotkid_room(),
            room_box=Box(0, 0, 800, 608),
        )

        self.assertEqual(result.dot_kid, 1)
        self.assertEqual(result.to_jmap().dot_kid, 1)

    def test_ordinary_warp_ring_does_not_enable_dotkid(self) -> None:
        result = scan_image(
            _synthetic_room(),
            room_box=Box(0, 0, 800, 608),
        )

        self.assertEqual(result.dot_kid, 0)

    def test_small_room_normalization_uses_left_and_down_bias(self) -> None:
        image = RGBImage(640, 384, bytes((12, 18, 24)) * 640 * 384)

        normalized = _normalize_room_to_jtool(image, 20, 12)

        self.assertEqual((normalized.image.width, normalized.image.height), (800, 608))
        self.assertEqual((normalized.source_offset_x, normalized.source_offset_y), (-64, -128))

    def test_large_room_normalization_keeps_lower_left_viewport(self) -> None:
        image = RGBImage(960, 704, bytes((12, 18, 24)) * 960 * 704)

        normalized = _normalize_room_to_jtool(image, 30, 22)

        self.assertEqual((normalized.image.width, normalized.image.height), (800, 608))
        self.assertEqual((normalized.source_offset_x, normalized.source_offset_y), (0, 96))

    def test_load_png_reads_fixture_dimensions(self) -> None:
        image = load_png(Path("fixtures/irkara/irkara-58-game.png"))

        self.assertEqual((image.width, image.height), (956, 718))
        self.assertIsInstance(image.pixel(0, 0), tuple)

    def test_scan_image_detects_synthetic_save_and_warp(self) -> None:
        image = _synthetic_room()

        result = scan_image(image, room_box=Box(0, 0, 800, 608), grid_step=16)
        saves = [det for det in result.detections if det.type_id == OBJ_SAVE]
        warps = [det for det in result.detections if det.type_id == OBJ_WARP]

        self.assertEqual(len(saves), 1)
        self.assertEqual((saves[0].x, saves[0].y), (64, 96))
        self.assertEqual(len(warps), 1)
        self.assertEqual((warps[0].x, warps[0].y), (320, 192))

    def test_filled_purple_component_with_dark_center_is_not_a_warp(self) -> None:
        result = scan_image(
            _synthetic_filled_warp_impostor_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=16,
        )

        self.assertFalse(
            any(det.type_id == OBJ_WARP for det in result.detections)
        )

    def test_elongated_hollow_purple_component_is_not_a_warp(self) -> None:
        result = scan_image(
            _synthetic_elongated_warp_impostor_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=16,
        )

        self.assertFalse(
            any(det.type_id == OBJ_WARP for det in result.detections)
        )

    def test_scan_image_treats_green_active_save_as_save(self) -> None:
        result = scan_image(
            _synthetic_active_save_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=16,
        )

        saves = [det for det in result.detections if det.type_id == OBJ_SAVE]
        self.assertEqual(len(saves), 1)
        self.assertEqual((saves[0].x, saves[0].y), (64, 96))

    def test_layout_recovery_finds_player_occluded_active_save(self) -> None:
        image = _synthetic_occluded_active_save_room()

        saves = _detect_weak_active_save_patches(
            image,
            Box(0, 0, 800, 608),
            8,
        )

        self.assertEqual(len(saves), 1)
        self.assertEqual(saves[0].kind, "save_active_layout_recovery")
        self.assertEqual((saves[0].x, saves[0].y), (96, 96))

    def test_layout_recovery_rejects_decorative_picture_colors(self) -> None:
        image = load_png(
            Path("fixtures/block_spike/irkara-nr-flames-game.png")
        )
        room = Box(0, 0, image.width, image.height)

        saves = _detect_saves(image, room, 8)

        self.assertEqual(
            [(save.x, save.y) for save in saves],
            [(64, 128)],
        )

    def test_compact_occluded_save_uses_downsampled_yellow_budget(self) -> None:
        source = load_png(Path("fixtures/block_spike/nang128-game.png"))

        result = scan_image(
            source,
            grid_step=16,
            source_grid=(19, 13),
        )

        saves = [
            detection
            for detection in result.detections
            if detection.type_id == OBJ_SAVE
        ]
        self.assertEqual(
            [(save.x, save.y) for save in saves],
            [(160, 416)],
        )

    def test_compact_palette_shifted_save_recovers_pale_header(self) -> None:
        source = load_png(Path("fixtures/block_spike/nang135-game.png"))

        result = scan_image(
            source,
            grid_step=16,
            source_grid=(19, 13),
        )

        saves = [
            detection
            for detection in result.detections
            if detection.type_id == OBJ_SAVE
        ]
        self.assertEqual(
            [(save.x, save.y) for save in saves],
            [(160, 448)],
        )

    def test_fragmented_red_cross_is_detected_as_save(self) -> None:
        result = scan_image(
            _synthetic_fragmented_cross_save_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
        )

        saves = [det for det in result.detections if det.type_id == OBJ_SAVE]
        self.assertEqual(len(saves), 1)
        self.assertEqual(saves[0].kind, "save_fragmented_cross")

    def test_red_body_and_pale_header_recover_muted_cross_save(self) -> None:
        saves = _detect_red_body_header_saves(
            _synthetic_muted_cross_save_room(with_header=True),
            Box(0, 0, 800, 608),
            8,
        )

        self.assertEqual(
            [(save.kind, save.x, save.y) for save in saves],
            [("save_red_body_header", 96, 96)],
        )

    def test_scan_reanchors_unanchored_red_body_header_phase(self) -> None:
        result = scan_image(
            _synthetic_low_body_header_save_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
        )

        saves = [
            detection
            for detection in result.detections
            if detection.type_id == OBJ_SAVE
        ]
        self.assertEqual(
            [(save.kind, save.x, save.y) for save in saves],
            [("save_header_aligned", 96, 96)],
        )

    def test_red_body_without_pale_header_is_not_a_save(self) -> None:
        saves = _detect_red_body_header_saves(
            _synthetic_muted_cross_save_room(with_header=False),
            Box(0, 0, 800, 608),
            8,
        )

        self.assertEqual(saves, [])

    def test_fragmented_red_body_with_weak_header_detail_is_not_a_save(self) -> None:
        saves = _detect_red_body_header_saves(
            _synthetic_fragmented_header_save_room(header_dark_width=4),
            Box(0, 0, 800, 608),
            8,
        )

        self.assertEqual(saves, [])

    def test_fragmented_red_save_body_recovers_headered_terrain_save(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "cn3-18-game.png")
        saves = _detect_saves(image, Box(0, 0, image.width, image.height), 8)

        self.assertTrue(
            any(
                save.x == 224
                and save.kind == "save_red_body_header_fragmented"
                for save in saves
            )
        )

    def test_fragmented_red_terrain_is_not_a_save_body(self) -> None:
        fixture_dir = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "regressions"
            / "unseen-rooms"
            / "ftfa"
        )
        image = load_png(fixture_dir / "screen-1-source.png")
        saves = _detect_red_body_header_saves(
            image,
            Box(0, 0, image.width, image.height),
            8,
        )

        self.assertFalse(
            any(save.kind == "save_red_body_header_fragmented" for save in saves)
        )

    def test_active_save_layout_rejects_floor_number_glyphs(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "f189-game.png")
        saves = _detect_saves(image, Box(0, 0, image.width, image.height), 8)

        self.assertEqual(len(saves), 1)
        self.assertNotEqual((saves[0].x, saves[0].y), (720, 32))

    def test_repeated_yellow_terrain_is_not_a_field_of_saves(self) -> None:
        result = scan_image(
            _synthetic_repeated_yellow_terrain_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
        )

        self.assertFalse(
            any(det.type_id == OBJ_SAVE for det in result.detections)
        )

    def test_scan_image_can_include_experimental_geometry(self) -> None:
        image = _synthetic_geometry_room()

        result = scan_image(
            image,
            room_box=Box(0, 0, 800, 608),
            grid_step=16,
            include_geometry=True,
        )
        blocks = [det for det in result.detections if det.type_id == OBJ_BLOCK]
        spikes = [det for det in result.detections if det.type_id == OBJ_SPIKE_UP]

        self.assertTrue(any((det.x, det.y) == (96, 64) for det in blocks))
        self.assertTrue(any((det.x, det.y) == (160, 64) for det in spikes))

    def test_scan_image_can_include_color_objects(self) -> None:
        image = _synthetic_color_object_room()

        result = scan_image(
            image,
            room_box=Box(0, 0, 800, 608),
            grid_step=16,
            include_color_objects=True,
        )
        apples = [det for det in result.detections if det.type_id == OBJ_APPLE]
        water = [det for det in result.detections if det.type_id == OBJ_WATER_2]
        walljumps = [det for det in result.detections if det.type_id == OBJ_WALLJUMP_LEFT]

        self.assertTrue(any((det.x, det.y) == (336, 112) for det in apples))
        self.assertTrue(any((det.x, det.y) == (192, 128) for det in water))
        self.assertTrue(any((det.x, det.y) == (64, 192) for det in walljumps))

    def test_single_blue_disc_is_a_jump_refresher_but_square_texture_is_not(self) -> None:
        true_result = scan_image(
            _synthetic_blue_refresher_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )
        false_result = scan_image(
            _synthetic_blue_square_texture_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )

        self.assertEqual(
            sum(det.type_id == OBJ_JUMP_REFRESHER for det in true_result.detections),
            1,
        )
        self.assertFalse(
            any(det.type_id == OBJ_JUMP_REFRESHER for det in false_result.detections)
        )

    def test_scan_image_can_recover_sparse_walljump_marks(self) -> None:
        image = _synthetic_sparse_walljump_room()

        result = scan_image(
            image,
            room_box=Box(0, 0, 800, 608),
            include_color_objects=True,
        )
        walljumps = [det for det in result.detections if det.type_id == OBJ_WALLJUMP_LEFT]

        self.assertTrue(any((det.x, det.y) == (96, 96) for det in walljumps))
        self.assertFalse(any((det.x, det.y) == (192, 96) for det in walljumps))

    def test_repeated_sparse_walljump_strip_is_brightness_independent(self) -> None:
        result = scan_image(
            _synthetic_dark_repeated_walljump_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )
        walljumps = [
            det for det in result.detections if det.type_id == OBJ_WALLJUMP_LEFT
        ]

        self.assertTrue(any((det.x, det.y) == (96, 96) for det in walljumps))
        self.assertTrue(any((det.x, det.y) == (96, 128) for det in walljumps))
        self.assertFalse(any(det.x == 192 for det in walljumps))

    def test_scan_image_can_include_pale_water(self) -> None:
        image = _synthetic_pale_water_room()

        result = scan_image(
            image,
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )
        water = [det for det in result.detections if det.type_id == OBJ_WATER_2]

        self.assertTrue(any((det.x, det.y) == (96, 96) for det in water))

    def test_water_colored_room_background_is_not_water(self) -> None:
        result = scan_image(
            _synthetic_water_colored_background_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )

        self.assertFalse(
            any(det.type_id == OBJ_WATER_2 for det in result.detections)
        )

    def test_winding_flat_background_between_solids_is_not_water(self) -> None:
        result = scan_image(
            _synthetic_winding_water_colored_background_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )

        self.assertFalse(
            any(det.type_id == OBJ_WATER_2 for det in result.detections)
        )

    def test_broad_basin_with_distinct_top_background_remains_water(self) -> None:
        result = scan_image(
            _synthetic_broad_water_basin_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )

        self.assertGreater(
            sum(det.type_id == OBJ_WATER_2 for det in result.detections),
            100,
        )

    def test_spatial_background_field_follows_gradient_but_excludes_bounded_pool(self) -> None:
        image = _synthetic_gradient_with_bounded_pool()
        room = Box(0, 0, 800, 608)

        field = _spatial_background_field(image, room)
        background = _patch_color_profile(image, room, 640, 256, 32)
        pool = _patch_color_profile(image, room, 352, 288, 32)

        self.assertGreater(len(field), 1000)
        self.assertTrue(
            _matches_spatial_background_field(640, 256, background, field)
        )
        self.assertFalse(_matches_spatial_background_field(352, 288, pool, field))

    def test_bounded_violet_water_is_detected_outside_a_broad_background(self) -> None:
        detections = _detect_bounded_cool_water(
            _synthetic_bounded_violet_water_room(textured=False),
            Box(0, 0, 800, 608),
        )

        self.assertGreaterEqual(len(detections), 3)
        self.assertTrue(any(96 <= item.x <= 224 for item in detections))

    def test_textured_violet_terrain_is_not_bounded_water(self) -> None:
        detections = _detect_bounded_cool_water(
            _synthetic_bounded_violet_water_room(textured=True),
            Box(0, 0, 800, 608),
        )

        self.assertEqual(detections, [])

    def test_scan_image_maps_catharsis_gray_water_to_water_2(self) -> None:
        image = _synthetic_catharsis_water_room()

        result = scan_image(
            image,
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )
        water = [det for det in result.detections if det.type_id == OBJ_WATER_2]

        self.assertTrue(any((det.x, det.y) == (128, 96) for det in water))
        self.assertTrue(any((det.x, det.y) == (128, 192) for det in water))

    def test_cyan_tinted_background_columns_are_not_catharsis_water(self) -> None:
        result = scan_image(
            _synthetic_cyan_tinted_catharsis_impostor_room(),
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )

        self.assertFalse(
            any(det.type_id == OBJ_WATER_2 for det in result.detections)
        )

    def test_scan_image_rejects_saturated_blue_blocks_as_water(self) -> None:
        image = _synthetic_blue_block_room()

        result = scan_image(
            image,
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )
        water = [det for det in result.detections if det.type_id == OBJ_WATER_2]

        self.assertEqual(water, [])

    def test_scan_image_rejects_dark_purple_background_as_catharsis_water(self) -> None:
        image = _synthetic_purple_noise_room()

        result = scan_image(
            image,
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )
        water = [det for det in result.detections if det.type_id == OBJ_WATER_2]

        self.assertEqual(water, [])

    def test_render_detection_overlay_marks_source_detections(self) -> None:
        image = _synthetic_room()
        result = scan_image(image, room_box=Box(0, 0, 800, 608), grid_step=16)

        svg = render_detection_overlay(result, Path("synthetic.png"), "Synthetic", show_labels=True)

        self.assertIn("<image href=", svg)
        self.assertIn('class="room"', svg)
        self.assertIn('data-kind="save"', svg)
        self.assertIn('data-type="save"', svg)
        self.assertIn('data-type="warp"', svg)
        self.assertIn("save:save", svg)

    def test_render_detection_overlay_can_mark_truth_matches(self) -> None:
        image = _synthetic_room()
        result = scan_image(image, room_box=Box(0, 0, 800, 608), grid_step=16)
        truth = JMap(
            objects=[
                JMapObject(64, 96, OBJ_SAVE),
                JMapObject(160, 160, OBJ_BLOCK),
                JMapObject(320, 320, OBJ_PLAYER_START),
            ]
        )

        svg = render_detection_overlay(
            result,
            Path("synthetic.png"),
            "Synthetic",
            show_labels=True,
            truth=truth,
            tolerance=8,
        )

        self.assertIn('data-status="matched"', svg)
        self.assertIn('data-status="unmatched"', svg)
        self.assertIn('data-status="missed"', svg)
        self.assertIn("missed:block", svg)
        self.assertNotIn("player_start", svg)


def _synthetic_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 28] * width * height)
    _rect(data, width, 68, 100, 24, 24, (235, 220, 40))
    _rect(data, width, 76, 108, 10, 10, (180, 20, 25))
    _ring(data, width, 336, 208, 14, (65, 20, 210))
    return RGBImage(width, height, bytes(data))


def _synthetic_filled_warp_impostor_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 28] * width * height)
    _rect(data, width, 320, 192, 40, 40, (65, 20, 210))
    _rect(data, width, 337, 209, 6, 6, (20, 20, 25))
    return RGBImage(width, height, bytes(data))


def _synthetic_elongated_warp_impostor_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 28] * width * height)
    purple = (65, 20, 210)
    _rect(data, width, 320, 192, 54, 4, purple)
    _rect(data, width, 320, 228, 54, 4, purple)
    _rect(data, width, 320, 196, 4, 32, purple)
    _rect(data, width, 370, 196, 4, 32, purple)
    return RGBImage(width, height, bytes(data))


def _synthetic_active_save_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 28] * width * height)
    _rect(data, width, 68, 100, 24, 24, (235, 220, 40))
    _rect(data, width, 76, 108, 10, 10, (25, 185, 45))
    return RGBImage(width, height, bytes(data))


def _synthetic_occluded_active_save_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([120, 70, 180] * width * height)
    _rect(data, width, 96, 96, 32, 12, (20, 20, 25))
    _rect(data, width, 104, 98, 12, 6, (225, 225, 225))
    _rect(data, width, 96, 108, 16, 20, (30, 180, 45))
    _rect(data, width, 112, 108, 16, 20, (225, 190, 35))
    return RGBImage(width, height, bytes(data))


def _synthetic_fragmented_cross_save_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 28] * width * height)
    red = (190, 25, 25)
    yellow = (235, 210, 35)
    for x, y in ((100, 108), (119, 108), (100, 120), (119, 120)):
        _rect(data, width, x, y, 10, 7, red)
    _rect(data, width, 112, 108, 5, 19, yellow)
    _rect(data, width, 100, 116, 29, 3, yellow)
    return RGBImage(width, height, bytes(data))


def _synthetic_muted_cross_save_room(
    *, with_header: bool, header_dark_width: int = 20
) -> RGBImage:
    width, height = 800, 608
    data = bytearray([80, 65, 55] * width * height)
    _rect(data, width, 96, 104, 30, 20, (175, 60, 45))
    _rect(data, width, 109, 108, 4, 13, (170, 125, 75))
    _rect(data, width, 102, 113, 18, 4, (170, 125, 75))
    if with_header:
        _rect(data, width, 96, 96, 30, 8, (205, 190, 170))
        _rect(data, width, 101, 98, header_dark_width, 3, (75, 65, 60))
    return RGBImage(width, height, bytes(data))


def _synthetic_low_body_header_save_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([80, 65, 55] * width * height)
    _rect(data, width, 96, 112, 30, 20, (175, 60, 45))
    _rect(data, width, 109, 116, 4, 13, (170, 125, 75))
    _rect(data, width, 102, 121, 18, 4, (170, 125, 75))
    _rect(data, width, 96, 96, 30, 8, (205, 190, 170))
    _rect(data, width, 101, 98, 20, 3, (75, 65, 60))
    return RGBImage(width, height, bytes(data))


def _synthetic_fragmented_header_save_room(*, header_dark_width: int) -> RGBImage:
    width, height = 800, 608
    data = bytearray([80, 65, 55] * width * height)
    red = (175, 60, 45)
    for x, y in ((100, 108), (119, 108), (100, 120), (119, 120)):
        _rect(data, width, x, y, 10, 7, red)
    _rect(data, width, 100, 96, 29, 15, (205, 190, 170))
    _rect(data, width, 104, 98, header_dark_width, 6, (75, 65, 60))
    return RGBImage(width, height, bytes(data))


def _synthetic_repeated_yellow_terrain_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 28] * width * height)
    for row in range(5):
        for column in range(8):
            x = 32 + column * 48
            y = 32 + row * 48
            _rect(data, width, x, y, 24, 24, (235, 205, 35))
            _rect(data, width, x + 8, y + 8, 8, 8, (180, 30, 25))
    return RGBImage(width, height, bytes(data))


def _synthetic_dotkid_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([95, 134, 75] * width * height)
    _ring(data, width, 400, 320, 32, (28, 28, 28))
    _disc(data, width, 400, 320, 2, (190, 45, 35))
    return RGBImage(width, height, bytes(data))


def _synthetic_geometry_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 28] * width * height)
    _rect(data, width, 96, 64, 32, 32, (168, 168, 168))
    _outline_rect(data, width, 96, 64, 32, 32, (12, 12, 12))
    _line(data, width, 176, 64, 160, 95, (225, 225, 225), thickness=2)
    _line(data, width, 176, 64, 191, 95, (225, 225, 225), thickness=2)
    _line(data, width, 160, 95, 191, 95, (225, 225, 225), thickness=2)
    return RGBImage(width, height, bytes(data))


def _synthetic_color_object_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 28] * width * height)
    _rect(data, width, 192, 128, 32, 32, (84, 150, 183))
    _rect(data, width, 224, 128, 32, 32, (84, 150, 183))
    _thin_outline_rect(data, width, 80, 192, 8, 24, (34, 188, 65))
    _disc(data, width, 336, 112, 11, (230, 24, 24))
    return RGBImage(width, height, bytes(data))


def _synthetic_sparse_walljump_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([232, 232, 232] * width * height)
    _rect(data, width, 123, 100, 4, 24, (35, 135, 45))
    # The same side-biased green marks are tile texture, not a vine, when
    # embedded in a pastel-green terrain cell.
    _rect(data, width, 192, 96, 32, 32, (110, 190, 150))
    _rect(data, width, 219, 100, 4, 24, (35, 135, 45))
    return RGBImage(width, height, bytes(data))


def _synthetic_dark_repeated_walljump_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([20, 24, 28] * width * height)
    green = (35, 135, 45)
    _rect(data, width, 123, 100, 4, 24, green)
    _rect(data, width, 123, 132, 4, 24, green)
    # An isolated side-biased green mark is not enough to establish a vine.
    _rect(data, width, 219, 100, 4, 24, green)
    return RGBImage(width, height, bytes(data))


def _synthetic_blue_refresher_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([36, 34, 42] * width * height)
    _disc(data, width, 112, 112, 10, (32, 72, 225))
    return RGBImage(width, height, bytes(data))


def _synthetic_blue_square_texture_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([36, 34, 42] * width * height)
    for x, y in ((96, 96), (192, 144), (320, 224), (496, 384)):
        _rect(data, width, x, y, 20, 20, (32, 72, 225))
    return RGBImage(width, height, bytes(data))


def _synthetic_pale_water_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([240, 240, 240] * width * height)
    _rect(data, width, 96, 96, 32, 32, (160, 220, 254))
    return RGBImage(width, height, bytes(data))


def _synthetic_water_colored_background_room() -> RGBImage:
    width, height = 800, 608
    return RGBImage(width, height, bytes((60, 150, 190)) * width * height)


def _synthetic_winding_water_colored_background_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([115, 70, 45] * width * height)
    cyan = (60, 150, 190)
    _rect(data, width, 0, 160, 160, height - 160, cyan)
    _rect(data, width, 0, 320, 640, 160, cyan)
    _rect(data, width, 480, 160, 160, height - 160, cyan)
    _rect(data, width, 320, 480, width - 320, height - 480, cyan)
    return RGBImage(width, height, bytes(data))


def _synthetic_broad_water_basin_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([30, 30, 42] * width * height)
    _rect(data, width, 0, 192, width, height - 192, (60, 150, 190))
    return RGBImage(width, height, bytes(data))


def _synthetic_gradient_with_bounded_pool() -> RGBImage:
    width, height = 800, 608
    data = bytearray(width * height * 3)
    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * 3
            data[offset] = 80 + x * 70 // width
            data[offset + 1] = 135 + y * 55 // height
            data[offset + 2] = 205 + x * 35 // width
    _rect(data, width, 320, 240, 128, 160, (38, 72, 214))
    return RGBImage(width, height, bytes(data))


def _synthetic_bounded_violet_water_room(*, textured: bool) -> RGBImage:
    width, height = 800, 608
    data = bytearray([174, 198, 220] * width * height)
    _rect(data, width, 96, 96, 160, 96, (78, 100, 242))
    if textured:
        for x in range(96, 257, 16):
            _rect(data, width, x, 96, 2, 96, (8, 16, 38))
        for y in range(96, 193, 16):
            _rect(data, width, 96, y, 160, 2, (8, 16, 38))
    return RGBImage(width, height, bytes(data))


def _synthetic_catharsis_water_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 32] * width * height)
    _rect(data, width, 128, 96, 32, 32, (52, 51, 57))
    _rect(data, width, 128, 128, 32, 32, (108, 108, 113))
    _rect(data, width, 128, 160, 32, 32, (4, 3, 23))
    _rect(data, width, 128, 192, 32, 32, (5, 5, 29))
    return RGBImage(width, height, bytes(data))


def _synthetic_cyan_tinted_catharsis_impostor_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([16, 23, 39] * width * height)
    for x in (288, 416, 544):
        _rect(data, width, x, 96, 64, 320, (64, 78, 94))
    return RGBImage(width, height, bytes(data))


def _synthetic_blue_block_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([198, 180, 222] * width * height)
    _rect(data, width, 96, 96, 32, 32, (100, 177, 252))
    return RGBImage(width, height, bytes(data))


def _synthetic_purple_noise_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([31, 24, 36] * width * height)
    _rect(data, width, 128, 96, 32, 32, (48, 41, 55))
    _rect(data, width, 128, 128, 32, 32, (62, 54, 70))
    _rect(data, width, 160, 128, 32, 32, (46, 39, 54))
    return RGBImage(width, height, bytes(data))


def _rect(
    data: bytearray,
    width: int,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
) -> None:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            offset = (yy * width + xx) * 3
            data[offset : offset + 3] = bytes(color)


def _outline_rect(
    data: bytearray,
    width: int,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
) -> None:
    _rect(data, width, x, y, w, 2, color)
    _rect(data, width, x, y + h - 2, w, 2, color)
    _rect(data, width, x, y, 2, h, color)
    _rect(data, width, x + w - 2, y, 2, h, color)


def _thin_outline_rect(
    data: bytearray,
    width: int,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
) -> None:
    _rect(data, width, x, y, w, 1, color)
    _rect(data, width, x, y + h - 1, w, 1, color)
    _rect(data, width, x, y, 1, h, color)
    _rect(data, width, x + w - 1, y, 1, h, color)


def _line(
    data: bytearray,
    width: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
    thickness: int = 1,
) -> None:
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    x = x0
    y = y0
    while True:
        _rect(data, width, x, y, thickness, thickness, color)
        if x == x1 and y == y1:
            break
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x += sx
        if doubled <= dx:
            error += dx
            y += sy


def _ring(
    data: bytearray,
    width: int,
    cx: int,
    cy: int,
    radius: int,
    color: tuple[int, int, int],
) -> None:
    inner = (radius - 5) ** 2
    outer = radius**2
    for yy in range(cy - radius, cy + radius + 1):
        for xx in range(cx - radius, cx + radius + 1):
            dist = (xx - cx) ** 2 + (yy - cy) ** 2
            if inner <= dist <= outer:
                offset = (yy * width + xx) * 3
                data[offset : offset + 3] = bytes(color)


def _disc(
    data: bytearray,
    width: int,
    cx: int,
    cy: int,
    radius: int,
    color: tuple[int, int, int],
) -> None:
    outer = radius**2
    for yy in range(cy - radius, cy + radius + 1):
        for xx in range(cx - radius, cx + radius + 1):
            dist = (xx - cx) ** 2 + (yy - cy) ** 2
            if dist <= outer:
                offset = (yy * width + xx) * 3
                data[offset : offset + 3] = bytes(color)


if __name__ == "__main__":
    unittest.main()
