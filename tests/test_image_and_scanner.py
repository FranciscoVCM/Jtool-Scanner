from __future__ import annotations

from pathlib import Path
import unittest

from jtool_scanner.constants import (
    OBJ_APPLE,
    OBJ_BLOCK,
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
from jtool_scanner.scanner import scan_image


class ImageAndScannerTests(unittest.TestCase):
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

        self.assertTrue(any((det.x, det.y) == (320, 96) for det in apples))
        self.assertTrue(any((det.x, det.y) == (192, 128) for det in water))
        self.assertTrue(any((det.x, det.y) == (64, 192) for det in walljumps))

    def test_scan_image_can_recover_sparse_walljump_marks(self) -> None:
        image = _synthetic_sparse_walljump_room()

        result = scan_image(
            image,
            room_box=Box(0, 0, 800, 608),
            grid_step=8,
            include_color_objects=True,
        )
        walljumps = [det for det in result.detections if det.type_id == OBJ_WALLJUMP_LEFT]

        self.assertTrue(any((det.x, det.y) == (96, 96) for det in walljumps))

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
    return RGBImage(width, height, bytes(data))


def _synthetic_pale_water_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([240, 240, 240] * width * height)
    _rect(data, width, 96, 96, 32, 32, (160, 220, 254))
    return RGBImage(width, height, bytes(data))


def _synthetic_catharsis_water_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 32] * width * height)
    _rect(data, width, 128, 96, 32, 32, (52, 51, 57))
    _rect(data, width, 128, 128, 32, 32, (108, 108, 113))
    _rect(data, width, 128, 160, 32, 32, (4, 3, 23))
    _rect(data, width, 128, 192, 32, 32, (5, 5, 29))
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
