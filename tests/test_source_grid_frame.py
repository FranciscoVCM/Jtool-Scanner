"""Portable original/working-coordinate coverage, with no room fixtures."""
from math import floor
from types import SimpleNamespace
from unittest import TestCase

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_contours import SourceContours
from scripts.source_grid_frame import frame_from_existing_grid
from scripts.source_sampling import SourceFrame


def scene(width=608, height=416, origin=(0, 0), grid=(19, 13)):
    raster = Image.new('RGB', (width, height), (20, 40, 70))
    draw = ImageDraw.Draw(raster)
    for x, y in ((64, 64), (128, 96), (192, 160)):
        draw.rectangle((round(x * width / 608), round(y * height / 416),
                        round((x + 31) * width / 608), round((y + 31) * height / 416)), fill=(80, 170, 210))
    ox, oy = origin
    padded = Image.new('RGB', (width + ox + 9, height + oy + 7), (253, 2, 119))
    padded.paste(raster, (ox, oy))
    image = RGBImage(padded.width, padded.height, padded.tobytes())
    room = Box(ox, oy, width, height)
    return image, room, scanner._normalize_room_to_jtool(image.crop(room), *grid)


def altered_padding(normalization, room, color):
    raster = Image.new('RGB', (normalization.image.width, normalization.image.height), color)
    old = Image.frombytes('RGB', (normalization.image.width, normalization.image.height), normalization.image.data)
    left, top = -normalization.source_offset_x, -normalization.source_offset_y
    raster.paste(old.crop((left, top, left + room.width, top + room.height)), (left, top))
    return SimpleNamespace(image=RGBImage(raster.width, raster.height, raster.tobytes()),
        source_offset_x=normalization.source_offset_x, source_offset_y=normalization.source_offset_y)


