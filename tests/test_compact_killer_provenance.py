"""Protect source-visible killer cells without counting normalization fill."""
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage


class CompactKillerProvenanceTests(TestCase):
    def test_observed_native_extent_matches_normalization_padding_and_cropping(self):
        for shape, observed in (
            ((19, 13), Box(96, 96, 608, 416)),
            ((20, 12), Box(64, 128, 640, 384)),
            ((30, 22), Box(0, 0, 800, 608)),
        ):
            with self.subTest(source_grid=shape):
                width, height = (38 * v for v in shape)
                image = RGBImage(width, height, bytes((130, 23, 11)) * width * height)
                norm = scanner._normalize_room_to_jtool(image, *shape)
                self.assertEqual(norm.observed_native_box, observed)
                self.assertEqual(norm.image.width, 25 * 38)
                self.assertEqual(norm.image.height, 19 * 38)
                self.assertEqual(norm.source_offset_x, -observed.x * 38 // 32)
                expected_y = 3 * 38 if shape == (30, 22) else -observed.y * 38 // 32
                self.assertEqual(norm.source_offset_y, expected_y)

    def test_synthetic_lethal_fill_never_reaches_compact_spike_quorum(self):
        # This is a normalized working frame: known original pixels inside
        # the logical 19x13 board, and a lethal-coloured synthetic border.
        visible = Box(96, 96, 608, 416)
        native = 96, 96
        red, gray = bytes((175, 50, 48)), bytes((138, 138, 138))
        outer = red * 800
        neutral = red * 96 + gray * 608 + red * 96
        first_cell = red * 128 + gray * 576 + red * 96
        working = RGBImage(
            800, 608, outer * 96 + first_cell * 32 + neutral * 384 + outer * 96,
        )
        normalized_box = Box(0, 0, 800, 608)
        kwargs = dict(adaptive_blocks=[], adaptive_profile=None)
        paths = (
            patch.object(scanner, '_detect_compact_room_spikes', return_value=[]),
            patch.object(scanner, '_detect_compact_room_relative_platforms', return_value=[]),
            patch.object(scanner, '_recover_native_compact_killer_tiles', side_effect=lambda ds, *a: ds),
        )
        with paths[0] as spikes, paths[1], paths[2]:
            before = scanner._replace_compact_room_geometry([], working, normalized_box, **kwargs)
            spikes.assert_not_called()
            after = scanner._replace_compact_room_geometry(
                [], working, normalized_box, observed_killer_cells=visible, **kwargs,
            )
            spikes.assert_called_once()
        before_keys = {(d.x, d.y) for d in before if d.kind == 'killer_block_cross'}
        after_keys = {(d.x, d.y) for d in after if d.kind == 'killer_block_cross'}
        self.assertEqual(len(before_keys), 229)
        self.assertEqual(after_keys, {native})
