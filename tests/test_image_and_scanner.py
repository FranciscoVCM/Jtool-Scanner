from __future__ import annotations

from pathlib import Path
import unittest

from jtool_scanner.constants import OBJ_SAVE, OBJ_WARP
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage, load_png
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


def _synthetic_room() -> RGBImage:
    width, height = 800, 608
    data = bytearray([24, 24, 28] * width * height)
    _rect(data, width, 68, 100, 24, 24, (235, 220, 40))
    _rect(data, width, 76, 108, 10, 10, (180, 20, 25))
    _ring(data, width, 336, 208, 14, (65, 20, 210))
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


if __name__ == "__main__":
    unittest.main()