class SourceGridFrameTests(TestCase):
    def test_centered_padding_is_unknown(self):
        image, room, norm = scene()
        frame = frame_from_existing_grid(image, room, (19, 13), norm)
        self.assertEqual(frame.extent, Box(room.x - 96, room.y - 96, 800, 608))
        self.assertEqual(frame.original_position(96.5, 96.5), (room.x, room.y))
        self.assertIsNone(frame.original_position(95.9, 96.5))
        self.assertIsNone(frame.pixel(95.5, 96.5))
        self.assertTrue(frame.rectangle_available(160, 160, 32, 32, margin=4))
        self.assertFalse(frame.rectangle_available(80, 96, 32, 32, margin=4))

    def test_fractional_mapping_uses_actual_rounded_transform(self):
        for width, height in ((777, 534), (431, 295), (760, 520), (997, 682)):
            image, room, norm = scene(width, height, (11, 7))
            frame = frame_from_existing_grid(image, room, (19, 13), norm)
            for x in (95.9, 96.5, 127.25, 400.5, 703.5, 704.1):
                for y in (95.9, 96.5, 207.25, 400.5, 511.5, 512.1):
                    sx = floor(x * norm.image.width / 800) + room.x + norm.source_offset_x
                    sy = floor(y * norm.image.height / 608) + room.y + norm.source_offset_y
                    expected = (sx, sy) if room.contains(sx, sy) else None
                    self.assertEqual(frame.original_position(x, y), expected)
                    if expected is not None:
                        self.assertEqual(frame.original_pixel(x, y), image.pixel(*expected))

    def test_fractional_source_does_not_have_ideal96_offset(self):
        image, room, norm = scene(777, 534)
        frame = frame_from_existing_grid(image, room, (19, 13), norm)
        self.assertEqual((norm.image.width, norm.image.height), (1023, 780))
        self.assertEqual(frame.extent.x, room.x - 123)
        self.assertNotEqual((room.x - frame.extent.x) * 800 / frame.extent.width, 96.)

    def test_generic_odd_padding_uses_existing_offsets(self):
        for grid in ((20, 12), (18, 11), (9, 9)):
            image, room, norm = scene(731, 489, (13, 5), grid)
            frame = frame_from_existing_grid(image, room, grid, norm)
            self.assertEqual(frame.extent.x, room.x + norm.source_offset_x)
            self.assertEqual(frame.extent.y, room.y + norm.source_offset_y)
            self.assertEqual((frame.extent.width, frame.extent.height), (norm.image.width, norm.image.height))

    def test_wrong_source_or_working_metadata_rejected(self):
        image, room, norm = scene()
        bad = SimpleNamespace(image=norm.image, source_offset_x=norm.source_offset_x + 1,
                              source_offset_y=norm.source_offset_y)
        with self.assertRaisesRegex(ValueError, 'metadata'):
            frame_from_existing_grid(image, room, (19, 13), bad)
        data = bytearray(norm.image.data)
        at = ((-norm.source_offset_y) * norm.image.width - norm.source_offset_x) * 3
        data[at] ^= 255
        bad = SimpleNamespace(image=RGBImage(norm.image.width, norm.image.height, bytes(data)),
            source_offset_x=norm.source_offset_x, source_offset_y=norm.source_offset_y)
        with self.assertRaisesRegex(ValueError, 'original source pixels'):
            frame_from_existing_grid(image, room, (19, 13), bad)

    def test_covered_boundary_samples_do_not_depend_on_padding_color(self):
        for width, height in ((608, 416), (777, 534), (760, 520), (431, 295), (319, 218)):
            image, room, norm = scene(width, height)
            frames = [frame_from_existing_grid(image, room, (19, 13), altered_padding(norm, room, color))
                      for color in ((0, 0, 0), (255, 255, 255))]
            left = (room.x - frames[0].extent.x) * 800 / frames[0].extent.width
            right = (room.right - frames[0].extent.x) * 800 / frames[0].extent.width
            top = (room.y - frames[0].extent.y) * 608 / frames[0].extent.height
            bottom = (room.bottom - frames[0].extent.y) * 608 / frames[0].extent.height
            points = [(boundary + offset / 4, y) for boundary in (left, right) for offset in range(-12, 13)
                      for y in (top + 8.5, 304.5, bottom - 8.5)]
            points += [(x, boundary + offset / 4) for boundary in (top, bottom) for offset in range(-12, 13)
                       for x in (left + 8.5, 400.5, right - 8.5)]
            self.assertTrue(any(frames[0].pixel(x, y) is not None for x, y in points))
            for x, y in points:
                self.assertEqual(frames[0].pixel(x, y), frames[1].pixel(x, y), (width, height, x, y))

    def test_full_grid_entire_view_and_coverage_match_legacy(self):
        image, room, norm = scene(1000, 760, (11, 7), (25, 19))
        current = frame_from_existing_grid(image, room, (25, 19), norm)
        legacy = SourceFrame(image, room)
        self.assertEqual(current.canonical_rgb, legacy.canonical_rgb)
        self.assertEqual(current._covered_x, legacy._covered_x)
        self.assertEqual(current._covered_y, legacy._covered_y)

    def test_contours_match_working_view_only_where_source_covered(self):
        image, room, norm = scene(777, 534)
        frame = frame_from_existing_grid(image, room, (19, 13), norm)
        physical = SourceContours(image, frame.extent, source_frame=frame)
        working = SourceContours(norm.image, Box(0, 0, norm.image.width, norm.image.height))
        for first, second in (((160, 160), (192, 160)), ((192, 160), (192, 192)), ((400, 304), (432, 304))):
            before, after = working.edge(first, second), physical.edge(first, second)
            self.assertEqual((before.support, before.unknown), (after.support, after.unknown))
        self.assertTrue(physical.edge((80, 96), (112, 96)).unknown)

    def test_wrapper_mutation_cannot_change_frozen_evidence(self):
        image, room, norm = scene()
        frame = frame_from_existing_grid(image, room, (19, 13), norm)
        before = frame.pixel(160.5, 160.5)
        image.data = bytes(len(image.data))
        norm.image.data = bytes(len(norm.image.data))
        self.assertFalse(frame.matches_source(image, room))
        self.assertEqual(frame.pixel(160.5, 160.5), before)

    def test_invalid_grid_or_physical_crop_rejected(self):
        image, room, norm = scene()
        for grid in ((0, 13), (True, 13), (19, -1), (19.5, 13), None):
            with self.assertRaises(ValueError):
                frame_from_existing_grid(image, room, grid, norm)
        with self.assertRaises(ValueError):
            frame_from_existing_grid(image, Box(-1, 0, 608, 416), (19, 13), norm)

    def test_downsample_filter_must_not_leak_padding_as_source(self):
        image, room, norm = scene(760, 520)
        views = [altered_padding(norm, room, color) for color in ((0, 0, 0), (255, 255, 255))]
        correct = [frame_from_existing_grid(image, room, (19, 13), view) for view in views]
        naive = [SourceFrame(image, room, extent=frame.extent,
                            canonical=RGBImage(800, 608, frame.canonical_rgb)) for frame in correct]
        self.assertIsNone(correct[0].pixel(96.5, 304.5))
        self.assertIsNone(correct[1].pixel(96.5, 304.5))
        self.assertIsNotNone(naive[0].pixel(96.5, 304.5))
        self.assertNotEqual(naive[0].pixel(96.5, 304.5), naive[1].pixel(96.5, 304.5))

    def test_geometry_box_rounds_before_odd_translation(self):
        image, room, norm = scene(777, 534)
        frame = frame_from_existing_grid(image, room, (19, 13), norm)
        expected = scanner._geometry_detection('probe', 1, 400, 160, .9, norm.image,
            Box(0, 0, norm.image.width, norm.image.height), 32).image_box
        expected = Box(expected.x + room.x + norm.source_offset_x,
                       expected.y + room.y + norm.source_offset_y, expected.width, expected.height)
        self.assertEqual(frame.geometry_box(400, 160, 32), expected)
        self.assertNotEqual(int(round(frame.extent.x + 400 * frame.extent.width / 800)), expected.x)

    def test_oversized_grid_reuses_lower_left_crop(self):
        image, room, norm = scene(960, 768, (11, 7), (30, 24))
        frame = frame_from_existing_grid(image, room, (30, 24), norm)
        self.assertEqual((norm.source_offset_x, norm.source_offset_y), (0, 160))
        self.assertEqual((norm.image.width, norm.image.height), (800, 608))
        self.assertEqual(frame.original_position(.5, .5), (room.x, room.y + 160))
