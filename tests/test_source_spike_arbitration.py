"""Source-contour arbitration against conflicting terrain hypotheses."""

import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.constants import (
    OBJ_MINI_BLOCK, OBJ_MINI_SPIKE_UP, OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_LEFT, OBJ_MINI_SPIKE_DOWN,
)
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.scanner import (
    Detection,
    _merge_capture_lattice_geometry,
    _prune_profiled_full_spike_noise,
    _prune_source_exterior_block_aliases,
    _reconcile_common_room_geometry,
    _reconcile_source_supported_spike_phases,
)
from jtool_scanner.spike_shape import VERTICES


def scene(direction, *, triangle=True, foreground=30, background=220,
          scale=1, origin=(160, 160)):
    image = Image.new("RGB", (800, 608), (background,) * 3)
    if triangle:
        ImageDraw.Draw(image).polygon(
            [(origin[0] + dx, origin[1] + dy) for dx, dy in VERTICES[direction]],
            fill=(foreground,) * 3,
        )
    if scale != 1:
        image = image.resize(
            (round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR,
        )
    return RGBImage(image.width, image.height, image.tobytes())


class SourceSpikeArbitrationTests(unittest.TestCase):
    def test_triangle_exterior_rejects_intrusive_block_but_keeps_true_occlusion(self):
        for background, terrain, scale in ((30, 220, 1), (220, 30, 1.25)):
            for occluded_block in (False, True):
                with self.subTest(background=background, scale=scale,
                                  occluded_block=occluded_block):
                    bitmap = Image.new("RGB", (800, 608), (background,) * 3)
                    draw = ImageDraw.Draw(bitmap)
                    draw.rectangle((160, 192, 191, 223), fill=(terrain,) * 3)
                    if occluded_block:
                        draw.rectangle((160, 160, 191, 191), fill=(terrain,) * 3)
                    draw.polygon([(160 + dx, 160 + dy)
                                  for dx, dy in VERTICES[3]],
                                 fill=(background if occluded_block else terrain,) * 3)
                    if scale != 1:
                        bitmap = bitmap.resize((round(800 * scale),
                                                round(608 * scale)),
                                               Image.Resampling.BILINEAR)
                    image = RGBImage(bitmap.width, bitmap.height, bitmap.tobytes())
                    room = Box(0, 0, image.width, image.height)
                    intrusive = Detection("block", 1, 160, 160, .8,
                                          Box(160, 160, 32, 32))
                    backing = Detection("block", 1, 160, 192, .8,
                                        Box(160, 192, 32, 32))
                    spike = Detection("spike_up", 3, 160, 160, .8,
                                      Box(160, 160, 32, 32))
                    result = _prune_source_exterior_block_aliases(
                        [intrusive, backing, spike], image, room,
                    )
                    self.assertIn(backing, result)
                    self.assertIn(spike, result)
                    self.assertEqual(intrusive in result, occluded_block)

    def test_true_spike_is_not_moved_to_blank_face_across_polarity_and_scale(self):
        for direction, block in ((3, (168, 160)), (4, (152, 160)),
                                 (5, (168, 160)), (6, (168, 160))):
            for foreground, background, scale in ((30, 220, 1), (220, 30, 1.25)):
                with self.subTest(direction=direction, scale=scale,
                                  foreground=foreground):
                    image = scene(direction, foreground=foreground,
                                  background=background, scale=scale)
                    room = Box(0, 0, image.width, image.height)
                    spike = Detection("spike", direction, 160, 160, .8,
                                      Box(160, 160, 32, 32))
                    terrain = Detection("block", 1, *block, .8,
                                        Box(*block, 32, 32))
                    result = _reconcile_common_room_geometry([spike, terrain], image, room)
                    self.assertIn(spike, result)

    def test_absent_spike_does_not_gain_source_contour_exemption(self):
        image = scene(3, triangle=False)
        room = Box(0, 0, image.width, image.height)
        spike = Detection("spike_up", 3, 160, 160, .8, Box(160, 160, 32, 32))
        terrain = Detection("block", 1, 168, 160, .8, Box(168, 160, 32, 32))
        result = _reconcile_common_room_geometry([spike, terrain], image, room)
        self.assertNotIn(spike, result)

    def test_profile_veto_respects_unambiguous_source_triangle(self):
        for direction in VERTICES:
            for foreground, background, scale in ((30, 220, 1), (220, 30, 1.25)):
                with self.subTest(direction=direction, scale=scale):
                    image = scene(direction, foreground=foreground,
                                  background=background, scale=scale)
                    room = Box(0, 0, image.width, image.height)
                    spike = Detection("spike", direction, 160, 160, .8,
                                      Box(160, 160, 32, 32))
                    with patch("jtool_scanner.scanner._full_spike_noise_profile",
                               return_value="solid_dense"), patch(
                        "jtool_scanner.scanner._is_profiled_full_spike_noise",
                        return_value=True,
                    ):
                        self.assertEqual(
                            [spike], _prune_profiled_full_spike_noise([spike], image, room),
                        )

    def test_profile_veto_still_rejects_texture_free_candidate(self):
        image = scene(3, triangle=False)
        room = Box(0, 0, image.width, image.height)
        spike = Detection("spike_up", 3, 160, 160, .8, Box(160, 160, 32, 32))
        with patch("jtool_scanner.scanner._full_spike_noise_profile",
                   return_value="solid_dense"), patch(
            "jtool_scanner.scanner._is_profiled_full_spike_noise",
            return_value=True,
        ):
            self.assertEqual([], _prune_profiled_full_spike_noise([spike], image, room))

    def test_lattice_merge_does_not_pair_distinct_diagonal_mini_cells(self):
        for type_id in (OBJ_MINI_BLOCK, OBJ_MINI_SPIKE_UP,
                        OBJ_MINI_SPIKE_RIGHT, OBJ_MINI_SPIKE_LEFT,
                        OBJ_MINI_SPIKE_DOWN):
            with self.subTest(type_id=type_id):
                def mini(x, y):
                    return Detection("mini", type_id, x, y, .8,
                                     Box(x, y, 16, 16))

                source = [mini(112, 544), mini(112, 560), mini(112, 576)]
                canonical = [mini(112, 544), mini(112, 560),
                             mini(128, 544), mini(128, 560)]
                merged = _merge_capture_lattice_geometry(
                    source, canonical, radius=24.0,
                )
                positions = {(d.x, d.y) for d in merged}
                self.assertTrue({(112, 544), (112, 560), (112, 576)} <= positions)

    def test_lattice_merge_accepts_overlapping_mini_phase(self):
        source = Detection("mini", OBJ_MINI_BLOCK, 112, 560, .8,
                           Box(112, 560, 16, 16))
        canonical = Detection("mini", OBJ_MINI_BLOCK, 120, 568, .8,
                              Box(120, 568, 16, 16))
        self.assertEqual([canonical], _merge_capture_lattice_geometry(
            [source], [canonical], radius=24.0,
        ))

    def test_lattice_merge_keeps_two_supported_distinct_terrain_cells(self):
        first = Detection("supported_terrain_miniblock", OBJ_MINI_BLOCK,
                          112, 576, .8, Box(112, 576, 16, 16))
        second = Detection("supported_terrain_miniblock", OBJ_MINI_BLOCK,
                           128, 560, .8, Box(128, 560, 16, 16))
        for background, terrain, scale in (
            ((30, 50, 70), (200, 220, 240), 1),
            ((225, 205, 185), (65, 45, 25), 1.25),
            ((5, 15, 25), (100, 110, 120), 1),
        ):
            with self.subTest(background=background, terrain=terrain,
                              scale=scale):
                bitmap = Image.new("RGB", (800, 608), background)
                draw = ImageDraw.Draw(bitmap)
                for x, y in ((112, 576), (128, 560)):
                    for dy in range(0, 16, 4):
                        for dx in range(0, 16, 4):
                            delta = 20 if (dx + dy) % 8 else -20
                            color = tuple(max(0, min(255, value + delta))
                                          for value in terrain)
                            draw.rectangle((x + dx, y + dy, x + dx + 3,
                                            y + dy + 3), fill=color)
                if scale != 1:
                    bitmap = bitmap.resize(
                        (round(800 * scale), round(608 * scale)),
                        Image.Resampling.BILINEAR,
                    )
                image = RGBImage(bitmap.width, bitmap.height, bitmap.tobytes())
                room = Box(0, 0, image.width, image.height)
                merged = _merge_capture_lattice_geometry(
                    [first], [second], radius=24.0,
                    source_image=image, source_room=room,
                )
                self.assertEqual({(112, 576), (128, 560)},
                                 {(item.x, item.y) for item in merged})

    def test_lattice_merge_rejects_different_material_mini_alias(self):
        first = Detection("supported_terrain_miniblock", OBJ_MINI_BLOCK,
                          112, 576, .8, Box(112, 576, 16, 16))
        second = Detection("supported_terrain_miniblock", OBJ_MINI_BLOCK,
                           128, 560, .8, Box(128, 560, 16, 16))
        bitmap = Image.new("RGB", (800, 608), (20, 30, 40))
        draw = ImageDraw.Draw(bitmap)
        for x, y, material in ((112, 576, (10, 190, 20)),
                               (128, 560, (220, 210, 190))):
            for dy in range(0, 16, 4):
                for dx in range(0, 16, 4):
                    delta = 20 if (dx + dy) % 8 else -20
                    draw.rectangle((x + dx, y + dy, x + dx + 3,
                                    y + dy + 3),
                                   fill=tuple(max(0, min(255, value + delta))
                                              for value in material))
        image = RGBImage(bitmap.width, bitmap.height, bitmap.tobytes())
        merged = _merge_capture_lattice_geometry(
            [first], [second], radius=24.0,
            source_image=image, source_room=Box(0, 0, 800, 608),
        )
        self.assertEqual([second], merged)

    def test_lattice_merge_keeps_source_contour_over_blank_canonical_phase(self):
        for direction in VERTICES:
            for foreground, background, scale in (
                (30, 220, 1), (220, 30, 1.25), (70, 170, 1),
            ):
                with self.subTest(direction=direction, scale=scale,
                                  foreground=foreground):
                    image = scene(direction, foreground=foreground,
                                  background=background, scale=scale)
                    room = Box(0, 0, image.width, image.height)
                    source = Detection("source_spike", direction, 160, 160, .8,
                                       Box(160, 160, 32, 32))
                    canonical = Detection("canonical_spike", direction, 160, 144,
                                          .8, Box(160, 144, 32, 32))
                    self.assertEqual([source], _merge_capture_lattice_geometry(
                        [source], [canonical], radius=24.0,
                        source_image=image, source_room=room,
                    ))

    def test_lattice_merge_does_not_preserve_source_without_source_contour(self):
        source = Detection("source_spike", 3, 160, 160, .8,
                           Box(160, 160, 32, 32))
        canonical = Detection("canonical_spike", 3, 160, 144, .8,
                              Box(160, 144, 32, 32))
        for has_canonical_triangle, image in (
            (False, scene(3, triangle=False)),
            (True, scene(3, origin=(160, 144))),
        ):
            with self.subTest(has_canonical_triangle=has_canonical_triangle):
                self.assertEqual([canonical], _merge_capture_lattice_geometry(
                    [source], [canonical], radius=24.0,
                    source_image=image,
                    source_room=Box(0, 0, image.width, image.height),
                ))

    def test_lattice_merge_requires_complete_source_contour_for_phase_override(self):
        image = scene(3, triangle=False)
        room = Box(0, 0, image.width, image.height)
        source = Detection("source_spike", 3, 160, 160, .8,
                           Box(160, 160, 32, 32))
        canonical = Detection("canonical_spike", 3, 160, 144, .8,
                              Box(160, 144, 32, 32))

        def localized_score(x, y, direction):
            if direction == 3 and (x, y) == (160, 160):
                return 11 / 12
            return 0.0

        with patch("jtool_scanner.scanner.SpikeShapeField.localized_score",
                   side_effect=localized_score), patch(
            "jtool_scanner.scanner.SpikeShapeField.contrast",
            return_value=.5,
        ):
            self.assertEqual([canonical], _merge_capture_lattice_geometry(
                [source], [canonical], radius=24.0,
                source_image=image, source_room=room,
            ))

    def test_unique_eight_pixel_phase_refit_requires_source_triangle(self):
        for direction in VERTICES:
            for foreground, background, scale in ((30, 220, 1), (220, 30, 1.25)):
                with self.subTest(direction=direction, scale=scale):
                    image = scene(direction, foreground=foreground,
                                  background=background, scale=scale)
                    room = Box(0, 0, image.width, image.height)
                    stale_x, stale_y = (168, 160) if direction in (3, 6) else (160, 168)
                    stale = Detection("spike", direction, stale_x, stale_y, .8,
                                      Box(stale_x, stale_y, 32, 32))
                    corrected = _reconcile_source_supported_spike_phases(
                        [stale], image, room,
                    )
                    self.assertEqual([(direction, 160, 160)],
                                     [(d.type_id, d.x, d.y) for d in corrected])
                    blank = scene(direction, triangle=False, scale=scale)
                    self.assertEqual([stale], _reconcile_source_supported_spike_phases(
                        [stale], blank, room,
                    ))

    def test_stronger_existing_terrain_face_prevents_source_phase_shift(self):
        # A scaled capture can draw a triangle edge eight pixels below the
        # editor origin. The confirmed backing block protects the old phase.
        image = scene(3, origin=(160, 168))
        room = Box(0, 0, image.width, image.height)
        spike = Detection("spike_up", 3, 160, 160, .8, Box(160, 160, 32, 32))
        block = Detection("block", 1, 160, 192, .8, Box(160, 192, 32, 32))
        self.assertEqual([spike, block], _reconcile_source_supported_spike_phases(
            [spike, block], image, room,
        ))


if __name__ == "__main__":
    unittest.main()
