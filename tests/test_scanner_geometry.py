from __future__ import annotations

from collections import Counter
from pathlib import Path
import unittest
from unittest import mock

from jtool_scanner.constants import (
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_GRAVITY_DOWN,
    OBJ_GRAVITY_UP,
    OBJ_JUMP_REFRESHER,
    OBJ_MINI_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_MINI_SPIKE_LEFT,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_UP,
    OBJ_PLATFORM,
    OBJ_SAVE,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
    OBJ_WARP,
    OBJ_WATER_2,
    OBJ_WALLJUMP_LEFT,
    OBJ_WALLJUMP_RIGHT,
)
from jtool_scanner.geometry import Box
from jtool_scanner.scanner import (
    Detection,
    _GeometryClass,
    _GeometryPatchCandidate,
    _ColorProfile,
    _PatchFeatures,
    _PlatformPatchFeatures,
    _TriangleFillFeatures,
    _RepeatedTerrainClusterMorphology,
    _SupportedCellTerrainProfile,
    _accept_block,
    _accept_block_run_gap_patch,
    _accept_full_spike,
    _accept_full_spike_support,
    _accept_mini_spike,
    _accept_repeated_terrain_partner,
    _arbitrate_minispikes_against_blocks,
    _arbitrate_full_spike_scale_duplicates,
    _reconcile_local_spike_scale_conflicts,
    _can_recover_diagonal_side_mini_spike,
    _can_recover_extended_left_mini_spike,
    _is_adjacent_up_mini_spike_candidate,
    _can_recover_axis_supported_mini_spike,
    _can_recover_horizontal_side_mini_spike,
    _dedupe_geometry,
    _dedupe_overlapping_geometry,
    _dedupe_normalized_full_spikes,
    _dense_minispike_lattice_axis,
    _detect_apples,
    _detect_mini_blocks,
    _detect_saves,
    _detect_warps,
    _detect_outline_cloud_warps,
    _detect_outline_warps,
    _is_neutral_outline_warp_color,
    _is_fragmented_outline_apple_patch,
    _component_silhouette_iou,
    _filled_cloud_warp_has_ambiguous_neutral_shadow,
    _filled_cloud_warp_is_dense_spike_enclosure,
    _filled_cloud_warp_shadow_is_background_like,
    _is_filled_cloud_warp_metrics,
    _is_outline_cloud_warp_metrics,
    _looks_like_bright_outlined_terrain_room,
    _looks_like_bright_neutral_outlined_terrain_room,
    _recover_bright_neutral_outline_blocks,
    _prune_bright_outlined_terrain_decorations,
    _expand_supported_cell_terrain_materials,
    _learn_repeated_terrain_profile,
    _learn_supported_cell_terrain_profile,
    _prefer_repeated_terrain_pair_over_single,
    _prune_supported_terrain_spike_body_cells,
    _prune_supported_terrain_marker_body_cells,
    _prune_supported_terrain_spike_recovery_noise,
    _is_sparse_supported_terrain_residual_noise,
    _is_full_width_smooth_water_anchor,
    _is_coherent_water_field_anchor,
    _select_neutral_terrain_cells,
    _repeated_terrain_paired_seed,
    _repeated_terrain_support_is_decisive,
    _repeated_terrain_seed_candidates,
    _repeated_terrain_blocks_form_dense_field,
    _repeated_terrain_mini_decoration_type,
    _replace_repeated_terrain_geometry,
    _supported_detection_overlaps_terrain,
    _supported_terrain_has_dominant_boundary_component,
    _can_recover_nearby_hollow_block,
    _is_block_run_gap,
    _is_bright_outline_platform_candidate,
    _is_bright_filled_full_spike_component,
    _should_reconcile_bright_filled_full_spikes,
    _bright_neutral_triangle_direction,
    _is_textured_platform_candidate,
    _is_textured_platform_horizontally_isolated,
    _is_repeated_terrain_lattice_candidate,
    _is_blocklike_mini_spike_noise_candidate,
    _is_blocklike_full_spike_recovery_candidate,
    _is_blocklike_spike_candidate,
    _is_bottom_edge_up_spike_continuation_anchor,
    _is_bottom_edge_up_spike_continuation_patch,
    _is_center_heavy_block_candidate,
    _is_dark_outline_block_run_fill_patch,
    _is_dark_outline_eight_step_full_spike_candidate,
    _is_dark_outline_full_spike_candidate,
    _is_weak_full_spike_shape_recovery,
    _is_dark_outline_half_step_full_spike_candidate,
    _is_strong_full_spike_shape_candidate,
    _is_strong_offgrid_full_spike_shape,
    _is_weak_full_spike_run_shape,
    _is_weak_two_neighbor_support_noise,
    _has_full_spike_run_anchor,
    _full_spike_run_distance,
    _is_edge_outline_block_patch,
    _is_edge_weak_block_patch,
    _is_final_right_mini_corridor_candidate,
    _is_final_right_mini_stack_candidate,
    _is_final_legacy_mini_spike_noise,
    _is_final_block_noise_candidate,
    _is_strong_yellowless_save_lattice,
    _is_final_miniblock_noise_candidate,
    _is_inverted_boundary_terrain_candidate,
    _is_haloed_red_warp_patch,
    HALOED_RED_WARP_MIN_COMPONENT_FILL,
    _is_dark_silhouette_warp_metrics,
    _is_distinctive_singleton_gravity_pair,
    _looks_like_block_texture_minispike_lattice,
    _is_pastel_walljump_impostor_color,
    _is_miniblock_room_mini_spike_candidate,
    _dense_axis_component_overlap_ids,
    _prune_final_walljump_noise,
    _prune_orphan_gravity_flippers,
    _is_edge_full_spike_continuation_anchor,
    _is_edge_full_spike_continuation_patch,
    _is_full_spike_run_gap_patch,
    _is_half_step_supported_full_spike_candidate,
    _has_axis_mini_spike_support,
    _has_axis_left_mini_step_support,
    _has_adjacent_up_mini_spike_pair,
    _has_ambiguous_adjacent_up_mini_spike_pair,
    _has_dense_adjacent_up_mini_spike_support,
    _has_dark_outline_axial_support,
    _has_diagonal_side_mini_spike_support,
    _has_diagonal_right_mini_step_support,
    _has_extended_left_mini_spike_support,
    _has_final_right_mini_corridor_support,
    _has_final_right_mini_stack_support,
    _has_horizontal_side_mini_spike_support,
    _has_low_contrast_mini_up_pair,
    _has_mixed_cluster_up_mini_spike_support,
    _has_border_supported_up_mini_spike_support,
    _has_diagonal_anchor_up_mini_spike_support,
    _has_left_spike_supports,
    _has_low_contrast_paired_up_mini_spike_pair,
    _has_low_contrast_paired_up_mini_spike_support,
    _has_low_border_side_mini_spike_support,
    detect_room_box,
    _has_ultra_faint_left_mini_spike_support,
    _has_four_quadrant_block_support,
    _is_low_contrast_mini_up_candidate,
    _is_directly_full_scale_dominant,
    _is_low_contrast_platform_candidate,
    _has_complete_low_contrast_platform_context,
    _has_bright_room_platform_bar_evidence,
    _platform_conflicts_supported_terrain,
    _looks_miniblock_dominant,
    _is_ambiguous_adjacent_up_mini_spike_candidate,
    _is_border_supported_up_mini_spike_candidate,
    _is_dense_adjacent_up_mini_spike_candidate,
    _is_diagonal_anchor_up_mini_spike_candidate,
    _is_low_contrast_paired_up_mini_spike_candidate,
    _detect_embedded_room_profile,
    _is_low_border_side_mini_spike_candidate,
    _is_low_border_side_mini_spike_patch,
    _is_mixed_cluster_up_mini_spike_candidate,
    _is_ultra_faint_left_mini_spike_candidate,
    _is_low_signal_supported_full_spike_candidate,
    _should_use_bright_neutral_spike_components,
    _should_use_oversized_bright_neutral_spike_components,
    _looks_like_detached_top_ui_band,
    _is_residual_mini_spike_noise_candidate,
    _is_profiled_full_spike_noise,
    _has_repeated_horizontal_edge_bands,
    _apple_contour_metrics,
    _detect_apples,
    _is_water_tinted_apple_patch,
    _is_outline_apple_component,
    _is_pale_outline_apple_room,
    _is_weak_room_corner_apple,
    _prune_apples_overlapping_killers,
    _is_supported_full_spike_candidate,
    _is_up_spike_full_step_continuation_patch,
    _is_up_spike_half_step_continuation_patch,
    _has_full_spike_perpendicular_neighbor,
    _has_compact_vertical_mini_support,
    _count_full_spike_perpendicular_neighbors,
    _is_ambiguous_right_full_spike_noise,
    _is_ambiguous_full_spike_noise,
    _is_block_heavy_full_spike_support_noise,
    _is_grid_shape_full_spike_candidate,
    _is_half_grid_full_spike_candidate,
    _is_nearby_half_grid_full_spike_candidate,
    _is_block_heavy_full_spike_candidate,
    _is_boundary_full_spike_candidate,
    _is_isolated_coherent_full_spike_candidate,
    _is_informative_raw_support_density,
    _is_low_texture_raw_support_candidate,
    _is_raw_primary_full_spike_candidate,
    _is_strong_ambiguous_raw_support_candidate,
    _is_supported_shape_full_spike_candidate,
    _is_low_signal_supported_full_spike_recovery,
    _is_low_value_primary_full_spike_geometry,
    _normalize_full_spike_origin,
    _infer_source_grid,
    _normalize_room_to_jtool,
    _forms_full_spike_orientation_junction,
    _full_spike_body_miniblock_overlap,
    _normalize_full_spike_detections,
    _outline_block_score,
    _patch_in_ranges,
    _prune_adaptive_block_noise,
    _prune_adaptive_weak_block_noise,
    _prune_isolated_weak_block_noise,
    _prune_dark_outline_low_signal_blocks,
    _prune_full_spike_shape_noise,
    _prune_isolated_weak_full_spike_noise,
    _prune_isolated_weak_full_spike_shape_noise,
    _prune_primary_isolated_full_spikes,
    _prune_sparse_off_grid_block_noise,
    _recover_dark_outline_supported_low_signal_blocks,
    _recover_dark_outline_long_low_signal_runs,
    _prune_duplicate_mini_spike_cells,
    _prune_recovered_full_spike_noise,
    _recover_full_spike_run_gaps,
    _recover_pruned_full_spikes,
    _recover_blocklike_full_spikes,
    _recover_axis_supported_mini_spikes,
    _recover_supported_block_cells,
    _recover_up_spike_lateral_continuations,
    _prune_miniblock_room_primary_full_spike_noise,
    _triangle_masks,
    _triangle_side_coverage,
    _value_in_range,
    _ColorProfile,
    scan_png,
)
from jtool_scanner.image import load_png
from jtool_scanner.jmap import JMap
from jtool_scanner.image import RGBImage


class ScannerGeometryTests(unittest.TestCase):
    def test_embedded_room_profile_requires_repeated_centered_grid(self) -> None:
        width, height = 640, 480
        data = bytearray([40, 40, 40] * width * height)
        left, top, tile = 140, 60, 40
        for grid_y in range(9):
            for grid_x in range(9):
                color = (120, 120, 120) if (grid_x + grid_y) % 2 else (80, 80, 80)
                for y in range(top + grid_y * tile + 2, top + (grid_y + 1) * tile - 2):
                    for x in range(left + grid_x * tile + 2, left + (grid_x + 1) * tile - 2):
                        offset = (y * width + x) * 3
                        data[offset : offset + 3] = bytes(color)
        image = RGBImage(width, height, bytes(data))

        profile = _detect_embedded_room_profile(image, Box(0, 0, width, height))

        self.assertIsNotNone(profile)
        room, source_grid = profile
        self.assertEqual(source_grid, (9, 9))
        self.assertTrue(130 <= room.x <= 150)
        self.assertTrue(50 <= room.y <= 70)
        self.assertTrue(340 <= room.width <= 370)
        self.assertTrue(340 <= room.height <= 370)

        ftfa = load_png(
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "regressions"
            / "unseen-rooms"
            / "ftfa"
            / "screen-1-source.png"
        )
        self.assertIsNone(
            _detect_embedded_room_profile(ftfa, detect_room_box(ftfa))
        )

    def test_repeated_horizontal_edge_bands_are_texture_not_spike_shape(self) -> None:
        width, height = 800, 608
        data = bytearray([24, 140, 140] * width * height)
        for y in range(208, 304):
            color = (220, 100, 100) if (y // 4) % 2 else (120, 70, 70)
            for x in range(528, 624):
                offset = (y * width + x) * 3
                data[offset : offset + 3] = bytes(color)
        image = RGBImage(width, height, bytes(data))

        self.assertTrue(
            _has_repeated_horizontal_edge_bands(
                image,
                Box(0, 0, width, height),
                560,
                224,
            )
        )
        self.assertFalse(
            _has_repeated_horizontal_edge_bands(
                image,
                Box(0, 0, width, height),
                320,
                64,
            )
        )

    def test_repeated_terrain_profile_is_palette_independent(self) -> None:
        expected = {
            (x, y)
            for y in (64, 96, 128)
            for x in (0, 32, 64, 96)
        }
        detections = _repeated_terrain_support_detections()
        first = _learn_repeated_terrain_profile(
            _repeated_terrain_test_image(
                background=(212, 72, 164),
                terrain=(18, 86, 205),
            ),
            Box(0, 0, 800, 608),
            detections,
        )
        second = _learn_repeated_terrain_profile(
            _repeated_terrain_test_image(
                background=(20, 175, 92),
                terrain=(228, 190, 24),
            ),
            Box(0, 0, 800, 608),
            detections,
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        assert first is not None
        assert second is not None
        self.assertEqual(first.full_blocks, expected)
        self.assertEqual(second.full_blocks, expected)

    def test_supported_cell_terrain_uses_save_and_spike_back_polarity(self) -> None:
        room = Box(0, 0, 800, 608)
        image_box = Box(0, 0, 1, 1)
        detections = [
            Detection("save_outline", OBJ_SAVE, 0, 32, 0.9, image_box),
            *[
                Detection("spike_up", OBJ_SPIKE_UP, x, 32, 0.8, image_box)
                for x in (0, 32, 64, 96, 128)
            ],
        ]

        profile = _learn_supported_cell_terrain_profile(
            _supported_cell_terrain_test_image(),
            room,
            detections,
        )

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(len(profile.blocks), 18)
        self.assertEqual(profile.mini_blocks, frozenset())
        self.assertEqual(profile.back_votes, 5)
        self.assertEqual(profile.tip_votes, 0)
        self.assertEqual(profile.direct_supports, 2)

    def test_supported_cell_terrain_rejects_dominant_boundary_gradient(self) -> None:
        boundary_band = frozenset(
            {(0, y) for y in range(0, 608, 32)}
            | {(x, 0) for x in range(32, 800, 32)}
            | {(x, 576) for x in range(32, 608, 32)}
        )
        fragmented_terrain = frozenset(
            {(x, 0) for x in range(0, 5 * 32, 32)}
            | {(x, 576) for x in range(10 * 32, 15 * 32, 32)}
            | {(x, 10 * 32) for x in range(18 * 32, 23 * 32, 32)}
        )

        self.assertTrue(
            _supported_terrain_has_dominant_boundary_component(boundary_band)
        )
        self.assertFalse(
            _supported_terrain_has_dominant_boundary_component(fragmented_terrain)
        )

    def test_inverted_boundary_terrain_requires_spike_polarity(self) -> None:
        boundary_mass = frozenset(
            (x, y)
            for y in range(0, 7 * 32, 32)
            for x in range(0, 800, 32)
        )
        profile = _ColorProfile(106.0, 78.0, 64.0, 0.16)

        self.assertTrue(
            _is_inverted_boundary_terrain_candidate(
                profile,
                boundary_mass,
                total_cells=25 * 19,
                back_votes=2,
                tip_votes=0,
                other_tip_votes=9,
            )
        )
        self.assertFalse(
            _is_inverted_boundary_terrain_candidate(
                profile,
                boundary_mass,
                total_cells=25 * 19,
                back_votes=1,
                tip_votes=1,
                other_tip_votes=9,
            )
        )

    def test_inverted_boundary_terrain_rejects_dark_starfield(self) -> None:
        boundary_mass = frozenset(
            (x, y)
            for y in range(0, 7 * 32, 32)
            for x in range(0, 800, 32)
        )

        self.assertFalse(
            _is_inverted_boundary_terrain_candidate(
                _ColorProfile(2.0, 3.5, 6.5, 0.02),
                boundary_mass,
                total_cells=25 * 19,
                back_votes=3,
                tip_votes=0,
                other_tip_votes=23,
            )
        )

    def test_muted_green_fill_is_not_sparse_vine_palette(self) -> None:
        self.assertTrue(_is_pastel_walljump_impostor_color(103, 131, 76))
        self.assertFalse(_is_pastel_walljump_impostor_color(15, 170, 35))

    def test_horizontal_minis_embedded_in_block_lattice_are_tile_texture(self) -> None:
        blocks = [
            Detection("block", OBJ_BLOCK, x, y, 0.8, Box(x, y, 32, 32))
            for y in range(0, 128, 32)
            for x in range(0, 800, 32)
        ]
        minis = [
            Detection(
                "mini_spike_left",
                OBJ_MINI_SPIKE_LEFT,
                block.x,
                block.y,
                0.6,
                Box(block.x, block.y, 16, 16),
            )
            for block in blocks
        ]

        self.assertTrue(
            _looks_like_block_texture_minispike_lattice(
                blocks,
                minis,
                frozenset((OBJ_MINI_SPIKE_LEFT, OBJ_MINI_SPIKE_RIGHT)),
            )
        )
        self.assertFalse(
            _looks_like_block_texture_minispike_lattice(
                blocks,
                minis,
                frozenset((OBJ_MINI_SPIKE_UP, OBJ_MINI_SPIKE_DOWN)),
            )
        )

    def test_haloed_red_warp_requires_outer_ring_and_light_center(self) -> None:
        halo = _PatchFeatures(tuple(), 0.32, 0.214, 0.375)
        apple = _PatchFeatures(tuple(), 0.36, 0.062, 0.578)

        self.assertTrue(_is_haloed_red_warp_patch(halo))
        self.assertFalse(_is_haloed_red_warp_patch(apple))

    def test_haloed_red_warp_component_fill_rejects_terrain_fragments(self) -> None:
        self.assertGreaterEqual(HALOED_RED_WARP_MIN_COMPONENT_FILL, 0.60)
        self.assertLess(HALOED_RED_WARP_MIN_COMPONENT_FILL, 0.708)

    def test_dark_silhouette_warp_requires_isolated_solid_portal_topology(self) -> None:
        portal_patch = _PatchFeatures((), 0.410, 0.491, 0.047)

        self.assertTrue(
            _is_dark_silhouette_warp_metrics(
                map_width=26.0,
                map_height=25.9,
                fill=0.729,
                contrast=186.5,
                ring_dark_share=0.110,
                patch=portal_patch,
                row_multi=0.125,
                column_multi=0.125,
                run_sum=2.250,
                center_fill=1.0,
            )
        )
        self.assertFalse(
            _is_dark_silhouette_warp_metrics(
                map_width=31.0,
                map_height=31.7,
                fill=0.788,
                contrast=93.9,
                ring_dark_share=0.05,
                patch=_PatchFeatures((), 0.40, 0.45, 0.05),
                row_multi=0.923,
                column_multi=0.921,
                run_sum=6.079,
                center_fill=1.0,
            )
        )

    def test_singleton_gravity_pair_requires_two_strong_arrows_and_edge_anchor(self) -> None:
        box = Box(0, 0, 32, 32)
        edge_up = Detection("gravity_up", OBJ_GRAVITY_UP, 64, 576, 0.656, box)
        down = Detection("gravity_down", OBJ_GRAVITY_DOWN, 224, 64, 0.716, box)
        interior_up = Detection("gravity_up", OBJ_GRAVITY_UP, 64, 544, 0.656, box)

        self.assertTrue(_is_distinctive_singleton_gravity_pair(edge_up, down))
        self.assertFalse(_is_distinctive_singleton_gravity_pair(interior_up, down))

    def test_supported_cell_terrain_joins_connected_distant_materials(self) -> None:
        seed_blocks = frozenset(
            (x, y)
            for y in (64, 96, 128, 160)
            for x in (0, 32, 64, 96)
        )
        expected = frozenset(
            (x, y)
            for y in (64, 96, 128, 160)
            for x in range(0, 256, 32)
        )

        expanded = _expand_supported_cell_terrain_materials(
            _multi_material_supported_terrain_test_image(),
            Box(0, 0, 800, 608),
            [],
            seed_blocks,
        )

        self.assertEqual(expanded.blocks, expected)
        self.assertEqual(
            expanded.mini_blocks,
            frozenset((256, y) for y in range(64, 192, 16)),
        )

    def test_supported_terrain_rejects_sparse_residual_texture_overrun(self) -> None:
        profile = _SupportedCellTerrainProfile(
            blocks=frozenset({(0, 0), (32, 0), (0, 32)}),
            mini_blocks=frozenset({(96, 0), (144, 0), (192, 32), (240, 64)}),
            seed_cluster=0,
            back_votes=8,
            tip_votes=2,
            direct_supports=2,
        )
        raw_blocks = [
            Detection("block", OBJ_BLOCK, x, y, 0.8, Box(0, 0, 1, 1))
            for x, y in (
                (0, 0),
                (32, 0),
                (0, 32),
                (32, 32),
                (64, 0),
                (64, 32),
            )
        ]
        self.assertTrue(
            _is_sparse_supported_terrain_residual_noise(profile, raw_blocks)
        )
        profile_with_connected_residual = _SupportedCellTerrainProfile(
            blocks=profile.blocks,
            mini_blocks=frozenset(
                (x, y)
                for y in range(0, 48, 16)
                for x in (96, 112)
            ),
            seed_cluster=profile.seed_cluster,
            back_votes=profile.back_votes,
            tip_votes=profile.tip_votes,
            direct_supports=profile.direct_supports,
        )
        self.assertFalse(
            _is_sparse_supported_terrain_residual_noise(
                profile_with_connected_residual,
                raw_blocks,
            )
        )

    def test_supported_cell_terrain_does_not_join_disconnected_decoration(self) -> None:
        seed_blocks = frozenset(
            (x, y)
            for y in (64, 96, 128, 160)
            for x in (0, 32, 64, 96)
        )

        expanded = _expand_supported_cell_terrain_materials(
            _multi_material_supported_terrain_test_image(
                include_disconnected_decoration=True,
            ),
            Box(0, 0, 800, 608),
            [],
            seed_blocks,
        )

        self.assertFalse(
            any(
                x >= 512 and y >= 384
                for x, y in (*expanded.blocks, *expanded.mini_blocks)
            )
        )

    def test_supported_cell_terrain_uses_centered_apple_extent(self) -> None:
        apple = Detection("apple", OBJ_APPLE, 688, 272, 0.9, Box(0, 0, 1, 1))

        self.assertFalse(
            _supported_detection_overlaps_terrain(
                apple,
                frozenset({(704, 256)}),
                frozenset(),
            )
        )
        self.assertTrue(
            _supported_detection_overlaps_terrain(
                apple,
                frozenset({(672, 256)}),
                frozenset(),
            )
        )

    def test_supported_cell_terrain_reclassifies_narrow_spike_backed_water_material(self) -> None:
        seed_blocks = frozenset(
            (x, y)
            for y in (64, 96, 128, 160)
            for x in (0, 32, 64, 96)
        )
        image_box = Box(0, 0, 1, 1)
        detections = [
            Detection("water_2", OBJ_WATER_2, 288, y, 0.8, image_box)
            for y in (64, 96, 128)
        ]
        detections.append(
            Detection("spike_left", OBJ_SPIKE_LEFT, 256, 96, 0.8, image_box)
        )

        expansion = _expand_supported_cell_terrain_materials(
            _water_backed_miniblock_material_test_image(),
            Box(0, 0, 800, 608),
            detections,
            seed_blocks,
        )

        self.assertEqual(
            expansion.mini_blocks,
            frozenset((288, y) for y in range(64, 192, 16)),
        )

    def test_supported_cell_terrain_preserves_unbacked_narrow_water(self) -> None:
        seed_blocks = frozenset(
            (x, y)
            for y in (64, 96, 128, 160)
            for x in (0, 32, 64, 96)
        )
        image_box = Box(0, 0, 1, 1)
        detections = [
            Detection("water_2", OBJ_WATER_2, 288, y, 0.8, image_box)
            for y in (64, 96, 128)
        ]

        expansion = _expand_supported_cell_terrain_materials(
            _water_backed_miniblock_material_test_image(),
            Box(0, 0, 800, 608),
            detections,
            seed_blocks,
        )

        self.assertEqual(expansion.mini_blocks, frozenset())

    def test_supported_cell_terrain_water_anchor_distinguishes_full_width_water(self) -> None:
        image_box = Box(0, 0, 1, 1)
        narrow = Detection("water_2", OBJ_WATER_2, 288, 64, 0.8, image_box)
        full_width = Detection("water_2", OBJ_WATER_2, 288, 64, 0.8, image_box)

        self.assertFalse(
            _is_full_width_smooth_water_anchor(
                narrow,
                _water_backed_miniblock_material_test_image(),
                Box(0, 0, 800, 608),
            )
        )
        self.assertTrue(
            _is_full_width_smooth_water_anchor(
                full_width,
                _water_backed_miniblock_material_test_image(water_width=32),
                Box(0, 0, 800, 608),
            )
        )

    def test_supported_cell_terrain_water_field_anchor_requires_two_full_halves(self) -> None:
        image_box = Box(0, 0, 1, 1)
        isolated = Detection("water_2", OBJ_WATER_2, 288, 64, 0.8, image_box)
        neighbors = [
            Detection("water_2", OBJ_WATER_2, 288, y, 0.8, image_box)
            for y in (64, 96, 128)
        ]

        self.assertFalse(
            _is_coherent_water_field_anchor(
                isolated,
                [isolated],
                _water_backed_miniblock_material_test_image(water_width=16),
                Box(0, 0, 800, 608),
            )
        )
        self.assertTrue(
            _is_coherent_water_field_anchor(
                neighbors[1],
                neighbors,
                _coherent_water_field_material_test_image(),
                Box(0, 0, 800, 608),
            )
        )

    def test_supported_cell_terrain_prunes_only_matching_strong_spike_cells(self) -> None:
        image = _up_spike_test_image([(64, 64), (128, 64)])
        detections = [
            Detection(
                "spike_up",
                OBJ_SPIKE_UP,
                64,
                64,
                0.9,
                Box(64, 64, 32, 32),
            ),
            Detection(
                "spike_down",
                OBJ_SPIKE_DOWN,
                128,
                64,
                0.9,
                Box(128, 64, 32, 32),
            ),
        ]

        self.assertEqual(
            _prune_supported_terrain_spike_body_cells(
                frozenset({(64, 64), (128, 64)}),
                detections,
                image,
                Box(0, 0, 800, 608),
            ),
            frozenset({(128, 64)}),
        )

    def test_supported_cell_terrain_prunes_repeated_and_overlapping_recoveries(self) -> None:
        image_box = Box(0, 0, 32, 32)
        repeated = [
            Detection(
                "full_spike_raw_support_recovery",
                OBJ_SPIKE_RIGHT,
                64 + index % 2 * 8,
                index * 32,
                0.35,
                image_box,
            )
            for index in range(5)
        ]
        stronger = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            304,
            192,
            0.65,
            image_box,
        )
        overlapping = Detection(
            "full_spike_shape_recovery",
            OBJ_SPIKE_LEFT,
            312,
            192,
            0.40,
            image_box,
        )
        isolated = Detection(
            "full_spike_raw_support_recovery",
            OBJ_SPIKE_DOWN,
            512,
            384,
            0.38,
            image_box,
        )

        result = _prune_supported_terrain_spike_recovery_noise(
            [*repeated, stronger, overlapping, isolated]
        )

        self.assertEqual(result, [stronger, isolated])

    def test_supported_cell_terrain_prunes_decisive_marker_cells(self) -> None:
        image = _textured_test_image()
        strong_save = Detection(
            "save_fragmented_cross",
            OBJ_SAVE,
            64,
            64,
            0.92,
            Box(64, 64, 32, 32),
        )
        weak_save = Detection(
            "save",
            OBJ_SAVE,
            128,
            64,
            0.70,
            Box(128, 64, 32, 32),
        )
        platform = Detection(
            "platform",
            OBJ_PLATFORM,
            192,
            64,
            0.80,
            Box(192, 64, 32, 16),
        )
        with mock.patch(
            "jtool_scanner.scanner._is_textured_platform_detection",
            return_value=True,
        ):
            result = _prune_supported_terrain_marker_body_cells(
                frozenset({(64, 64), (128, 64), (192, 64)}),
                [strong_save, weak_save, platform],
                image,
                Box(0, 0, 800, 608),
            )

        self.assertEqual(result, frozenset({(128, 64)}))

    def test_yellowless_save_requires_dense_quadrants_and_dark_center(self) -> None:
        boxes = (
            Box(16, 24, 10, 6),
            Box(34, 24, 10, 6),
            Box(16, 36, 10, 6),
            Box(34, 36, 10, 6),
        )
        union = Box(16, 24, 28, 18)

        self.assertTrue(
            _is_strong_yellowless_save_lattice(
                _yellowless_save_lattice_test_image(dark_center=True),
                boxes,
                union,
                1.0,
                1.0,
            )
        )
        self.assertFalse(
            _is_strong_yellowless_save_lattice(
                _yellowless_save_lattice_test_image(dark_center=False),
                boxes,
                union,
                1.0,
                1.0,
            )
        )

    def test_yellowless_save_accepts_bounded_center_palette_variation(self) -> None:
        boxes = (
            Box(16, 24, 10, 6),
            Box(34, 24, 10, 6),
            Box(16, 36, 10, 6),
            Box(34, 36, 10, 6),
        )
        union = Box(16, 24, 28, 18)
        image = _yellowless_save_lattice_test_image(dark_center=True)
        data = bytearray(image.data)
        for y in range(29, 36):
            start = (y * 64 + 27) * 3
            data[start : start + 7 * 3] = bytes((130, 130, 130) * 7)
        for y in range(29, 31):
            start = (y * 64 + 27) * 3
            data[start : start + 7 * 3] = bytes((86, 86, 86) * 7)
        self.assertTrue(
            _is_strong_yellowless_save_lattice(
                RGBImage(64, 64, bytes(data)),
                boxes,
                union,
                1.0,
                1.0,
            )
        )

    def test_repeated_terrain_replaces_only_low_coverage_results(self) -> None:
        image = _repeated_terrain_test_image()
        room = Box(0, 0, 800, 608)
        supports = _repeated_terrain_support_detections()

        replaced, applied = _replace_repeated_terrain_geometry(
            supports,
            image,
            room,
        )
        self.assertTrue(applied)
        self.assertEqual(
            sum(detection.type_id == OBJ_BLOCK for detection in replaced),
            12,
        )

        existing = [
            Detection("block", OBJ_BLOCK, x, y, 0.7, room)
            for y in (64, 96, 128)
            for x in (0, 32, 64, 96)
        ][:10]
        unchanged, applied = _replace_repeated_terrain_geometry(
            supports + existing,
            image,
            room,
        )
        self.assertFalse(applied)
        self.assertEqual(unchanged, supports + existing)

    def test_repeated_terrain_removes_texture_minispikes_inside_learned_blocks(self) -> None:
        image = _repeated_terrain_test_image()
        room = Box(0, 0, 800, 608)
        image_box = Box(0, 0, 1, 1)
        false_texture = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            16,
            64,
            0.7,
            image_box,
        )
        outside_terrain = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            128,
            64,
            0.7,
            image_box,
        )

        replaced, applied = _replace_repeated_terrain_geometry(
            _repeated_terrain_support_detections()
            + [false_texture, outside_terrain],
            image,
            room,
        )

        self.assertTrue(applied)
        self.assertNotIn(false_texture, replaced)
        self.assertIn(outside_terrain, replaced)

    def test_repeated_terrain_morphology_accepts_sparse_tile_lattices(self) -> None:
        for morphology in (
            _RepeatedTerrainClusterMorphology(709, 709 / 1900, 0.937, 0.055),
            _RepeatedTerrainClusterMorphology(699, 699 / 1900, 0.950, 0.039),
            _RepeatedTerrainClusterMorphology(48, 0.025, 1.0, 0.50),
            # A moderately connected room-wide material can still be a
            # gameplay lattice rather than a smooth background field.  This
            # shape is representative of the Say-family solid tiles.
            _RepeatedTerrainClusterMorphology(769, 769 / 1900, 0.889, 0.326),
        ):
            with self.subTest(morphology=morphology):
                self.assertTrue(_is_repeated_terrain_lattice_candidate(morphology))

    def test_repeated_terrain_morphology_rejects_incomplete_or_roomwide_fields(self) -> None:
        for morphology in (
            _RepeatedTerrainClusterMorphology(241, 241 / 1900, 0.647, 0.043),
            _RepeatedTerrainClusterMorphology(856, 856 / 1900, 0.850, 0.697),
            _RepeatedTerrainClusterMorphology(652, 652 / 1900, 1.0, 0.515),
        ):
            with self.subTest(morphology=morphology):
                self.assertFalse(_is_repeated_terrain_lattice_candidate(morphology))

    def test_repeated_terrain_seed_prefers_texture_but_allows_smooth_only_room(self) -> None:
        self.assertEqual(
            _repeated_terrain_seed_candidates(
                {1, 5},
                {1: 0.0283, 5: 0.0018},
            ),
            {1},
        )
        self.assertEqual(
            _repeated_terrain_seed_candidates(
                {2, 4},
                {2: 0.003, 4: 0.004},
            ),
            {2, 4},
        )

    def test_repeated_terrain_paired_seed_recovers_split_material(self) -> None:
        labels = {
            (x, y): 2
            for y in range(0, 608, 16)
            for x in range(0, 800, 16)
        }
        for block_x in range(0, 12 * 32, 32):
            labels[(block_x, 64)] = 0
            labels[(block_x + 16, 64)] = 1
            labels[(block_x, 80)] = 1
            labels[(block_x + 16, 80)] = 0

        result = _repeated_terrain_paired_seed(
            labels=labels,
            centers=[
                _ColorProfile(31, 28, 118, 0.35),
                _ColorProfile(44, 39, 142, 0.38),
                _ColorProfile(205, 180, 235, 0.15),
            ],
            votes=Counter({0: 24, 1: 22, 2: 33}),
            edge_densities={0: 0.03, 1: 0.025, 2: 0.002},
            room_contrast=216,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.clusters, frozenset({0, 1}))
        self.assertEqual(result.support_votes, 46)

    def test_repeated_terrain_paired_seed_allows_unsupported_tonal_half(self) -> None:
        labels = {
            (x, y): 2
            for y in range(0, 608, 16)
            for x in range(0, 800, 16)
        }
        for block_x in range(0, 12 * 32, 32):
            labels[(block_x, 64)] = 0
            labels[(block_x + 16, 64)] = 1
            labels[(block_x, 80)] = 1
            labels[(block_x + 16, 80)] = 0

        result = _repeated_terrain_paired_seed(
            labels=labels,
            centers=[
                _ColorProfile(31, 28, 118, 0.35),
                _ColorProfile(44, 39, 142, 0.38),
                _ColorProfile(205, 180, 235, 0.15),
            ],
            votes=Counter({0: 10, 2: 14}),
            edge_densities={0: 0.04, 1: 0.026, 2: 0.01},
            room_contrast=216,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.clusters, frozenset({0, 1}))
        self.assertEqual(result.support_votes, 10)
        self.assertTrue(
            _prefer_repeated_terrain_pair_over_single(
                pair=result,
                single_votes=13,
                single_morphology=_RepeatedTerrainClusterMorphology(
                    769,
                    769 / 1900,
                    0.889,
                    0.326,
                ),
                single_edge_density=0.0104,
            )
        )

    def test_repeated_terrain_paired_seed_rejects_dense_colour_field(self) -> None:
        labels = {
            (x, y): 2
            for y in range(0, 608, 16)
            for x in range(0, 800, 16)
        }
        for block_y in range(0, 7 * 32, 32):
            for block_x in range(0, 12 * 32, 32):
                labels[(block_x, block_y)] = 0
                labels[(block_x + 16, block_y)] = 1
                labels[(block_x, block_y + 16)] = 1
                labels[(block_x + 16, block_y + 16)] = 0

        result = _repeated_terrain_paired_seed(
            labels=labels,
            centers=[
                _ColorProfile(31, 28, 118, 0.35),
                _ColorProfile(44, 39, 142, 0.38),
                _ColorProfile(205, 180, 235, 0.15),
            ],
            votes=Counter({0: 24, 1: 22, 2: 33}),
            edge_densities={0: 0.03, 1: 0.025, 2: 0.002},
            room_contrast=216,
        )

        self.assertIsNone(result)

    def test_repeated_terrain_final_topology_rejects_dense_colour_field(self) -> None:
        dense_field = frozenset(
            (x * 32, y * 32)
            for y in range(7)
            for x in range(12)
            if (x, y) not in {(0, 0), (11, 6)}
        )
        sparse_corridor = frozenset(
            {(x * 32, 0) for x in range(12)}
            | {(0, y * 32) for y in range(1, 7)}
            | {(11 * 32, y * 32) for y in range(1, 7)}
        )

        self.assertTrue(_repeated_terrain_blocks_form_dense_field(dense_field))
        self.assertFalse(_repeated_terrain_blocks_form_dense_field(sparse_corridor))

    def test_repeated_terrain_partner_rejects_dominant_smooth_background(self) -> None:
        self.assertFalse(
            _accept_repeated_terrain_partner(
                cooccurrences=45,
                occurrence_ratio=0.40,
                row_count=8,
                column_count=18,
                candidate_cells=856,
                family_cells=241,
                total_cells=1900,
                candidate_edge=0.0032,
                family_edge=0.043,
            )
        )
        self.assertTrue(
            _accept_repeated_terrain_partner(
                cooccurrences=68,
                occurrence_ratio=0.72,
                row_count=8,
                column_count=12,
                candidate_cells=287,
                family_cells=374,
                total_cells=1900,
                candidate_edge=0.002,
                family_edge=0.04,
            )
        )
        self.assertFalse(
            _accept_repeated_terrain_partner(
                cooccurrences=68,
                occurrence_ratio=0.72,
                row_count=8,
                column_count=12,
                candidate_cells=287,
                family_cells=1100,
                total_cells=1900,
                candidate_edge=0.02,
                family_edge=0.04,
            )
        )

    def test_block_overlap_arbitration_rejects_decorative_minispike(self) -> None:
        image_box = Box(0, 0, 1, 1)
        block = Detection("block", OBJ_BLOCK, 32, 32, 0.74, image_box)
        decorative_mini = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            48,
            40,
            0.68,
            image_box,
        )

        result = _arbitrate_minispikes_against_blocks([block, decorative_mini])

        self.assertEqual(result, [block])

    def test_block_overlap_arbitration_keeps_decisive_minispike(self) -> None:
        image_box = Box(0, 0, 1, 1)
        weak_block = Detection("block", OBJ_BLOCK, 32, 32, 0.40, image_box)
        true_mini = Detection(
            "mini_spike_down",
            OBJ_MINI_SPIKE_DOWN,
            40,
            48,
            0.76,
            image_box,
        )
        outside_block = Detection("block", OBJ_BLOCK, 96, 96, 0.90, image_box)

        result = _arbitrate_minispikes_against_blocks(
            [weak_block, true_mini, outside_block]
        )

        self.assertEqual(result, [true_mini, outside_block])

    def test_repeated_terrain_mini_motif_prunes_same_direction_residuals(self) -> None:
        image_box = Box(0, 0, 1, 1)
        blocks = [
            Detection("block", OBJ_BLOCK, index * 32, 32, 0.80, image_box)
            for index in range(20)
        ]
        covered = [
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                block.x + 16,
                block.y,
                0.65,
                image_box,
            )
            for block in blocks
        ]
        residual = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            32,
            160,
            0.65,
            image_box,
        )
        real_other_direction = Detection(
            "mini_spike_up",
            OBJ_MINI_SPIKE_UP,
            96,
            160,
            0.80,
            image_box,
        )

        result = _arbitrate_minispikes_against_blocks(
            [*blocks, *covered, residual, real_other_direction]
        )

        self.assertNotIn(residual, result)
        self.assertIn(real_other_direction, result)

    def test_refresher_arbitration_removes_orphan_gravity_flippers(self) -> None:
        box = Box(0, 0, 1, 1)
        detections = [
            Detection("gravity_up", OBJ_GRAVITY_UP, 32, 32, 0.9, box),
            Detection("gravity_up", OBJ_GRAVITY_UP, 64, 32, 0.9, box),
            Detection("gravity_down", OBJ_GRAVITY_DOWN, 32, 64, 0.9, box),
            Detection(
                "jump_refresher_blue",
                OBJ_JUMP_REFRESHER,
                64,
                64,
                0.9,
                box,
            ),
        ]

        remaining = _prune_orphan_gravity_flippers(detections)

        self.assertEqual(
            [detection.type_id for detection in remaining],
            [OBJ_JUMP_REFRESHER],
        )

    def test_final_block_noise_candidate_uses_general_patch_structure(self) -> None:
        self.assertTrue(
            _is_final_block_noise_candidate(
                0.50, 0.10, 0.15, 0.05, 0.12, 30.0, 5.0, 1
            )
        )

    def test_opposite_walljump_conflicts_require_tight_axis_overlap(self) -> None:
        left = Detection(
            "walljump_left",
            OBJ_WALLJUMP_LEFT,
            408,
            576,
            0.48,
            Box(0, 0, 1, 1),
        )
        right = Detection(
            "walljump_right",
            OBJ_WALLJUMP_RIGHT,
            432,
            552,
            0.52,
            Box(0, 0, 1, 1),
        )
        self.assertEqual(_prune_final_walljump_noise([left, right]), [left, right])
        self.assertFalse(
            _is_final_block_noise_candidate(
                0.50, 0.30, 0.30, 0.25, 0.35, 10.0, 5.0, 1
            )
        )

    def test_final_miniblock_noise_keeps_structural_recoveries(self) -> None:
        self.assertTrue(_is_final_miniblock_noise_candidate("mini_block", 101.0))
        self.assertFalse(
            _is_final_miniblock_noise_candidate(
                "mini_block_walljump_backing",
                150.0,
            )
        )

    def test_dense_axis_overlap_uses_minimum_32px_cover(self) -> None:
        detections = [
            Detection("water_3", OBJ_WATER_2, 320, y, 1.0, Box(0, 0, 1, 1))
            for y in (288, 304, 320, 336)
        ]
        removed = _dense_axis_component_overlap_ids(detections, True)
        self.assertEqual(
            {detection.y for detection in detections if id(detection) in removed},
            {304},
        )

    def test_final_legacy_mini_spike_noise_requires_isolation(self) -> None:
        self.assertTrue(_is_final_legacy_mini_spike_noise(0.50, 0.60, 0))
        self.assertFalse(_is_final_legacy_mini_spike_noise(0.50, 0.60, 1))
        self.assertFalse(_is_final_legacy_mini_spike_noise(0.35, 0.60, 0))

    def test_miniblock_room_mini_spike_accepts_filled_triangle_core(self) -> None:
        self.assertTrue(
            _is_miniblock_room_mini_spike_candidate(
                OBJ_MINI_SPIKE_UP,
                0.50,
                0.0,
                0.875,
                0.50,
                0.25,
                0.25,
                0.25,
                0.25,
                0.25,
                80.0,
                0.80,
                0.50,
                20.0,
                0,
                0,
                0,
                0,
            )
        )

    def test_miniblock_room_mini_spike_rejects_unstructured_noise(self) -> None:
        self.assertFalse(
            _is_miniblock_room_mini_spike_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.50,
                -0.20,
                0.25,
                0.75,
                0.27,
                0.25,
                0.25,
                0.40,
                0.30,
                80.0,
                0.35,
                0.05,
                5.0,
                4,
                0,
                0,
                2,
            )
        )

    def test_low_value_primary_full_spike_requires_compound_defect(self) -> None:
        self.assertTrue(
            _is_low_value_primary_full_spike_geometry(
                OBJ_SPIKE_UP,
                0.58,
                0.875,
                1.0,
                0.10,
                0.40,
                0.52,
                False,
            )
        )
        self.assertFalse(
            _is_low_value_primary_full_spike_geometry(
                OBJ_SPIKE_UP,
                0.72,
                1.0,
                0.50,
                0.18,
                0.35,
                0.32,
                False,
            )
        )

    def test_full_spike_body_miniblock_overlap_rotates_with_orientation(self) -> None:
        positions = {(32, 48), (48, 48), (96, 64), (96, 80)}

        self.assertEqual(
            _full_spike_body_miniblock_overlap(OBJ_SPIKE_UP, 32, 48, positions),
            2,
        )
        self.assertEqual(
            _full_spike_body_miniblock_overlap(OBJ_SPIKE_RIGHT, 96, 64, positions),
            2,
        )
        self.assertEqual(
            _full_spike_body_miniblock_overlap(OBJ_SPIKE_DOWN, 96, 64, positions),
            1,
        )

    def test_miniblock_room_gate_rejects_dense_32px_quarter_cell_topology(self) -> None:
        thin_rows = {
            (x, y)
            for y in range(0, 608, 32)
            for x in range(0, 800, 16)
        }
        dense_cells = {
            (x, y)
            for y in range(0, 160, 16)
            for x in range(0, 640, 16)
        }

        self.assertTrue(_looks_miniblock_dominant(thin_rows))
        self.assertFalse(_looks_miniblock_dominant(dense_cells))

    def test_bright_outlined_terrain_gate_uses_sparse_room_local_contrast(self) -> None:
        width, height = 800, 608
        data = bytearray(bytes((240, 240, 240)) * width * height)

        def paint_cells(cell_count: int) -> RGBImage:
            painted = bytearray(data)
            positions = [
                (x, y)
                for y in range(0, height, 32)
                for x in range(0, width, 32)
            ][:cell_count]
            for x, y in positions:
                for py in range(y, y + 32):
                    for px in range(x, x + 32):
                        offset = (py * width + px) * 3
                        painted[offset : offset + 3] = bytes((120, 80, 90))
            return RGBImage(width, height, bytes(painted))

        sparse = paint_cells(60)
        dense = paint_cells(171)

        self.assertTrue(
            _looks_like_bright_outlined_terrain_room(
                sparse,
                Box(0, 0, width, height),
            )
        )
        self.assertFalse(
            _looks_like_bright_outlined_terrain_room(
                dense,
                Box(0, 0, width, height),
            )
        )

        kept = _prune_bright_outlined_terrain_decorations(
            [
                Detection("block", OBJ_BLOCK, 0, 0, 0.8, Box(0, 0, 32, 32)),
                Detection(
                    "mini_block",
                    OBJ_MINI_BLOCK,
                    16,
                    16,
                    0.8,
                    Box(16, 16, 16, 16),
                ),
                Detection(
                    "mini_spike_up",
                    OBJ_MINI_SPIKE_UP,
                    32,
                    0,
                    0.8,
                    Box(32, 0, 16, 16),
                ),
            ]
        )
        self.assertEqual([d.type_id for d in kept], [OBJ_BLOCK])

    def test_bright_neutral_outline_gate_rejects_irkara89_quarter_cells(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "irkara-89-game.png")
        room = detect_room_box(image)

        self.assertTrue(_looks_like_bright_outlined_terrain_room(image, room))
        self.assertEqual(_detect_mini_blocks(image, room), [])

        colored = load_png(fixture_dir / "irkara-nr-flames-game.png")
        self.assertFalse(
            _looks_like_bright_outlined_terrain_room(
                colored,
                detect_room_box(colored),
            )
        )

    def test_bright_neutral_outline_block_recovery_uses_square_morphology(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "irkara-89-game.png")
        room = detect_room_box(image)
        anchors = [
            *_detect_saves(image, room, 8),
            *_detect_warps(image, room, 8),
        ]

        candidates = _recover_bright_neutral_outline_blocks(image, room, anchors)
        truth = JMap.from_file(fixture_dir / "irkara-89.jmap").objects_of_type(OBJ_BLOCK)
        matched = sum(
            any(
                (candidate.x - expected.x) ** 2
                + (candidate.y - expected.y) ** 2
                <= 24**2
                for candidate in candidates
            )
            for expected in truth
        )

        self.assertTrue(_looks_like_bright_neutral_outlined_terrain_room(image, room))
        self.assertGreaterEqual(len(candidates), 60)
        self.assertGreaterEqual(matched, 60)
        self.assertTrue(
            all(
                (candidate.x - warp.x) ** 2 + (candidate.y - warp.y) ** 2 > 32**2
                for candidate in candidates
                for warp in anchors
                if warp.type_id == OBJ_WARP
            )
        )

        ftfa = load_png(
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "regressions"
            / "unseen-rooms"
            / "ftfa"
            / "screen-2-source.png"
        )
        self.assertFalse(
            _looks_like_bright_neutral_outlined_terrain_room(
                ftfa,
                detect_room_box(ftfa),
            )
        )

    def test_bright_chromatic_platform_gate_rejects_single_terrain_edge(self) -> None:
        self.assertFalse(
            _has_bright_room_platform_bar_evidence([0] * 13 + [30, 30])
        )
        self.assertFalse(
            _has_bright_room_platform_bar_evidence(
                [24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            )
        )
        self.assertTrue(
            _has_bright_room_platform_bar_evidence(
                [0] * 11 + [24, 25, 26, 0]
            )
        )
        self.assertTrue(
            _has_bright_room_platform_bar_evidence(
                [25, 25] + [0] * 12 + [25]
            )
        )

    def test_cn3_miniblocks_match_all_truth_inside_excellent_detection_band(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "cn3-16-game.png")
        truth = JMap.from_file(fixture_dir / "cn3-16.jmap")

        detections = _detect_mini_blocks(image, Box(0, 0, image.width, image.height))
        detected_positions = {(detection.x, detection.y) for detection in detections}
        truth_positions = {
            (obj.x, obj.y)
            for obj in truth.objects
            if obj.type_id == OBJ_MINI_BLOCK
        }

        self.assertEqual(len(truth_positions), 501)
        self.assertTrue(truth_positions <= detected_positions)
        self.assertGreaterEqual(len(detections), 550)
        self.assertLessEqual(len(detections), 625)

    def test_cn3_18_miniblocks_retain_high_recall_with_strong_seams(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "cn3-18-game.png")
        truth = JMap.from_file(fixture_dir / "cn3-18.jmap")

        detections = _detect_mini_blocks(image, detect_room_box(image))
        detected_positions = {(detection.x, detection.y) for detection in detections}
        truth_positions = {
            (obj.x, obj.y)
            for obj in truth.objects
            if obj.type_id == OBJ_MINI_BLOCK
        }
        matched = truth_positions & detected_positions

        self.assertGreaterEqual(len(matched) / len(truth_positions), 0.95)

    def test_miniblock_room_gate_uses_directional_side_coverage(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "cn3-16-game.png")
        room = Box(0, 0, image.width, image.height)
        mini_blocks = _detect_mini_blocks(image, room)
        marker_box = Box(0, 0, 32, 32)
        candidates = mini_blocks + [
            Detection("mini_spike_up", OBJ_MINI_SPIKE_UP, 64, 64, 0.50, marker_box),
            Detection("mini_spike_up", OBJ_MINI_SPIKE_UP, 96, 64, 0.50, marker_box),
            Detection("mini_spike_up", OBJ_MINI_SPIKE_UP, 128, 64, 0.50, marker_box),
            Detection("mini_spike_up", OBJ_MINI_SPIKE_UP, 160, 64, 0.50, marker_box),
            Detection("spike_right", OBJ_SPIKE_RIGHT, 224, 480, 0.60, marker_box),
            Detection("spike_right", OBJ_SPIKE_RIGHT, 512, 32, 0.34, marker_box),
            Detection("spike_up", OBJ_SPIKE_UP, 368, 64, 0.63, marker_box),
            Detection("spike_up", OBJ_SPIKE_UP, 512, 128, 0.42, marker_box),
        ]

        kept = _prune_miniblock_room_primary_full_spike_noise(
            candidates,
            image,
            room,
        )

        self.assertEqual(
            {
                (detection.kind, detection.x, detection.y)
                for detection in kept
                if detection.type_id in {OBJ_SPIKE_RIGHT, OBJ_SPIKE_UP}
            },
            {
                ("spike_right", 224, 480),
                ("spike_up", 368, 64),
            },
        )

    def test_f189_full_block_room_is_not_misclassified_as_miniblocks(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "f189-game.png")

        detections = _detect_mini_blocks(image, detect_room_box(image))

        self.assertEqual(detections, [])

    def test_neutral_terrain_profile_rejects_noisy_background_cluster(self) -> None:
        terrain = _ColorProfile(70.0, 66.0, 80.0, 0.055)
        background = _ColorProfile(86.0, 86.0, 87.0, 0.004)
        cells = [
            (0, 0, terrain, 0.060, 1.0),
            (16, 0, terrain, 0.055, 1.0),
            (0, 16, terrain, 0.058, 1.0),
            (16, 16, background, 0.012, 1.0),
            (32, 16, background, 0.010, 1.0),
        ]

        self.assertEqual(
            _select_neutral_terrain_cells(cells),
            {(0, 0), (16, 0), (0, 16)},
        )

    def test_nang_compact_block_room_is_not_misclassified_as_miniblocks(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "nang128-game.png")

        detections = _detect_mini_blocks(image, detect_room_box(image))

        self.assertEqual(detections, [])

    def test_compact_vertical_minis_use_their_native_support_cell_phase(self) -> None:
        fixture_dir = (
            Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        )
        result = scan_png(
            fixture_dir / "nang128-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        blocks = {
            (detection.x, detection.y)
            for detection in result.detections
            if detection.type_id == OBJ_BLOCK
        }
        vertical_minis = [
            detection
            for detection in result.detections
            if detection.type_id in {OBJ_MINI_SPIKE_UP, OBJ_MINI_SPIKE_DOWN}
        ]

        self.assertTrue(vertical_minis)
        self.assertTrue(
            all(
                _has_compact_vertical_mini_support(detection, blocks)
                for detection in vertical_minis
            )
        )
        self.assertEqual(len(vertical_minis), 9)

    def test_nested_outline_warps_recover_all_tracked_nang_variants(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        expected = {
            "nang128-game.png": {(384, 176)},
            "nang135-game.png": {(624, 144)},
            "nang138-game.png": {(192, 240)},
        }

        for filename, positions in expected.items():
            with self.subTest(filename=filename):
                source = load_png(fixture_dir / filename)
                room = detect_room_box(source)
                source_grid = _infer_source_grid(room)
                self.assertEqual(source_grid, (19, 13))
                image = _normalize_room_to_jtool(
                    source.crop(room),
                    *source_grid,
                ).image
                normalized_room = Box(0, 0, image.width, image.height)

                detections = _detect_outline_warps(
                    image,
                    normalized_room,
                    8,
                )

                self.assertEqual(
                    {
                        (detection.x, detection.y)
                        for detection in detections
                        if detection.type_id == OBJ_WARP
                    },
                    positions,
                )

    def test_neutral_outline_warp_seed_is_palette_bounded(self) -> None:
        self.assertTrue(_is_neutral_outline_warp_color(140, 141, 139))
        self.assertFalse(_is_neutral_outline_warp_color(80, 81, 80))
        self.assertFalse(_is_neutral_outline_warp_color(140, 124, 118))

    def test_irkara_colored_warps_do_not_gain_outline_duplicates(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "irkara"

        for floor in ("57", "58"):
            with self.subTest(floor=floor):
                image = load_png(fixture_dir / f"irkara-{floor}-game.png")
                room = detect_room_box(image)

                self.assertEqual(_detect_outline_warps(image, room, 8), [])

    def test_colored_warp_ring_tolerates_mild_center_fill(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "irkara-nr-flames-game.png")
        detections = _detect_warps(image, detect_room_box(image), 8)

        self.assertEqual(
            {(detection.x, detection.y) for detection in detections},
            {(32, 24), (752, 528)},
        )

    def test_full_spike_rejects_blocklike_weak_outline_candidate(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.50)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.535,
            direction_margin=0.12,
            outline_delta=0.22,
        )

        self.assertFalse(_accept_full_spike(spike, block))

    def test_full_spike_accepts_clear_outline_candidate(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.50)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.535,
            direction_margin=0.12,
            outline_delta=0.30,
        )

        self.assertTrue(_accept_full_spike(spike, block))

    def test_off_grid_full_spike_support_requires_substantial_directional_shape(self) -> None:
        accepted = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.36, 0.08, 0.14)
        weak_score = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.29, 0.08, 0.14)
        weak_margin = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.36, 0.03, 0.14)
        weak_outline = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.36, 0.08, 0.09)

        self.assertTrue(_accept_full_spike_support(accepted))
        self.assertFalse(_accept_full_spike_support(weak_score))
        self.assertFalse(_accept_full_spike_support(weak_margin))
        self.assertFalse(_accept_full_spike_support(weak_outline))

    def test_full_spike_support_markers_are_not_emitted_at_final_boundary(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        support = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            72,
            104,
            0.70,
            Box(72, 104, 32, 32),
        )
        regular = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            64,
            96,
            0.80,
            Box(64, 96, 32, 32),
        )

        result = _prune_full_spike_shape_noise(
            [support, regular],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertEqual(result, [regular])

    def test_isolated_weak_full_spike_noise_requires_same_direction_neighbor(self) -> None:
        isolated = Detection("spike_up", OBJ_SPIKE_UP, 64, 64, 0.24, Box(64, 64, 32, 32))
        supported = Detection("spike_up", OBJ_SPIKE_UP, 96, 64, 0.24, Box(96, 64, 32, 32))
        second_supported = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            32,
            64,
            0.24,
            Box(32, 64, 32, 32),
        )
        other_direction = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            64,
            96,
            0.24,
            Box(64, 96, 32, 32),
        )

        result = _prune_isolated_weak_full_spike_noise(
            [isolated, supported, second_supported, other_direction]
        )

        self.assertIn(isolated, result)
        self.assertNotIn(supported, result)
        self.assertNotIn(
            isolated,
            _prune_isolated_weak_full_spike_noise([isolated, other_direction]),
        )
        diagonal_neighbor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            80,
            80,
            0.24,
            Box(80, 80, 32, 32),
        )
        self.assertNotIn(
            isolated,
            _prune_isolated_weak_full_spike_noise([isolated, diagonal_neighbor]),
        )
        self.assertNotIn(
            isolated,
            _prune_isolated_weak_full_spike_noise([isolated, supported]),
        )
        stronger_isolated = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            64,
            64,
            0.27,
            Box(64, 64, 32, 32),
        )
        self.assertIn(
            stronger_isolated,
            _prune_isolated_weak_full_spike_noise([stronger_isolated, supported]),
        )

    def test_weak_full_spike_shape_recovery_requires_coherent_triangle(self) -> None:
        image = _textured_test_image()
        room = Box(0, 0, 800, 608)
        weak = Detection("spike_up", OBJ_SPIKE_UP, 64, 64, 0.25, Box(64, 64, 32, 32))

        self.assertFalse(_is_weak_full_spike_shape_recovery(weak, image, room))
        self.assertFalse(
            _is_weak_full_spike_shape_recovery(
                Detection("full_spike_support", OBJ_SPIKE_UP, 64, 64, 0.25, Box(64, 64, 32, 32)),
                image,
                room,
            )
        )

    def test_strong_full_spike_shape_requires_margin_over_block_texture(self) -> None:
        spike = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.60, 0.12, 0.24)
        block = _GeometryClass("block", OBJ_BLOCK, 0.45)
        patch = _PatchFeatures((), edge_density=0.30, border_score=0.20, center_score=0.40)

        self.assertTrue(_is_strong_full_spike_shape_candidate(spike, block, patch, 0.80))
        self.assertFalse(
            _is_strong_full_spike_shape_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.55),
                patch,
                0.80,
            )
        )

    def test_strong_offgrid_full_spike_shape_rejects_block_heavy_patch(self) -> None:
        spike = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45, 0.10, 0.16)
        patch = _PatchFeatures((), edge_density=0.24, border_score=0.20, center_score=0.30)

        self.assertTrue(
            _is_strong_offgrid_full_spike_shape(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.40),
                patch,
                0.75,
            )
        )
        self.assertFalse(
            _is_strong_offgrid_full_spike_shape(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.56),
                patch,
                0.75,
            )
        )

    def test_weak_full_spike_run_shape_keeps_only_supported_texture(self) -> None:
        spike = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.30, 0.05, 0.16)
        patch = _PatchFeatures((), edge_density=0.26, border_score=0.18, center_score=0.25)

        self.assertTrue(
            _is_weak_full_spike_run_shape(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.35),
                patch,
                0.70,
            )
        )
        self.assertFalse(
            _is_weak_full_spike_run_shape(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.45),
                patch,
                0.70,
            )
        )

    def test_weak_two_neighbor_support_noise_requires_block_heavy_ambiguity(self) -> None:
        image = _textured_test_image()
        support = Detection("full_spike_support", OBJ_SPIKE_UP, 64, 64, 0.40, Box(64, 64, 32, 32))
        self.assertFalse(
            _is_weak_two_neighbor_support_noise(support, image, Box(0, 0, 800, 608), 1)
        )

    def test_weak_full_spike_run_anchor_uses_perpendicular_axis(self) -> None:
        anchor = Detection("spike_up", OBJ_SPIKE_UP, 112, 64, 0.40, Box(112, 64, 32, 32))
        self.assertTrue(_has_full_spike_run_anchor(OBJ_SPIKE_UP, 64, 64, anchor))
        self.assertEqual(_full_spike_run_distance(OBJ_SPIKE_UP, 64, 64, anchor), 48)
        self.assertFalse(_has_full_spike_run_anchor(OBJ_SPIKE_UP, 64, 80, anchor))

    def test_full_spike_support_requires_perpendicular_same_direction_run(self) -> None:
        up_a = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            64,
            0.30,
            Box(64, 64, 32, 32),
        )
        up_b = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            112,
            64,
            0.30,
            Box(112, 64, 32, 32),
        )
        up_axis_neighbor = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            112,
            0.30,
            Box(64, 112, 32, 32),
        )
        down = Detection(
            "full_spike_support",
            OBJ_SPIKE_DOWN,
            64,
            64,
            0.30,
            Box(64, 64, 32, 32),
        )

        self.assertTrue(_has_full_spike_perpendicular_neighbor(up_a, [up_a, up_b]))
        self.assertEqual(
            _count_full_spike_perpendicular_neighbors(up_a, [up_a, up_b]),
            1,
        )
        self.assertFalse(
            _has_full_spike_perpendicular_neighbor(up_a, [up_a, up_axis_neighbor])
        )
        self.assertFalse(_has_full_spike_perpendicular_neighbor(up_a, [up_a, down]))

    def test_pruned_full_spike_recovery_uses_offset_tolerant_run_support(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        room = Box(0, 0, 800, 608)
        candidate = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            64,
            0.35,
            Box(64, 64, 32, 32),
        )
        anchor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            160,
            72,
            0.70,
            Box(160, 72, 32, 32),
        )
        patch = _PatchFeatures((), edge_density=0.24, border_score=0.20, center_score=0.35)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.40,
            direction_margin=0.08,
            outline_delta=0.20,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.30),
            ),
            mock.patch("jtool_scanner.scanner._triangle_side_coverage", return_value=0.50),
        ):
            result = _recover_pruned_full_spikes(
                [candidate, anchor],
                [anchor],
                image,
                room,
            )

        self.assertIn(candidate, result)
        self.assertIn(anchor, result)

    def test_pruned_full_spike_recovery_rejects_unsupported_weak_candidate(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        room = Box(0, 0, 800, 608)
        candidate = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            64,
            0.35,
            Box(64, 64, 32, 32),
        )
        patch = _PatchFeatures((), edge_density=0.24, border_score=0.20, center_score=0.35)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.40,
            direction_margin=0.05,
            outline_delta=0.12,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.30),
            ),
            mock.patch("jtool_scanner.scanner._triangle_side_coverage", return_value=0.50),
        ):
            result = _recover_pruned_full_spikes(
                [candidate],
                [],
                image,
                room,
            )

        self.assertNotIn(candidate, result)

    def test_ambiguous_full_spike_noise_uses_score_and_orientation_gates(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        room = Box(0, 0, 800, 608)
        patch = _PatchFeatures((), edge_density=0.35, border_score=0.20, center_score=0.35)
        weak_ambiguous = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            64,
            64,
            0.40,
            Box(64, 64, 32, 32),
        )
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.40,
            direction_margin=0.05,
            outline_delta=0.20,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
        ):
            self.assertTrue(_is_ambiguous_full_spike_noise(weak_ambiguous, image, room))
            self.assertFalse(
                _is_ambiguous_full_spike_noise(
                    Detection(
                        "spike_up",
                        OBJ_SPIKE_UP,
                        64,
                        64,
                        0.50,
                        Box(64, 64, 32, 32),
                    ),
                    image,
                    room,
                )
            )
            self.assertFalse(
                _is_ambiguous_full_spike_noise(
                    Detection(
                        "spike_down",
                        OBJ_SPIKE_DOWN,
                        64,
                        64,
                        0.40,
                        Box(64, 64, 32, 32),
                    ),
                    image,
                    room,
                )
            )

    def test_final_support_noise_requires_block_dominance_and_weak_orientation(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        room = Box(0, 0, 800, 608)
        support = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            64,
            0.50,
            Box(64, 64, 32, 32),
        )
        patch = _PatchFeatures((), edge_density=0.40, border_score=0.20, center_score=0.35)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.45,
            direction_margin=0.10,
            outline_delta=0.20,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.50),
            ),
        ):
            self.assertTrue(_is_block_heavy_full_spike_support_noise(support, image, room))

        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.40),
            ),
        ):
            self.assertFalse(_is_block_heavy_full_spike_support_noise(support, image, room))

        weak_margin_spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.45,
            direction_margin=0.12,
            outline_delta=0.20,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=weak_margin_spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.50),
            ),
        ):
            self.assertFalse(_is_block_heavy_full_spike_support_noise(support, image, room))

    def test_low_signal_supported_recovery_requires_provenance_and_run_support(self) -> None:
        supported = Detection(
            "full_spike_supported",
            OBJ_SPIKE_UP,
            64,
            64,
            0.24,
            Box(64, 64, 32, 32),
        )
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.30,
            direction_margin=0.02,
            outline_delta=0.10,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.40)
        patch = _PatchFeatures((), edge_density=0.16, border_score=0.20, center_score=0.35)

        self.assertTrue(
            _is_low_signal_supported_full_spike_recovery(
                supported,
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_recovery(
                supported,
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=False,
            )
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_recovery(
                Detection(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    64,
                    64,
                    0.24,
                    Box(64, 64, 32, 32),
                ),
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_recovery(
                supported,
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.21,
                    direction_margin=0.02,
                    outline_delta=0.10,
                ),
                block,
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )

    def test_grid_shape_recovery_requires_run_and_triangle_shape(self) -> None:
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.22,
            direction_margin=0.06,
            outline_delta=0.12,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.20)
        patch = _PatchFeatures((), edge_density=0.18, border_score=0.20, center_score=0.35)

        self.assertTrue(
            _is_grid_shape_full_spike_candidate(
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_grid_shape_full_spike_candidate(
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=False,
            )
        )
        self.assertFalse(
            _is_grid_shape_full_spike_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.23),
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )

    def test_half_grid_recovery_requires_stronger_shape_and_run_support(self) -> None:
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.31,
            direction_margin=0.17,
            outline_delta=0.26,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.20)
        patch = _PatchFeatures((), edge_density=0.13, border_score=0.20, center_score=0.35)
        self.assertTrue(
            _is_half_grid_full_spike_candidate(
                spike,
                block,
                patch,
                side_coverage=0.51,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_half_grid_full_spike_candidate(
                spike,
                block,
                patch,
                side_coverage=0.51,
                run_supported=False,
            )
        )
        self.assertTrue(
            _is_nearby_half_grid_full_spike_candidate(
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.33,
                    direction_margin=0.11,
                    outline_delta=0.20,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.25),
                _PatchFeatures((), edge_density=0.13, border_score=0.20, center_score=0.35),
                side_coverage=0.51,
                nearby_supported=True,
            )
        )
        self.assertTrue(
            _is_block_heavy_full_spike_candidate(
                _GeometryClass(
                    "spike_left",
                    OBJ_SPIKE_LEFT,
                    0.48,
                    direction_margin=0.20,
                    outline_delta=0.29,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.35),
                _PatchFeatures((), edge_density=0.28, border_score=0.30, center_score=0.22),
                side_coverage=0.80,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_block_heavy_full_spike_candidate(
                _GeometryClass(
                    "spike_left",
                    OBJ_SPIKE_LEFT,
                    0.48,
                    direction_margin=0.20,
                    outline_delta=0.29,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.35),
                _PatchFeatures((), edge_density=0.28, border_score=0.30, center_score=0.22),
                side_coverage=0.80,
                run_supported=False,
            )
        )
        self.assertTrue(
            _is_boundary_full_spike_candidate(
                _GeometryClass(
                    "spike_right",
                    OBJ_SPIKE_RIGHT,
                    0.72,
                    direction_margin=0.08,
                    outline_delta=0.30,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.65),
                _PatchFeatures((), edge_density=0.42, border_score=0.35, center_score=0.70),
                side_coverage=0.80,
                x=480,
                y=0,
                nearby_supported=True,
            )
        )
        self.assertTrue(
            _is_isolated_coherent_full_spike_candidate(
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.47,
                    direction_margin=0.15,
                    outline_delta=0.37,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.34),
                _PatchFeatures((), edge_density=0.29, border_score=0.25, center_score=0.40),
                side_coverage=0.94,
            )
        )
        self.assertTrue(
            _is_supported_shape_full_spike_candidate(
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.41,
                    direction_margin=0.10,
                    outline_delta=0.26,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.32),
                _PatchFeatures((), edge_density=0.28, border_score=0.30, center_score=0.30),
                side_coverage=0.70,
            )
        )
        self.assertFalse(
            _is_supported_shape_full_spike_candidate(
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.41,
                    direction_margin=0.08,
                    outline_delta=0.26,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.32),
                _PatchFeatures((), edge_density=0.28, border_score=0.30, center_score=0.30),
                side_coverage=0.70,
            )
        )
        self.assertTrue(_is_informative_raw_support_density(0.30))
        self.assertTrue(_is_informative_raw_support_density(0.50))
        self.assertFalse(_is_informative_raw_support_density(0.22))
        self.assertFalse(_is_informative_raw_support_density(0.85))
        image_box = Box(0, 0, 32, 32)
        self.assertTrue(
            _is_raw_primary_full_spike_candidate(
                Detection("spike_left", OBJ_SPIKE_LEFT, 64, 64, 0.45, image_box)
            )
        )
        self.assertFalse(
            _is_raw_primary_full_spike_candidate(
                Detection("spike_left", OBJ_SPIKE_LEFT, 64, 64, 0.44, image_box)
            )
        )
        self.assertFalse(
            _is_raw_primary_full_spike_candidate(
                Detection("spike_down", OBJ_SPIKE_DOWN, 64, 64, 0.90, image_box)
            )
        )
        raw_support = Detection(
            "full_spike_support",
            OBJ_SPIKE_RIGHT,
            64,
            64,
            0.34,
            image_box,
        )
        self.assertTrue(
            _is_strong_ambiguous_raw_support_candidate(
                raw_support,
                _GeometryClass(
                    "spike_down",
                    OBJ_SPIKE_DOWN,
                    0.51,
                    direction_margin=0.16,
                    outline_delta=0.27,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.46),
                _PatchFeatures((), edge_density=0.33, border_score=0.30, center_score=0.30),
                side_coverage=0.625,
            )
        )
        self.assertTrue(
            _is_low_texture_raw_support_candidate(
                Detection(
                    "full_spike_support",
                    OBJ_SPIKE_UP,
                    64,
                    64,
                    0.34,
                    image_box,
                ),
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.27,
                    direction_margin=0.13,
                    outline_delta=0.18,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.29),
                _PatchFeatures((), edge_density=0.27, border_score=0.20, center_score=0.20),
                side_coverage=0.375,
            )
        )

    def test_full_spike_origin_normalization_snaps_stable_axis_only(self) -> None:
        self.assertEqual(
            _normalize_full_spike_origin(OBJ_SPIKE_UP, 164, 73),
            (160, 73),
        )
        self.assertEqual(
            _normalize_full_spike_origin(OBJ_SPIKE_DOWN, 167, 73),
            (160, 73),
        )
        self.assertEqual(
            _normalize_full_spike_origin(OBJ_SPIKE_LEFT, 164, 73),
            (164, 80),
        )
        self.assertEqual(
            _normalize_full_spike_origin(OBJ_SPIKE_RIGHT, 164, 73),
            (164, 80),
        )

    def test_shape_recovery_preserves_half_grid_origin(self) -> None:
        image_box = Box(0, 0, 32, 32)
        shape = Detection(
            "full_spike_shape_recovery",
            OBJ_SPIKE_UP,
            168,
            73,
            0.5,
            image_box,
        )
        primary = Detection("spike_up", OBJ_SPIKE_UP, 168, 73, 0.5, image_box)
        normalized = _normalize_full_spike_detections([shape, primary])
        self.assertEqual((normalized[0].x, normalized[0].y), (168, 73))
        self.assertEqual((normalized[1].x, normalized[1].y), (160, 73))

    def test_normalized_full_spike_dedupe_removes_same_direction_duplicate(self) -> None:
        strong = Detection("spike_up", OBJ_SPIKE_UP, 64, 96, 0.80, Box(64, 96, 32, 32))
        weak = Detection("spike_up", OBJ_SPIKE_UP, 72, 104, 0.50, Box(72, 104, 32, 32))
        other_direction = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            72,
            104,
            0.40,
            Box(72, 104, 32, 32),
        )

        result = _dedupe_normalized_full_spikes([weak, other_direction, strong])

        self.assertEqual(
            [(det.type_id, det.x, det.y) for det in result],
            [
                (OBJ_SPIKE_DOWN, 72, 104),
                (OBJ_SPIKE_UP, 64, 96),
            ],
        )

    def test_geometry_dedupe_prefers_primary_grid_spike_over_support_marker(self) -> None:
        primary = Detection("spike_up", OBJ_SPIKE_UP, 480, 256, 0.54, Box(480, 256, 32, 32))
        support = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            480,
            272,
            0.65,
            Box(480, 272, 32, 32),
        )

        result = _dedupe_geometry([support, primary])

        self.assertEqual(result, [primary])

    def test_strong_mini_geometry_survives_full_overlap_noise_prune(self) -> None:
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.64,
                0.84,
                0.33,
                0.55,
                3,
                7,
                1,
                7,
            )
        )

    def test_isolated_weak_full_spike_shape_noise_is_pruned(self) -> None:
        weak = Detection(
            "spike_right",
            OBJ_SPIKE_RIGHT,
            480,
            256,
            0.35,
            Box(480, 256, 32, 32),
        )
        result = _prune_isolated_weak_full_spike_shape_noise(
            [weak],
            _textured_test_image(),
            Box(0, 0, 800, 608),
        )
        self.assertEqual(result, [])

    def test_primary_isolated_full_spike_prune_preserves_run_and_strong_shape(self) -> None:
        weak = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            480,
            256,
            0.60,
            Box(480, 256, 32, 32),
        )
        run_neighbor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            528,
            256,
            0.60,
            Box(528, 256, 32, 32),
        )
        with mock.patch(
            "jtool_scanner.scanner._classify_block",
            return_value=_GeometryClass("block", OBJ_BLOCK, 0.70),
        ), mock.patch(
            "jtool_scanner.scanner._triangle_side_coverage",
            return_value=0.40,
        ):
            result = _prune_primary_isolated_full_spikes(
                [weak],
                _textured_test_image(),
                Box(0, 0, 800, 608),
            )
        self.assertEqual(result, [])

        strong = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            480,
            256,
            0.60,
            Box(480, 256, 32, 32),
        )
        with mock.patch(
            "jtool_scanner.scanner._classify_block",
            return_value=_GeometryClass("block", OBJ_BLOCK, 0.30),
        ), mock.patch(
            "jtool_scanner.scanner._triangle_side_coverage",
            return_value=0.80,
        ):
            result = _prune_primary_isolated_full_spikes(
                [strong],
                _textured_test_image(),
                Box(0, 0, 800, 608),
            )
        self.assertEqual(result, [strong])

        with mock.patch(
            "jtool_scanner.scanner._classify_block",
            return_value=_GeometryClass("block", OBJ_BLOCK, 0.70),
        ), mock.patch(
            "jtool_scanner.scanner._triangle_side_coverage",
            return_value=0.40,
        ):
            result = _prune_primary_isolated_full_spikes(
                [weak, run_neighbor],
                _textured_test_image(),
                Box(0, 0, 800, 608),
            )
        self.assertEqual(result, [weak, run_neighbor])

    def test_final_full_spike_prune_removes_low_score_and_tight_duplicate(self) -> None:
        strong = Detection("spike_up", OBJ_SPIKE_UP, 64, 96, 0.80, Box(64, 96, 32, 32))
        duplicate = Detection("spike_up", OBJ_SPIKE_UP, 68, 100, 0.50, Box(68, 100, 32, 32))
        low_score = Detection("spike_left", OBJ_SPIKE_LEFT, 192, 128, 0.24, Box(192, 128, 32, 32))
        nearby_other_direction = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            68,
            100,
            0.40,
            Box(68, 100, 32, 32),
        )
        save = Detection("save", OBJ_SAVE, 224, 192, 1.00, Box(224, 192, 32, 32))

        result = _prune_recovered_full_spike_noise(
            [duplicate, low_score, nearby_other_direction, save, strong]
        )

        self.assertEqual(
            [(det.type_id, det.x, det.y) for det in result],
            [
                (OBJ_SPIKE_DOWN, 64, 100),
                (OBJ_SAVE, 224, 192),
                (OBJ_SPIKE_UP, 64, 96),
            ],
        )

    def test_duplicate_mini_spike_cell_prune_keeps_highest_score_candidate(self) -> None:
        weak = Detection(
            "mini_spike_up",
            OBJ_MINI_SPIKE_UP,
            96,
            128,
            0.60,
            Box(96, 128, 16, 16),
        )
        strong = Detection(
            "mini_spike_down",
            OBJ_MINI_SPIKE_DOWN,
            96,
            128,
            0.80,
            Box(96, 128, 16, 16),
        )
        separate = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            112,
            128,
            0.50,
            Box(112, 128, 16, 16),
        )

        result = _prune_duplicate_mini_spike_cells([weak, separate, strong])

        self.assertEqual(
            [(det.type_id, det.x, det.y) for det in result],
            [
                (OBJ_MINI_SPIKE_LEFT, 112, 128),
                (OBJ_MINI_SPIKE_DOWN, 96, 128),
            ],
        )

    def test_blocklike_mini_spike_noise_candidate_uses_broad_and_directional_cuts(
        self,
    ) -> None:
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.90,
                0.50,
                0.0,
                0.0,
                4,
                0,
                4,
                0,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.78,
                0.50,
                0.0,
                -0.1,
                4,
                0,
                4,
                0,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.78,
                0.50,
                0.0,
                -0.1,
                4,
                0,
                4,
                0,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.90,
                0.86,
                0.2,
                0.09,
                0,
                3,
                1,
                4,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.90,
                0.86,
                0.2,
                0.09,
                0,
                3,
                1,
                4,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.50,
                0.90,
                0.2,
                0.2,
                0,
                7,
                1,
                0,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.74,
                0.76,
                0.0,
                0.0,
                4,
                0,
                1,
                0,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.74,
                0.84,
                0.08,
                0.12,
                4,
                0,
                2,
                0,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.83,
                0.90,
                0.2,
                0.2,
                4,
                0,
                1,
                0,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.82,
                0.90,
                0.2,
                0.2,
                4,
                0,
                1,
                0,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.89,
                0.90,
                0.2,
                0.2,
                4,
                0,
                1,
                0,
            )
        )

    def test_residual_mini_spike_noise_candidate_prunes_supported_false_shapes(
        self,
    ) -> None:
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.92,
                0.88,
                0.08,
                0.20,
                0,
                0,
                5,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.65,
                0.70,
                0.15,
                0.40,
                0,
                0,
                3,
                3,
                2,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.65,
                0.70,
                0.15,
                0.40,
                0,
                0,
                3,
                3,
                2,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.65,
                0.70,
                0.15,
                0.40,
                1,
                1,
                3,
                3,
                2,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.40,
                0.30,
                0.18,
                0.50,
                0,
                0,
                5,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.40,
                0.50,
                0.20,
                0.50,
                0,
                0,
                5,
                2,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.72,
                0.80,
                0.08,
                0.35,
                0,
                0,
                4,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.55,
                0.60,
                0.08,
                0.20,
                0,
                0,
                2,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.50,
                0.72,
                0.20,
                0.50,
                0,
                0,
                2,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.50,
                0.60,
                0.10,
                0.20,
                0,
                0,
                4,
                2,
                1,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.40,
                0.65,
                0.20,
                0.50,
                0,
                0,
                0,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.70,
                0.70,
                0.10,
                0.15,
                0,
                0,
                4,
                3,
                2,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.40,
                0.80,
                0.20,
                0.50,
                0,
                0,
                5,
                0,
                0,
            )
        )

        self.assertFalse(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.90,
                0.72,
                -0.05,
                -0.02,
                1,
                2,
                6,
                0,
                0,
            )
        )
        self.assertFalse(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.12,
                0.20,
                0.0,
                0.05,
                0,
                0,
                0,
                0,
                0,
            )
        )
        self.assertFalse(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.80,
                0.70,
                -0.04,
                0.15,
                1,
                1,
                4,
                1,
                3,
            )
        )
        self.assertFalse(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.88,
                0.86,
                0.07,
                0.22,
                1,
                1,
                1,
                2,
                3,
            )
        )

    def test_diagonal_right_mini_step_support_requires_half_step_pair(self) -> None:
        candidate = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            112,
            544,
            0.70,
            Box(112, 544, 16, 16),
        )
        diagonal_support = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            96,
            512,
            0.65,
            Box(96, 512, 16, 16),
        )
        vertical_only = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            112,
            512,
            0.65,
            Box(112, 512, 16, 16),
        )

        self.assertTrue(
            _has_diagonal_right_mini_step_support(
                candidate,
                [candidate, diagonal_support],
            )
        )
        self.assertFalse(
            _has_diagonal_right_mini_step_support(
                candidate,
                [candidate, vertical_only],
            )
        )

    def test_axis_left_mini_step_support_requires_vertical_half_step_pair(self) -> None:
        candidate = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            304,
            384,
            0.70,
            Box(304, 384, 16, 16),
        )
        vertical_support = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            304,
            416,
            0.65,
            Box(304, 416, 16, 16),
        )
        diagonal_only = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            320,
            416,
            0.65,
            Box(320, 416, 16, 16),
        )

        self.assertTrue(
            _has_axis_left_mini_step_support(
                candidate,
                [candidate, vertical_support],
            )
        )
        self.assertFalse(
            _has_axis_left_mini_step_support(
                candidate,
                [candidate, diagonal_only],
            )
        )

    def test_adaptive_block_noise_prunes_bimodal_dense_room(self) -> None:
        weak = [
            Detection("block", OBJ_BLOCK, x * 32, 0, 0.35, Box(x * 32, 0, 32, 32))
            for x in range(192)
        ]
        strong = [
            Detection(
                "block",
                OBJ_BLOCK,
                (x + 192) * 32,
                0,
                0.80,
                Box((x + 192) * 32, 0, 32, 32),
            )
            for x in range(64)
        ]
        mini = Detection(
            "mini_spike_up",
            OBJ_MINI_SPIKE_UP,
            0,
            0,
            0.5,
            Box(0, 0, 16, 16),
        )

        result = _prune_adaptive_block_noise([*weak, *strong, mini])

        self.assertEqual(result, [*strong, mini])

    def test_isolated_weak_block_noise_keeps_supported_blocks(self) -> None:
        isolated = Detection("block", OBJ_BLOCK, 128, 0, 0.34, Box(128, 0, 32, 32))
        supported = Detection("block", OBJ_BLOCK, 32, 0, 0.34, Box(32, 0, 32, 32))
        strong = Detection("block", OBJ_BLOCK, 64, 0, 0.50, Box(64, 0, 32, 32))
        filler = [
            Detection("block", OBJ_BLOCK, 1000 + index * 64, 0, 0.50, Box(0, 0, 32, 32))
            for index in range(256)
        ]

        result = _prune_isolated_weak_block_noise([isolated, supported, strong, *filler])

        self.assertNotIn(isolated, result)
        self.assertIn(supported, result)
        self.assertIn(strong, result)

    def test_adaptive_weak_block_noise_keeps_non_block_objects(self) -> None:
        weak = [
            Detection("block", OBJ_BLOCK, index * 32, 0, 0.282, Box(0, 0, 32, 32))
            for index in range(192)
        ]
        strong = [
            Detection("block", OBJ_BLOCK, (index + 192) * 32, 0, 0.70, Box(0, 0, 32, 32))
            for index in range(64)
        ]
        mini = Detection(
            "mini_spike_up",
            OBJ_MINI_SPIKE_UP,
            0,
            0,
            0.282,
            Box(0, 0, 16, 16),
        )

        result = _prune_adaptive_weak_block_noise([*weak, *strong, mini])

        self.assertEqual(result, [*strong, mini])

    def test_adaptive_weak_block_noise_prunes_mid_signal_tail(self) -> None:
        weak = [
            Detection("block", OBJ_BLOCK, index * 32, 64, 0.34, Box(0, 0, 32, 32))
            for index in range(192)
        ]
        strong = [
            Detection("block", OBJ_BLOCK, (index + 192) * 32, 64, 0.52, Box(0, 0, 32, 32))
            for index in range(64)
        ]

        result = _prune_adaptive_weak_block_noise([*weak, *strong])

        self.assertEqual(result, strong)

    def test_adaptive_weak_block_noise_keeps_supported_boundary_tile(self) -> None:
        boundary = Detection("block", OBJ_BLOCK, 288, 0, 0.4998, Box(0, 0, 32, 32))
        support = Detection("block", OBJ_BLOCK, 256, 0, 0.54, Box(0, 0, 32, 32))
        filler = [
            Detection("block", OBJ_BLOCK, 1000 + index * 64, 64, 0.55, Box(0, 0, 32, 32))
            for index in range(256)
        ]

        result = _prune_adaptive_weak_block_noise([boundary, support, *filler])

        self.assertIn(boundary, result)

    def test_supported_block_cells_recover_a_strong_grid_gap(self) -> None:
        image = _textured_test_image()
        first = Detection("block", OBJ_BLOCK, 704, 480, 0.55, Box(704, 480, 32, 32))
        second = Detection("block", OBJ_BLOCK, 768, 480, 0.55, Box(768, 480, 32, 32))
        vertical = Detection("block", OBJ_BLOCK, 736, 448, 0.55, Box(736, 448, 32, 32))

        result = _recover_supported_block_cells(
            [first, second, vertical], image, Box(0, 0, 800, 608)
        )

        self.assertTrue(any(det.x == 736 and det.y == 480 for det in result))

    def test_sparse_off_grid_block_noise_removes_outliers(self) -> None:
        aligned = [
            Detection("block", OBJ_BLOCK, index * 32, 0, 0.5, Box(0, 0, 32, 32))
            for index in range(64)
        ]
        outliers = [
            Detection("block", OBJ_BLOCK, 2048 + index * 32, 8, 0.5, Box(0, 0, 32, 32))
            for index in range(2)
        ]

        result = _prune_sparse_off_grid_block_noise([*aligned, *outliers])

        self.assertEqual(result, aligned)

    def test_sparse_off_grid_block_noise_keeps_real_offset_population(self) -> None:
        aligned = [
            Detection("block", OBJ_BLOCK, index * 32, 0, 0.5, Box(0, 0, 32, 32))
            for index in range(64)
        ]
        outliers = [
            Detection("block", OBJ_BLOCK, 2048 + index * 32, 8, 0.5, Box(0, 0, 32, 32))
            for index in range(4)
        ]

        result = _prune_sparse_off_grid_block_noise([*aligned, *outliers])

        self.assertEqual(result, [*aligned, *outliers])

    def test_dark_outline_low_signal_prune_keeps_other_objects(self) -> None:
        weak = [
            Detection("block", OBJ_BLOCK, index * 32, 0, 0.282, Box(0, 0, 32, 32))
            for index in range(192)
        ]
        strong = [
            Detection("block", OBJ_BLOCK, (index + 192) * 32, 0, 0.80, Box(0, 0, 32, 32))
            for index in range(64)
        ]
        mini = Detection("mini_spike_up", OBJ_MINI_SPIKE_UP, 0, 0, 0.282, Box(0, 0, 16, 16))

        result = _prune_dark_outline_low_signal_blocks([*weak, *strong, mini])

        self.assertEqual(result, [*strong, mini])

    def test_dark_outline_supported_low_signal_recovery_uses_hollow_edges(self) -> None:
        image = _textured_test_image()
        candidate = Detection("block", OBJ_BLOCK, 64, 64, 0.282, Box(64, 64, 32, 32))
        result = _recover_dark_outline_supported_low_signal_blocks(
            [candidate], [], image, Box(0, 0, 800, 608)
        )

        self.assertEqual(result, [])

    def test_dark_outline_long_run_recovery_fills_faint_interior_cells(self) -> None:
        image = _textured_test_image()
        anchors = [
            Detection("block", OBJ_BLOCK, 96, 0, 0.50, Box(96, 0, 32, 32)),
            Detection("block", OBJ_BLOCK, 96, 128, 0.50, Box(96, 128, 32, 32)),
        ]
        faint_patch = _PatchFeatures((), 0.02, 0.0, 0.0)
        with mock.patch(
            "jtool_scanner.scanner._is_dark_outline_room",
            return_value=True,
        ), mock.patch(
            "jtool_scanner.scanner._patch_features",
            return_value=faint_patch,
        ):
            result = _recover_dark_outline_long_low_signal_runs(
                anchors,
                image,
                Box(0, 0, 800, 608),
            )

        self.assertEqual(
            {(det.x, det.y) for det in result if det.type_id == OBJ_BLOCK},
            {(96, 0), (96, 32), (96, 64), (96, 96), (96, 128)},
        )

    def test_full_spike_run_gap_recovery_fills_same_direction_midpoint(self) -> None:
        image = _textured_test_image()
        first = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            192,
            208,
            0.55,
            Box(192, 208, 32, 32),
        )
        second = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            256,
            208,
            0.50,
            Box(256, 208, 32, 32),
        )

        result = _recover_full_spike_run_gaps(
            [first, second],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertIn(
            (OBJ_SPIKE_UP, 224, 208),
            [(det.type_id, det.x, det.y) for det in result],
        )

    def test_full_spike_run_gap_recovery_keeps_existing_midpoint_unique(self) -> None:
        image = _textured_test_image()
        detections = [
            Detection(
                "spike_up",
                OBJ_SPIKE_UP,
                192,
                208,
                0.55,
                Box(192, 208, 32, 32),
            ),
            Detection(
                "spike_up",
                OBJ_SPIKE_UP,
                224,
                208,
                0.60,
                Box(224, 208, 32, 32),
            ),
            Detection(
                "spike_up",
                OBJ_SPIKE_UP,
                256,
                208,
                0.50,
                Box(256, 208, 32, 32),
            ),
        ]

        result = _recover_full_spike_run_gaps(
            detections,
            image,
            Box(0, 0, 800, 608),
        )

        self.assertEqual(
            1,
            sum(
                1
                for det in result
                if det.type_id == OBJ_SPIKE_UP and det.x == 224 and det.y == 208
            ),
        )

    def test_full_spike_run_gap_patch_requires_textured_midpoint(self) -> None:
        self.assertTrue(
            _is_full_spike_run_gap_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.35,
                    border_score=0.20,
                    center_score=0.25,
                )
            )
        )
        self.assertFalse(
            _is_full_spike_run_gap_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.34,
                    border_score=0.20,
                    center_score=0.25,
                )
            )
        )

    def test_blocklike_full_spike_recovery_requires_medium_center_body(self) -> None:
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.39,
            direction_margin=0.06,
            outline_delta=0.11,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.40)
        patch = _PatchFeatures(
            (),
            edge_density=0.30,
            border_score=0.20,
            center_score=0.25,
        )

        self.assertTrue(
            _is_blocklike_full_spike_recovery_candidate(spike, block, patch)
        )
        self.assertFalse(
            _is_blocklike_full_spike_recovery_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.46),
                patch,
            )
        )
        self.assertFalse(
            _is_blocklike_full_spike_recovery_candidate(
                spike,
                block,
                _PatchFeatures(
                    (),
                    edge_density=0.30,
                    border_score=0.20,
                    center_score=0.40,
                ),
            )
        )

    def test_blocklike_full_spike_recovery_uses_same_direction_support(self) -> None:
        image = _textured_test_image()
        supported = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            224,
            96,
            0.55,
            Box(224, 96, 32, 32),
        )

        result = _recover_blocklike_full_spikes(
            [supported],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertTrue(
            any(
                det.type_id == OBJ_SPIKE_UP
                and 128 <= det.x <= 320
                and det.y == 96
                for det in result
            )
        )

    def test_edge_full_spike_continuation_anchor_requires_facing_room_edge(self) -> None:
        left_edge = Detection(
            "spike_left",
            OBJ_SPIKE_LEFT,
            0,
            192,
            0.75,
            Box(0, 192, 32, 32),
        )
        right_edge = Detection(
            "spike_right",
            OBJ_SPIKE_RIGHT,
            768,
            192,
            0.75,
            Box(768, 192, 32, 32),
        )
        interior = Detection(
            "spike_left",
            OBJ_SPIKE_LEFT,
            32,
            192,
            0.75,
            Box(32, 192, 32, 32),
        )
        weak = Detection(
            "spike_left",
            OBJ_SPIKE_LEFT,
            0,
            192,
            0.74,
            Box(0, 192, 32, 32),
        )

        self.assertTrue(_is_edge_full_spike_continuation_anchor(left_edge))
        self.assertTrue(_is_edge_full_spike_continuation_anchor(right_edge))
        self.assertFalse(_is_edge_full_spike_continuation_anchor(interior))
        self.assertFalse(_is_edge_full_spike_continuation_anchor(weak))

    def test_edge_full_spike_continuation_patch_requires_texture(self) -> None:
        self.assertTrue(
            _is_edge_full_spike_continuation_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.35,
                    border_score=0.20,
                    center_score=0.25,
                )
            )
        )
        self.assertFalse(
            _is_edge_full_spike_continuation_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.34,
                    border_score=0.20,
                    center_score=0.25,
                )
            )
        )

    def test_bottom_edge_up_spike_continuation_anchor_requires_bottom_half_step(self) -> None:
        anchor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            160,
            568,
            0.44,
            Box(160, 568, 32, 32),
        )
        wrong_y = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            160,
            560,
            0.44,
            Box(160, 560, 32, 32),
        )
        weak = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            160,
            568,
            0.43,
            Box(160, 568, 32, 32),
        )

        self.assertTrue(_is_bottom_edge_up_spike_continuation_anchor(anchor))
        self.assertFalse(_is_bottom_edge_up_spike_continuation_anchor(wrong_y))
        self.assertFalse(_is_bottom_edge_up_spike_continuation_anchor(weak))

    def test_bottom_edge_up_spike_continuation_patch_requires_texture(self) -> None:
        self.assertTrue(
            _is_bottom_edge_up_spike_continuation_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.27,
                    border_score=0.15,
                    center_score=0.18,
                )
            )
        )
        self.assertFalse(
            _is_bottom_edge_up_spike_continuation_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.26,
                    border_score=0.15,
                    center_score=0.18,
                )
            )
        )

    def test_up_spike_half_step_continuation_patch_requires_strong_up_outline(self) -> None:
        self.assertTrue(
            _is_up_spike_half_step_continuation_patch(
                _up_outline_patch(
                    edge_density=0.37,
                    border_score=0.25,
                    center_score=0.45,
                )
            )
        )
        self.assertFalse(
            _is_up_spike_half_step_continuation_patch(
                _up_outline_patch(
                    edge_density=0.36,
                    border_score=0.25,
                    center_score=0.45,
                )
            )
        )

    def test_up_spike_full_step_continuation_patch_requires_dense_texture(self) -> None:
        self.assertTrue(
            _is_up_spike_full_step_continuation_patch(
                _up_outline_patch(
                    edge_density=0.48,
                    border_score=0.38,
                    center_score=0.58,
                )
            )
        )
        self.assertFalse(
            _is_up_spike_full_step_continuation_patch(
                _up_outline_patch(
                    edge_density=0.48,
                    border_score=0.38,
                    center_score=0.57,
                )
            )
        )

    def test_up_spike_lateral_continuation_recovers_half_step_run(self) -> None:
        image = _up_spike_test_image([(176, 208)])
        anchor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            192,
            208,
            0.44,
            Box(192, 208, 32, 32),
        )
        run_support = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            256,
            208,
            0.38,
            Box(256, 208, 32, 32),
        )

        result = _recover_up_spike_lateral_continuations(
            [anchor, run_support],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertIn(
            (OBJ_SPIKE_UP, 176, 208),
            [(det.type_id, det.x, det.y) for det in result],
        )

    def test_up_spike_lateral_continuation_recovers_strong_full_step(self) -> None:
        image = _up_spike_test_image([(448, 272)])
        anchor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            480,
            272,
            0.60,
            Box(480, 272, 32, 32),
        )

        result = _recover_up_spike_lateral_continuations(
            [anchor],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertIn(
            (OBJ_SPIKE_UP, 448, 272),
            [(det.type_id, det.x, det.y) for det in result],
        )

    def test_patch_range_helper_accepts_values_inside_all_ranges(self) -> None:
        patch = _PatchFeatures((), edge_density=0.25, border_score=0.15, center_score=0.30)

        self.assertTrue(_value_in_range(0.25, (0.20, 0.30)))
        self.assertTrue(
            _patch_in_ranges(
                patch,
                (0.20, 0.30),
                (0.10, 0.20),
                (0.25, 0.35),
            )
        )
        self.assertFalse(_value_in_range(0.31, (0.20, 0.30)))
        self.assertFalse(
            _patch_in_ranges(
                patch,
                (0.26, 0.30),
                (0.10, 0.20),
                (0.25, 0.35),
            )
        )

    def test_left_spike_supports_require_counted_nearby_left_spikes(self) -> None:
        detections = [
            Detection("spike_left", OBJ_SPIKE_LEFT, 704, 96, 0.60, Box(704, 96, 32, 32)),
            Detection("spike_left", OBJ_SPIKE_LEFT, 568, 64, 0.55, Box(568, 64, 32, 32)),
            Detection("spike_left", OBJ_SPIKE_LEFT, 640, 160, 0.70, Box(640, 160, 32, 32)),
            Detection("spike_right", OBJ_SPIKE_RIGHT, 656, 64, 0.90, Box(656, 64, 32, 32)),
        ]

        self.assertTrue(_has_left_spike_supports(detections, 640, 64, 40, 80, 2))
        self.assertFalse(_has_left_spike_supports(detections, 640, 64, 40, 60, 2))
        self.assertFalse(_has_left_spike_supports(detections, 640, 64, 40, 80, 3))

    def test_outline_block_accepts_aligned_empty_center_patch(self) -> None:
        candidate = _GeometryPatchCandidate(
            32,
            64,
            _PatchFeatures((), edge_density=0.06, border_score=0.12, center_score=0.0),
            spike=None,
            block=_GeometryClass("block", OBJ_BLOCK, 0.20),
        )

        self.assertIsNotNone(_outline_block_score(candidate))

    def test_outline_block_rejects_off_grid_patch(self) -> None:
        candidate = _GeometryPatchCandidate(
            40,
            64,
            _PatchFeatures((), edge_density=0.06, border_score=0.12, center_score=0.0),
            spike=None,
            block=_GeometryClass("block", OBJ_BLOCK, 0.20),
        )

        self.assertIsNone(_outline_block_score(candidate))

    def test_mini_spike_rejects_blocklike_weak_direction_candidate(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.90)
        mini = _GeometryClass(
            "mini_spike_down",
            OBJ_MINI_SPIKE_DOWN,
            0.80,
            direction_margin=0.05,
            outline_delta=0.30,
        )

        self.assertFalse(_accept_mini_spike(mini, block))

    def test_mini_spike_accepts_blocklike_clear_direction_candidate(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.90)
        mini = _GeometryClass(
            "mini_spike_down",
            OBJ_MINI_SPIKE_DOWN,
            0.80,
            direction_margin=0.08,
            outline_delta=0.30,
        )

        self.assertTrue(_accept_mini_spike(mini, block))

    def test_axis_mini_spike_support_uses_same_direction_axis(self) -> None:
        detections = [
            Detection(
                "mini_spike_up",
                OBJ_MINI_SPIKE_UP,
                128,
                96,
                0.50,
                Box(128, 96, 16, 16),
            ),
            Detection(
                "mini_spike_left",
                OBJ_MINI_SPIKE_LEFT,
                320,
                240,
                0.50,
                Box(320, 240, 16, 16),
            ),
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                160,
                96,
                0.90,
                Box(160, 96, 16, 16),
            ),
        ]

        self.assertTrue(
            _has_axis_mini_spike_support(detections, OBJ_MINI_SPIKE_UP, 176, 96)
        )
        self.assertTrue(
            _has_axis_mini_spike_support(detections, OBJ_MINI_SPIKE_LEFT, 320, 288)
        )
        self.assertFalse(
            _has_axis_mini_spike_support(detections, OBJ_MINI_SPIKE_UP, 128, 144)
        )
        self.assertFalse(
            _has_axis_mini_spike_support(detections, OBJ_MINI_SPIKE_RIGHT, 224, 96)
        )

    def test_axis_supported_mini_spike_recovery_rejects_blocklike_noise(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.25,
            border_score=0.25,
            center_score=0.25,
        )
        mini = _GeometryClass(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            0.55,
            direction_margin=0.01,
            outline_delta=0.12,
        )

        self.assertTrue(
            _can_recover_axis_supported_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.50),
                patch,
            )
        )
        self.assertFalse(
            _can_recover_axis_supported_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.90),
                patch,
            )
        )

    def test_axis_supported_mini_spike_recovery_adds_supported_candidate(self) -> None:
        image = _mini_left_test_image([(128, 112)])
        support = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            128,
            64,
            0.60,
            Box(128, 64, 16, 16),
        )

        result = _recover_axis_supported_mini_spikes(
            [support],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertIn(
            (OBJ_MINI_SPIKE_LEFT, 128, 112),
            [(det.type_id, det.x, det.y) for det in result],
        )

    def test_horizontal_side_mini_support_uses_strong_same_row_anchor(self) -> None:
        detections = [
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                656,
                592,
                0.80,
                Box(656, 592, 16, 16),
            ),
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                704,
                544,
                0.90,
                Box(704, 544, 16, 16),
            ),
        ]

        self.assertTrue(
            _has_horizontal_side_mini_spike_support(
                detections,
                OBJ_MINI_SPIKE_RIGHT,
                704,
                592,
            )
        )
        self.assertFalse(
            _has_horizontal_side_mini_spike_support(
                detections,
                OBJ_MINI_SPIKE_RIGHT,
                704,
                576,
            )
        )

    def test_horizontal_side_mini_recovery_requires_clear_side_shape(self) -> None:
        clear_patch = _PatchFeatures(
            (),
            edge_density=0.45,
            border_score=0.30,
            center_score=0.40,
        )
        weak_patch = _PatchFeatures(
            (),
            edge_density=0.39,
            border_score=0.30,
            center_score=0.40,
        )
        mini = _GeometryClass(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            0.60,
            direction_margin=0.01,
            outline_delta=0.19,
        )

        self.assertTrue(
            _can_recover_horizontal_side_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.50),
                clear_patch,
            )
        )
        self.assertFalse(
            _can_recover_horizontal_side_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.50),
                weak_patch,
            )
        )

    def test_diagonal_side_mini_support_uses_nearby_vertical_offset_anchor(self) -> None:
        detections = [
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                112,
                544,
                0.75,
                Box(112, 544, 16, 16),
            ),
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                160,
                512,
                0.90,
                Box(160, 512, 16, 16),
            ),
        ]

        self.assertTrue(
            _has_diagonal_side_mini_spike_support(
                detections,
                OBJ_MINI_SPIKE_RIGHT,
                96,
                512,
            )
        )
        self.assertFalse(
            _has_diagonal_side_mini_spike_support(
                detections,
                OBJ_MINI_SPIKE_RIGHT,
                96,
                544,
            )
        )

    def test_diagonal_side_mini_recovery_requires_clear_side_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.36,
            border_score=0.30,
            center_score=0.46,
        )
        mini = _GeometryClass(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            0.53,
            direction_margin=0.0,
            outline_delta=0.29,
        )

        self.assertTrue(
            _can_recover_diagonal_side_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.60),
                patch,
            )
        )
        self.assertFalse(
            _can_recover_diagonal_side_mini_spike(
                _GeometryClass(
                    "mini_spike_right",
                    OBJ_MINI_SPIKE_RIGHT,
                    0.53,
                    direction_margin=-0.06,
                    outline_delta=0.29,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.66),
                patch,
            )
        )

    def test_extended_left_mini_support_uses_farther_vertical_offset_anchor(self) -> None:
        detections = [
            Detection(
                "mini_spike_left",
                OBJ_MINI_SPIKE_LEFT,
                576,
                528,
                0.68,
                Box(576, 528, 16, 16),
            ),
            Detection(
                "mini_spike_left",
                OBJ_MINI_SPIKE_LEFT,
                608,
                560,
                0.90,
                Box(608, 560, 16, 16),
            ),
        ]

        self.assertTrue(_has_extended_left_mini_spike_support(detections, 560, 592))
        self.assertFalse(_has_extended_left_mini_spike_support(detections, 560, 528))

    def test_extended_left_mini_recovery_requires_supported_left_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.41,
            border_score=0.30,
            center_score=0.46,
        )
        mini = _GeometryClass(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            0.46,
            direction_margin=0.0,
            outline_delta=0.13,
        )

        self.assertTrue(
            _can_recover_extended_left_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.60),
                patch,
            )
        )
        self.assertFalse(
            _can_recover_extended_left_mini_spike(
                _GeometryClass(
                    "mini_spike_left",
                    OBJ_MINI_SPIKE_LEFT,
                    0.46,
                    direction_margin=-0.06,
                    outline_delta=0.13,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.71),
                patch,
            )
        )

    def test_low_contrast_mini_up_candidate_requires_pairable_weak_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.08,
            border_score=0.05,
            center_score=0.12,
        )

        self.assertTrue(
            _is_low_contrast_mini_up_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.20),
                0.09,
                0.05,
            )
        )
        self.assertFalse(
            _is_low_contrast_mini_up_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.21),
                0.09,
                0.05,
            )
        )
        self.assertTrue(
            _has_low_contrast_mini_up_pair(
                {
                    (544, 112): 0.14,
                    (560, 112): 0.14,
                },
                544,
                112,
            )
        )
        self.assertFalse(
            _has_low_contrast_mini_up_pair(
                {
                    (544, 112): 0.14,
                    (592, 112): 0.14,
                },
                544,
                112,
            )
        )

    def test_direct_full_scale_evidence_blocks_weak_mini_pair_recovery(self) -> None:
        full_spikes = [
            Detection("spike_up", OBJ_SPIKE_UP, index * 32, 0, 0.5, Box(0, 0, 32, 32))
            for index in range(20)
        ]
        one_mini = Detection(
            "mini_spike_up", OBJ_MINI_SPIKE_UP, 0, 32, 0.3, Box(0, 0, 16, 16)
        )

        self.assertTrue(_is_directly_full_scale_dominant(full_spikes))
        self.assertTrue(_is_directly_full_scale_dominant([*full_spikes, one_mini]))
        self.assertFalse(
            _is_directly_full_scale_dominant(
                [
                    *full_spikes,
                    *[
                        Detection(
                            "mini_spike_up",
                            OBJ_MINI_SPIKE_UP,
                            index * 16,
                            32,
                            0.3,
                            Box(0, 0, 16, 16),
                        )
                        for index in range(2)
                    ],
                ]
            )
        )

    def test_dense_minispike_lattice_requires_abundant_axis_consistent_evidence(self) -> None:
        vertical_minis = [
            Detection(
                "mini_spike_up" if index % 2 == 0 else "mini_spike_down",
                OBJ_MINI_SPIKE_UP if index % 2 == 0 else OBJ_MINI_SPIKE_DOWN,
                (index % 25) * 16,
                (index // 25) * 16,
                0.5,
                Box(0, 0, 16, 16),
            )
            for index in range(120)
        ]
        full_spikes = [
            Detection("spike_up", OBJ_SPIKE_UP, 0, 0, 0.5, Box(0, 0, 32, 32))
            for _ in range(300)
        ]

        self.assertEqual(
            _dense_minispike_lattice_axis(vertical_minis, full_spikes),
            frozenset((OBJ_MINI_SPIKE_UP, OBJ_MINI_SPIKE_DOWN)),
        )
        self.assertIsNone(
            _dense_minispike_lattice_axis(vertical_minis[:80], full_spikes)
        )
        mixed_axes = [
            *vertical_minis[:60],
            *[
                Detection(
                    "mini_spike_right",
                    OBJ_MINI_SPIKE_RIGHT,
                    (index % 25) * 16,
                    (index // 25) * 16,
                    0.5,
                    Box(0, 0, 16, 16),
                )
                for index in range(60)
            ],
        ]
        self.assertIsNone(_dense_minispike_lattice_axis(mixed_axes, full_spikes))

    def test_bright_filled_spike_component_requires_inside_and_luma_contrast(self) -> None:
        self.assertTrue(
            _is_bright_filled_full_spike_component(
                _TriangleFillFeatures(120.0, 0.90, 0.10, 0.80, 80.0)
            )
        )
        self.assertFalse(
            _is_bright_filled_full_spike_component(
                _TriangleFillFeatures(120.0, 0.90, 0.55, 0.35, 80.0)
            )
        )
        self.assertFalse(
            _is_bright_filled_full_spike_component(
                _TriangleFillFeatures(10.0, 0.90, 0.10, 0.80, 10.0)
            )
        )

    def test_bright_neutral_component_uses_centroid_mass_as_triangle_base(self) -> None:
        self.assertEqual(_bright_neutral_triangle_direction(0.01, 0.12), "up")
        self.assertEqual(_bright_neutral_triangle_direction(-0.15, 0.02), "right")
        self.assertEqual(_bright_neutral_triangle_direction(0.15, 0.02), "left")
        self.assertIsNone(_bright_neutral_triangle_direction(0.03, -0.04))

    def test_bright_filled_reconciliation_requires_an_existing_spike_field(self) -> None:
        self.assertTrue(_should_reconcile_bright_filled_full_spikes(82, 84))
        self.assertFalse(_should_reconcile_bright_filled_full_spikes(50, 0))
        self.assertFalse(_should_reconcile_bright_filled_full_spikes(31, 1))

    def test_detached_top_ui_band_requires_text_shape_and_lower_anchor(self) -> None:
        metrics = dict(
            upper_count=36,
            upper_block_count=29,
            lower_count=15,
            lower_block_count=13,
            upper_min_y=-32,
            upper_width=768,
            upper_height=128,
            gap=160,
            upper_center=0.0,
            lower_center=0.28,
            has_lower_anchor=True,
        )
        self.assertTrue(_looks_like_detached_top_ui_band(**metrics))
        self.assertFalse(
            _looks_like_detached_top_ui_band(
                **{**metrics, "upper_center": 0.24}
            )
        )
        self.assertFalse(
            _looks_like_detached_top_ui_band(
                **{**metrics, "has_lower_anchor": False}
            )
        )

    def test_bright_neutral_component_profile_requires_coverage_and_sparse_mask(self) -> None:
        self.assertTrue(_should_use_bright_neutral_spike_components(80, 102, 0.05))
        self.assertFalse(_should_use_bright_neutral_spike_components(64, 84, 0.05))
        self.assertFalse(_should_use_bright_neutral_spike_components(80, 1, 0.05))
        self.assertFalse(_should_use_bright_neutral_spike_components(80, 102, 0.20))

    def test_oversized_bright_neutral_profile_requires_coherent_scale_mismatch(self) -> None:
        metrics = dict(
            component_count=15,
            current_full_spike_count=38,
            exact_overlap_count=0,
            median_map_area=890.0,
            median_min_extent=39.0,
            component_mask_share=0.05,
        )
        self.assertTrue(
            _should_use_oversized_bright_neutral_spike_components(**metrics)
        )
        self.assertFalse(
            _should_use_oversized_bright_neutral_spike_components(
                **{**metrics, "median_map_area": 404.0, "median_min_extent": 28.0}
            )
        )
        self.assertFalse(
            _should_use_oversized_bright_neutral_spike_components(
                **{**metrics, "component_count": 1}
            )
        )

    def test_adjacent_up_mini_candidate_requires_clear_up_pair_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.43,
            border_score=0.30,
            center_score=0.26,
        )
        mini = _GeometryClass(
            "mini_spike_up",
            OBJ_MINI_SPIKE_UP,
            0.48,
            direction_margin=0.01,
            outline_delta=0.04,
        )

        self.assertTrue(
            _is_adjacent_up_mini_spike_candidate(
                mini,
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.54),
            )
        )
        self.assertFalse(
            _is_adjacent_up_mini_spike_candidate(
                mini,
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.56),
            )
        )
        self.assertTrue(
            _has_adjacent_up_mini_spike_pair(
                {
                    (352, 304): 0.50,
                    (368, 304): 0.55,
                },
                352,
                304,
            )
        )
        self.assertFalse(
            _has_adjacent_up_mini_spike_pair(
                {
                    (352, 304): 0.50,
                    (400, 304): 0.55,
                },
                352,
                304,
            )
        )

    def test_dense_adjacent_up_mini_requires_textured_blocklike_neighbor(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.72,
            border_score=0.40,
            center_score=0.82,
        )

        self.assertTrue(
            _is_dense_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.82),
                0.72,
                -0.04,
            )
        )
        self.assertFalse(
            _is_dense_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.79),
                0.72,
                -0.04,
            )
        )
        self.assertTrue(
            _has_dense_adjacent_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_up",
                        OBJ_MINI_SPIKE_UP,
                        656,
                        560,
                        0.47,
                        Box(656, 560, 16, 16),
                    )
                ],
                672,
                560,
            )
        )
        self.assertFalse(
            _has_dense_adjacent_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_up",
                        OBJ_MINI_SPIKE_UP,
                        640,
                        560,
                        0.47,
                        Box(640, 560, 16, 16),
                    )
                ],
                672,
                560,
            )
        )

    def test_ambiguous_adjacent_up_mini_requires_paired_blocklike_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.43,
            border_score=0.30,
            center_score=0.44,
        )

        self.assertTrue(
            _is_ambiguous_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.44),
                0.24,
                0.50,
            )
        )
        self.assertFalse(
            _is_ambiguous_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.47),
                0.24,
                0.50,
            )
        )
        self.assertFalse(
            _is_ambiguous_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.44),
                0.24,
                0.53,
            )
        )
        self.assertTrue(
            _has_ambiguous_adjacent_up_mini_spike_pair(
                {
                    (128, 112): 0.28,
                    (144, 112): 0.24,
                },
                128,
                112,
            )
        )
        self.assertFalse(
            _has_ambiguous_adjacent_up_mini_spike_pair(
                {
                    (128, 112): 0.28,
                    (176, 112): 0.24,
                },
                128,
                112,
            )
        )

    def test_mixed_cluster_up_mini_requires_right_and_down_support(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.51,
            border_score=0.40,
            center_score=0.56,
        )

        self.assertTrue(
            _is_mixed_cluster_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.57),
                0.41,
                0.59,
            )
        )
        self.assertFalse(
            _is_mixed_cluster_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.61),
                0.41,
                0.59,
            )
        )
        self.assertTrue(
            _has_mixed_cluster_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_right",
                        OBJ_MINI_SPIKE_RIGHT,
                        64,
                        160,
                        0.62,
                        Box(64, 160, 16, 16),
                    ),
                    Detection(
                        "mini_spike_down",
                        OBJ_MINI_SPIKE_DOWN,
                        48,
                        176,
                        0.85,
                        Box(48, 176, 16, 16),
                    ),
                ],
                48,
                144,
            )
        )
        self.assertFalse(
            _has_mixed_cluster_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_right",
                        OBJ_MINI_SPIKE_RIGHT,
                        64,
                        160,
                        0.62,
                        Box(64, 160, 16, 16),
                    )
                ],
                48,
                144,
            )
        )

    def test_border_supported_up_mini_requires_border_heavy_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.34,
            border_score=0.36,
            center_score=0.24,
        )

        self.assertTrue(
            _is_border_supported_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.40),
                0.29,
                0.36,
            )
        )
        self.assertFalse(
            _is_border_supported_up_mini_spike_candidate(
                _PatchFeatures(
                    (),
                    edge_density=0.34,
                    border_score=0.24,
                    center_score=0.41,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.40),
                0.29,
                0.36,
            )
        )
        self.assertTrue(
            _has_border_supported_up_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        544,
                        144,
                        0.50,
                        Box(544, 144, 32, 32),
                    ),
                    Detection(
                        "spike_up",
                        OBJ_SPIKE_UP,
                        544,
                        144,
                        0.52,
                        Box(544, 144, 32, 32),
                    ),
                ],
                560,
                144,
            )
        )
        self.assertFalse(
            _has_border_supported_up_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        544,
                        144,
                        0.50,
                        Box(544, 144, 32, 32),
                    )
                ],
                560,
                144,
            )
        )

    def test_diagonal_anchor_up_mini_requires_strong_offset_anchor(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.07,
            border_score=0.15,
            center_score=0.0,
        )

        self.assertTrue(
            _is_diagonal_anchor_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.12),
                0.05,
                0.22,
            )
        )
        self.assertFalse(
            _is_diagonal_anchor_up_mini_spike_candidate(
                _PatchFeatures(
                    (),
                    edge_density=0.07,
                    border_score=0.15,
                    center_score=0.08,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.12),
                0.05,
                0.22,
            )
        )
        self.assertTrue(
            _has_diagonal_anchor_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_up",
                        OBJ_MINI_SPIKE_UP,
                        288,
                        528,
                        0.76,
                        Box(288, 528, 16, 16),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        288,
                        576,
                        0.88,
                        Box(288, 576, 32, 32),
                    ),
                ],
                272,
                560,
            )
        )
        self.assertFalse(
            _has_diagonal_anchor_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_up",
                        OBJ_MINI_SPIKE_UP,
                        288,
                        528,
                        0.76,
                        Box(288, 528, 16, 16),
                    )
                ],
                272,
                560,
            )
        )

    def test_low_contrast_paired_up_mini_requires_pair_and_support(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.09,
            border_score=0.08,
            center_score=0.11,
        )

        self.assertTrue(
            _is_low_contrast_paired_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.12),
                0.07,
                0.11,
            )
        )
        self.assertFalse(
            _is_low_contrast_paired_up_mini_spike_candidate(
                _PatchFeatures(
                    (),
                    edge_density=0.13,
                    border_score=0.08,
                    center_score=0.11,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.12),
                0.07,
                0.11,
            )
        )
        self.assertTrue(
            _has_low_contrast_paired_up_mini_spike_pair(
                {
                    (480, 272): 0.07,
                    (528, 272): 0.07,
                },
                480,
                272,
            )
        )
        self.assertFalse(
            _has_low_contrast_paired_up_mini_spike_pair(
                {
                    (480, 272): 0.07,
                    (512, 272): 0.07,
                },
                480,
                272,
            )
        )
        self.assertTrue(
            _has_low_contrast_paired_up_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        480,
                        288,
                        0.28,
                        Box(480, 288, 32, 32),
                    ),
                    Detection(
                        "spike_up",
                        OBJ_SPIKE_UP,
                        496,
                        256,
                        0.28,
                        Box(496, 256, 32, 32),
                    ),
                ],
                480,
                272,
            )
        )
        self.assertFalse(
            _has_low_contrast_paired_up_mini_spike_support(
                [
                    Detection(
                        "spike_up",
                        OBJ_SPIKE_UP,
                        496,
                        256,
                        0.28,
                        Box(496, 256, 32, 32),
                    )
                ],
                480,
                272,
            )
        )

    def test_low_border_side_mini_requires_sparse_block_support(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.09,
            border_score=0.05,
            center_score=0.12,
        )

        self.assertTrue(
            _is_low_border_side_mini_spike_patch(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.08),
                0.20,
            )
        )
        self.assertFalse(
            _is_low_border_side_mini_spike_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.09,
                    border_score=0.09,
                    center_score=0.12,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.08),
                0.20,
            )
        )
        self.assertTrue(_is_low_border_side_mini_spike_candidate(0.11))
        self.assertFalse(_is_low_border_side_mini_spike_candidate(0.09))
        self.assertTrue(
            _has_low_border_side_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        0,
                        128,
                        0.30,
                        Box(0, 128, 32, 32),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        32,
                        160,
                        0.30,
                        Box(32, 160, 32, 32),
                    ),
                    Detection(
                        "spike_right",
                        OBJ_SPIKE_RIGHT,
                        24,
                        128,
                        0.30,
                        Box(24, 128, 32, 32),
                    ),
                ],
                32,
                128,
                OBJ_MINI_SPIKE_RIGHT,
            )
        )
        self.assertFalse(
            _has_low_border_side_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        0,
                        128,
                        0.30,
                        Box(0, 128, 32, 32),
                    ),
                    Detection(
                        "spike_right",
                        OBJ_SPIKE_RIGHT,
                        24,
                        128,
                        0.30,
                        Box(24, 128, 32, 32),
                    ),
                ],
                32,
                128,
                OBJ_MINI_SPIKE_RIGHT,
            )
        )

    def test_ultra_faint_left_mini_requires_local_spike_and_block_layout(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.074,
            border_score=0.045,
            center_score=0.125,
        )

        self.assertTrue(
            _is_ultra_faint_left_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.08),
                0.01,
                -0.09,
                0.076,
            )
        )
        self.assertFalse(
            _is_ultra_faint_left_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.08),
                0.04,
                -0.09,
                0.076,
            )
        )
        self.assertTrue(
            _has_ultra_faint_left_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        80,
                        384,
                        0.30,
                        Box(80, 384, 32, 32),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        96,
                        416,
                        0.30,
                        Box(96, 416, 32, 32),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        96,
                        384,
                        0.30,
                        Box(96, 384, 32, 32),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        96,
                        448,
                        0.30,
                        Box(96, 448, 32, 32),
                    ),
                    Detection(
                        "spike_right",
                        OBJ_SPIKE_RIGHT,
                        64,
                        400,
                        0.30,
                        Box(64, 400, 32, 32),
                    ),
                    Detection(
                        "spike_left",
                        OBJ_SPIKE_LEFT,
                        88,
                        448,
                        0.30,
                        Box(88, 448, 32, 32),
                    ),
                ],
                80,
                416,
            )
        )
        self.assertFalse(
            _has_ultra_faint_left_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        96,
                        416,
                        0.30,
                        Box(96, 416, 32, 32),
                    ),
                    Detection(
                        "spike_right",
                        OBJ_SPIKE_RIGHT,
                        64,
                        400,
                        0.30,
                        Box(64, 400, 32, 32),
                    ),
                    Detection(
                        "spike_left",
                        OBJ_SPIKE_LEFT,
                        88,
                        448,
                        0.30,
                        Box(88, 448, 32, 32),
                    ),
                ],
                80,
                416,
            )
        )

    def test_block_accepts_weak_aligned_candidate(self) -> None:
        candidate = _GeometryPatchCandidate(
            64,
            96,
            _PatchFeatures((), edge_density=0.05, border_score=0.06, center_score=0.02),
            spike=None,
            block=_GeometryClass("block", OBJ_BLOCK, 0.28),
        )

        self.assertTrue(_accept_block(candidate))

    def test_block_rejects_weak_off_grid_candidate(self) -> None:
        candidate = _GeometryPatchCandidate(
            72,
            96,
            _PatchFeatures((), edge_density=0.05, border_score=0.06, center_score=0.02),
            spike=None,
            block=_GeometryClass("block", OBJ_BLOCK, 0.28),
        )

        self.assertFalse(_accept_block(candidate))

    def test_block_dedupe_prefers_aligned_candidate_over_shifted_neighbor(self) -> None:
        shifted = Detection("block", OBJ_BLOCK, 56, 96, 1.00, Box(56, 96, 32, 32))
        aligned = Detection("block", OBJ_BLOCK, 64, 96, 0.28, Box(64, 96, 32, 32))

        result = _dedupe_geometry([shifted, aligned])

        self.assertEqual([(det.x, det.y) for det in result], [(64, 96)])

    def test_block_dedupe_prefers_32px_alignment_over_16px_alignment(self) -> None:
        half_shifted = Detection("block", OBJ_BLOCK, 80, 96, 1.00, Box(80, 96, 32, 32))
        aligned_32 = Detection("block", OBJ_BLOCK, 96, 96, 0.30, Box(96, 96, 32, 32))

        result = _dedupe_geometry([half_shifted, aligned_32])

        self.assertEqual([(det.x, det.y) for det in result], [(96, 96)])

    def test_strong_block_can_coexist_with_color_anchor(self) -> None:
        water = Detection("water_2", OBJ_WATER_2, 224, 40, 0.50, Box(224, 40, 32, 32))
        strong_block = Detection("block", OBJ_BLOCK, 224, 32, 0.36, Box(224, 32, 32, 32))

        result = _dedupe_overlapping_geometry([water, strong_block])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_WATER_2, 224, 40),
            (OBJ_BLOCK, 224, 32),
        ])

    def test_very_weak_block_still_loses_to_color_anchor(self) -> None:
        water = Detection("water_2", OBJ_WATER_2, 224, 40, 0.50, Box(224, 40, 32, 32))
        weak_block = Detection("block", OBJ_BLOCK, 224, 32, 0.27, Box(224, 32, 32, 32))

        result = _dedupe_overlapping_geometry([water, weak_block])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_WATER_2, 224, 40),
        ])

    def test_block_still_loses_to_apple_anchor(self) -> None:
        apple = Detection("apple", OBJ_APPLE, 224, 40, 0.80, Box(224, 40, 32, 32))
        strong_block = Detection("block", OBJ_BLOCK, 224, 32, 0.80, Box(224, 32, 32, 32))

        result = _dedupe_overlapping_geometry([apple, strong_block])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_APPLE, 224, 40),
        ])

    def test_diagonally_overlapping_spike_loses_to_apple_anchor(self) -> None:
        apple = Detection("apple", OBJ_APPLE, 224, 40, 0.80, Box(224, 40, 32, 32))
        spike = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            208,
            24,
            0.80,
            Box(208, 24, 32, 32),
        )

        result = _dedupe_overlapping_geometry(
            [apple, spike],
            anchor_types=frozenset({OBJ_APPLE}),
        )

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_APPLE, 224, 40),
        ])

    def test_late_sprite_arbitration_does_not_treat_platform_as_anchor(self) -> None:
        platform = Detection(
            "platform", OBJ_PLATFORM, 224, 40, 0.80, Box(224, 40, 32, 16)
        )
        spike = Detection(
            "spike_up", OBJ_SPIKE_UP, 208, 24, 0.80, Box(208, 24, 32, 32)
        )

        result = _dedupe_overlapping_geometry(
            [platform, spike],
            anchor_types=frozenset({OBJ_APPLE}),
        )

        self.assertEqual(len(result), 2)

    def test_block_still_loses_to_save_anchor(self) -> None:
        save = Detection("save", OBJ_SAVE, 224, 40, 0.95, Box(224, 40, 32, 32))
        strong_block = Detection("block", OBJ_BLOCK, 224, 32, 0.80, Box(224, 32, 32, 32))

        result = _dedupe_overlapping_geometry([save, strong_block])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_SAVE, 224, 40),
        ])

    def test_half_overlapping_miniblock_can_coexist_with_save_anchor(self) -> None:
        save = Detection("save", OBJ_SAVE, 16, 176, 0.95, Box(16, 176, 32, 32))
        backing = Detection(
            "mini_block",
            OBJ_MINI_BLOCK,
            0,
            176,
            0.70,
            Box(0, 176, 16, 16),
        )

        result = _dedupe_overlapping_geometry([save, backing])

        self.assertEqual(
            [(det.type_id, det.x, det.y) for det in result],
            [(OBJ_SAVE, 16, 176), (OBJ_MINI_BLOCK, 0, 176)],
        )

    def test_half_overlapping_miniblock_can_coexist_with_warp_anchor(self) -> None:
        warp = Detection("warp", OBJ_WARP, 0, 352, 0.95, Box(0, 352, 32, 32))
        backing = Detection(
            "mini_block",
            OBJ_MINI_BLOCK,
            0,
            336,
            0.70,
            Box(0, 336, 16, 16),
        )

        result = _dedupe_overlapping_geometry([warp, backing])

        self.assertEqual(
            [(det.type_id, det.x, det.y) for det in result],
            [(OBJ_WARP, 0, 352), (OBJ_MINI_BLOCK, 0, 336)],
        )

    def test_strong_full_spike_can_coexist_with_water_anchor(self) -> None:
        water = Detection("water_2", OBJ_WATER_2, 720, 96, 0.60, Box(720, 96, 32, 32))
        strong_spike = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            720,
            96,
            0.49,
            Box(720, 96, 32, 32),
        )

        result = _dedupe_overlapping_geometry([water, strong_spike])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_WATER_2, 720, 96),
            (OBJ_SPIKE_DOWN, 720, 96),
        ])

    def test_weak_full_spike_still_loses_to_water_anchor(self) -> None:
        water = Detection("water_2", OBJ_WATER_2, 720, 96, 0.60, Box(720, 96, 32, 32))
        weak_spike = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            720,
            96,
            0.47,
            Box(720, 96, 32, 32),
        )

        result = _dedupe_overlapping_geometry([water, weak_spike])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_WATER_2, 720, 96),
        ])

    def test_full_spike_still_loses_to_save_anchor(self) -> None:
        save = Detection("save", OBJ_SAVE, 720, 96, 0.95, Box(720, 96, 32, 32))
        strong_spike = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            720,
            96,
            0.80,
            Box(720, 96, 32, 32),
        )

        result = _dedupe_overlapping_geometry([save, strong_spike])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_SAVE, 720, 96),
        ])

    def test_blocklike_spike_candidate_accepts_hollow_aligned_outline(self) -> None:
        candidate = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.12, border_score=0.16, center_score=0.0),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.26),
            block=_GeometryClass("block", OBJ_BLOCK, 0.15),
        )

        self.assertTrue(_is_blocklike_spike_candidate(candidate))

    def test_blocklike_spike_candidate_rejects_unclear_block_shape(self) -> None:
        high_center = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.12, border_score=0.16, center_score=0.04),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.26),
            block=_GeometryClass("block", OBJ_BLOCK, 0.15),
        )
        off_grid = _GeometryPatchCandidate(
            112,
            128,
            _PatchFeatures((), edge_density=0.12, border_score=0.16, center_score=0.0),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.26),
            block=_GeometryClass("block", OBJ_BLOCK, 0.15),
        )
        strong_spike = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.12, border_score=0.16, center_score=0.0),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.40),
            block=_GeometryClass("block", OBJ_BLOCK, 0.15),
        )

        self.assertFalse(_is_blocklike_spike_candidate(high_center))
        self.assertFalse(_is_blocklike_spike_candidate(off_grid))
        self.assertFalse(_is_blocklike_spike_candidate(strong_spike))

    def test_center_heavy_block_candidate_accepts_textured_block_shape(self) -> None:
        candidate = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.35, border_score=0.10, center_score=0.50),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45),
            block=_GeometryClass("block", OBJ_BLOCK, 0.32),
        )

        self.assertTrue(_is_center_heavy_block_candidate(candidate))

    def test_center_heavy_block_candidate_rejects_weak_or_off_grid_shape(self) -> None:
        weak_center = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.35, border_score=0.10, center_score=0.49),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45),
            block=_GeometryClass("block", OBJ_BLOCK, 0.32),
        )
        weak_block = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.35, border_score=0.10, center_score=0.50),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45),
            block=_GeometryClass("block", OBJ_BLOCK, 0.31),
        )
        off_grid = _GeometryPatchCandidate(
            100,
            128,
            _PatchFeatures((), edge_density=0.35, border_score=0.10, center_score=0.50),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45),
            block=_GeometryClass("block", OBJ_BLOCK, 0.32),
        )

        self.assertFalse(_is_center_heavy_block_candidate(weak_center))
        self.assertFalse(_is_center_heavy_block_candidate(weak_block))
        self.assertFalse(_is_center_heavy_block_candidate(off_grid))

    def test_block_run_gap_accepts_structural_neighbor_pairs(self) -> None:
        self.assertTrue(_is_block_run_gap(64, 96, {(32, 96), (96, 96)}))
        self.assertTrue(_is_block_run_gap(64, 96, {(64, 64), (64, 128)}))
        self.assertTrue(_is_block_run_gap(64, 96, {(32, 96), (64, 128)}))
        self.assertTrue(_is_block_run_gap(64, 96, {(32, 96), (0, 96)}))
        self.assertTrue(_is_block_run_gap(64, 96, {(32, 96)}))
        self.assertFalse(_is_block_run_gap(64, 96, set()))

    def test_block_run_gap_patch_accepts_strong_or_hollow_outline(self) -> None:
        strong_patch = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.02,
            center_score=0.10,
        )
        hollow_patch = _PatchFeatures(
            (),
            edge_density=0.06,
            border_score=0.04,
            center_score=0.0,
        )

        self.assertTrue(
            _accept_block_run_gap_patch(
                strong_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.12),
            )
        )
        self.assertTrue(
            _accept_block_run_gap_patch(
                hollow_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.04),
            )
        )

    def test_block_run_extension_accepts_hollow_outline_patch(self) -> None:
        hollow_patch = _PatchFeatures(
            (),
            edge_density=0.06,
            border_score=0.04,
            center_score=0.0,
        )

        self.assertTrue(
            _accept_block_run_gap_patch(
                hollow_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.04),
                "neighbor_extension",
            )
        )

    def test_nearby_hollow_block_recovery_requires_cluster_support(self) -> None:
        hollow_patch = _PatchFeatures(
            (),
            edge_density=0.06,
            border_score=0.04,
            center_score=0.0,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.04)

        self.assertTrue(
            _can_recover_nearby_hollow_block(hollow_patch, block, "cluster")
        )
        self.assertFalse(
            _can_recover_nearby_hollow_block(
                hollow_patch,
                block,
                "neighbor_extension",
            )
        )

    def test_nearby_hollow_block_recovery_rejects_center_heavy_patch(self) -> None:
        center_heavy_patch = _PatchFeatures(
            (),
            edge_density=0.06,
            border_score=0.04,
            center_score=0.03,
        )

        self.assertFalse(
            _can_recover_nearby_hollow_block(
                center_heavy_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.04),
                "cluster",
            )
        )

    def test_dark_outline_run_fill_patch_accepts_only_low_signal_interiors(self) -> None:
        low_signal = _PatchFeatures(
            (),
            edge_density=0.03,
            border_score=0.02,
            center_score=0.0,
        )
        textured = _PatchFeatures(
            (),
            edge_density=0.08,
            border_score=0.02,
            center_score=0.0,
        )
        border_heavy = _PatchFeatures(
            (),
            edge_density=0.03,
            border_score=0.07,
            center_score=0.0,
        )

        self.assertTrue(_is_dark_outline_block_run_fill_patch(low_signal))
        self.assertFalse(_is_dark_outline_block_run_fill_patch(textured))
        self.assertFalse(_is_dark_outline_block_run_fill_patch(border_heavy))

    def test_dark_outline_full_spike_candidate_uses_triangle_geometry(self) -> None:
        candidate = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.26,
            direction_margin=0.0,
            outline_delta=0.12,
        )
        weak_score = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.25,
            direction_margin=0.0,
            outline_delta=0.12,
        )
        weak_outline = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.26,
            direction_margin=0.0,
            outline_delta=0.11,
        )

        self.assertTrue(_is_dark_outline_full_spike_candidate(candidate))
        self.assertFalse(_is_dark_outline_full_spike_candidate(weak_score))
        self.assertFalse(_is_dark_outline_full_spike_candidate(weak_outline))

    def test_full_spike_side_coverage_rejects_a_single_edge_fragment(self) -> None:
        full_triangle = _up_outline_patch(
            edge_density=0.20,
            border_score=0.20,
            center_score=0.20,
        )
        base_only = [False] * 256
        for x in range(16):
            base_only[15 * 16 + x] = True
        fragment = _PatchFeatures(tuple(base_only), 0.06, 0.06, 0.0)

        self.assertGreaterEqual(_triangle_side_coverage(full_triangle, "up"), 0.45)
        self.assertLess(_triangle_side_coverage(fragment, "up"), 0.45)

    def test_dark_outline_half_step_full_spike_candidate_is_stricter(self) -> None:
        candidate = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.275,
            direction_margin=0.0,
            outline_delta=0.14,
        )
        weak_score = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.274,
            direction_margin=0.0,
            outline_delta=0.14,
        )
        weak_outline = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.275,
            direction_margin=0.0,
            outline_delta=0.13,
        )

        self.assertTrue(_is_dark_outline_half_step_full_spike_candidate(candidate))
        self.assertFalse(_is_dark_outline_half_step_full_spike_candidate(weak_score))
        self.assertFalse(_is_dark_outline_half_step_full_spike_candidate(weak_outline))

    def test_dark_outline_eight_step_candidate_combines_margin_and_block_score(
        self,
    ) -> None:
        spike = _GeometryClass(
            "spike_left",
            OBJ_SPIKE_LEFT,
            0.249,
            direction_margin=0.108,
            outline_delta=0.236,
        )
        patch = _PatchFeatures((), 0.172, 0.0, 0.0)

        self.assertTrue(
            _is_dark_outline_eight_step_full_spike_candidate(
                spike,
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.175),
                0.625,
            )
        )
        self.assertFalse(
            _is_dark_outline_eight_step_full_spike_candidate(
                spike,
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.19),
                0.625,
            )
        )

    def test_dark_outline_axial_support_requires_primary_anchor(self) -> None:
        image_box = Box(0, 0, 32, 32)
        primary = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            448,
            160,
            0.4,
            image_box,
        )
        provisional = Detection(
            "full_spike_support",
            OBJ_SPIKE_DOWN,
            448,
            160,
            0.4,
            image_box,
        )

        self.assertTrue(
            _has_dark_outline_axial_support(
                [primary],
                OBJ_SPIKE_DOWN,
                OBJ_SPIKE_DOWN,
                448,
                184,
                require_primary=True,
            )
        )
        self.assertFalse(
            _has_dark_outline_axial_support(
                [provisional],
                OBJ_SPIKE_DOWN,
                OBJ_SPIKE_DOWN,
                448,
                184,
                require_primary=True,
            )
        )

    def test_four_quadrant_block_support_requires_every_corner(self) -> None:
        image_box = Box(0, 0, 32, 32)
        blocks = [
            Detection("block", OBJ_BLOCK, x, y, 0.4, image_box)
            for x, y in ((84, 84), (116, 84), (84, 116), (116, 116))
        ]

        self.assertTrue(_has_four_quadrant_block_support(blocks, 100, 100))
        self.assertFalse(_has_four_quadrant_block_support(blocks[:-1], 100, 100))

    def test_full_spike_orientation_junction_rotates_support_pattern(self) -> None:
        image_box = Box(0, 0, 32, 32)
        supports = [
            Detection("spike_down", OBJ_SPIKE_DOWN, 100, 116, 0.4, image_box),
            Detection("spike_right", OBJ_SPIKE_RIGHT, 108, 84, 0.4, image_box),
            Detection("spike_left", OBJ_SPIKE_LEFT, 84, 84, 0.4, image_box),
        ]

        self.assertTrue(
            _forms_full_spike_orientation_junction(
                OBJ_SPIKE_UP,
                100,
                100,
                supports,
            )
        )
        self.assertFalse(
            _forms_full_spike_orientation_junction(
                OBJ_SPIKE_UP,
                100,
                100,
                supports[:-1],
            )
        )

    def test_supported_full_spike_candidate_requires_nonblock_triangle_body(self) -> None:
        spike = _GeometryClass(
            "spike_down",
            OBJ_SPIKE_DOWN,
            0.24,
            direction_margin=0.06,
            outline_delta=0.12,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.32)
        patch = _PatchFeatures(
            (),
            edge_density=0.18,
            border_score=0.08,
            center_score=0.28,
        )

        self.assertTrue(_is_supported_full_spike_candidate(spike, block, patch))
        self.assertFalse(
            _is_supported_full_spike_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.41),
                patch,
            )
        )
        self.assertFalse(
            _is_supported_full_spike_candidate(
                spike,
                block,
                _PatchFeatures(
                    (),
                    edge_density=0.18,
                    border_score=0.08,
                    center_score=0.10,
                ),
            )
        )

    def test_low_signal_supported_full_spike_requires_low_block_score(self) -> None:
        spike = _GeometryClass(
            "spike_down",
            OBJ_SPIKE_DOWN,
            0.18,
            direction_margin=0.02,
            outline_delta=0.08,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.16)
        patch = _PatchFeatures(
            (),
            edge_density=0.15,
            border_score=0.06,
            center_score=0.28,
        )

        self.assertTrue(
            _is_low_signal_supported_full_spike_candidate(spike, block, patch)
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.23),
                patch,
            )
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_candidate(
                _GeometryClass(
                    "spike_down",
                    OBJ_SPIKE_DOWN,
                    0.18,
                    direction_margin=0.0,
                    outline_delta=0.08,
                ),
                block,
                patch,
            )
        )

    def test_half_step_supported_full_spike_requires_low_block_score(self) -> None:
        spike = _GeometryClass(
            "spike_down",
            OBJ_SPIKE_DOWN,
            0.23,
            direction_margin=0.05,
            outline_delta=0.10,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.20)
        patch = _PatchFeatures(
            (),
            edge_density=0.20,
            border_score=0.08,
            center_score=0.28,
        )

        self.assertTrue(
            _is_half_step_supported_full_spike_candidate(spike, block, patch)
        )
        self.assertFalse(
            _is_half_step_supported_full_spike_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.23),
                patch,
            )
        )
        self.assertFalse(
            _is_half_step_supported_full_spike_candidate(
                _GeometryClass(
                    "spike_down",
                    OBJ_SPIKE_DOWN,
                    0.23,
                    direction_margin=0.04,
                    outline_delta=0.10,
                ),
                block,
                patch,
            )
        )

    def test_pale_outline_apple_room_requires_bright_low_saturation_room(self) -> None:
        self.assertTrue(_is_pale_outline_apple_room(_ColorProfile(230, 232, 231, 0.02)))
        self.assertFalse(_is_pale_outline_apple_room(_ColorProfile(150, 150, 150, 0.02)))
        self.assertFalse(_is_pale_outline_apple_room(_ColorProfile(230, 220, 180, 0.08)))

    def test_apple_contour_metrics_match_normalized_sprite_boundary(self) -> None:
        # The contour helper is deliberately independent of absolute color;
        # a perfect normalized boundary should score one in both directions.
        from jtool_scanner.scanner import APPLE_CONTOUR_TEMPLATE

        edge_mask = tuple(
            (x, y) in APPLE_CONTOUR_TEMPLATE
            for y in range(16)
            for x in range(16)
        )
        score, support, precision = _apple_contour_metrics(
            _PatchFeatures(edge_mask, 0.24, 0.05, 0.30)
        )
        self.assertAlmostEqual(score, 1.0)
        self.assertAlmostEqual(support, 1.0)
        self.assertAlmostEqual(precision, 1.0)

    def test_water_tinted_apple_patch_requires_compact_contour(self) -> None:
        weak = _PatchFeatures(
            tuple(True for _ in range(16 * 16)),
            edge_density=0.80,
            border_score=0.60,
            center_score=0.80,
        )
        self.assertFalse(
            _is_water_tinted_apple_patch(
                weak,
                support=0.95,
                precision=0.95,
            )
        )

    def test_red_apple_components_keep_close_clustered_sprites(self) -> None:
        centers = ((80, 112), (72, 128), (96, 128))
        components = []
        for center_x, center_y in centers:
            width, height = 16, 20
            box = Box(
                center_x - width // 2,
                center_y - height // 2,
                width,
                height,
            )
            components.append((box, [(box.x, box.y)] * 190))
        with mock.patch(
            "jtool_scanner.scanner._connected_components",
            return_value=components,
        ), mock.patch(
            "jtool_scanner.scanner._detect_outline_apples",
            return_value=[],
        ):
            detections = _detect_apples(
                RGBImage(800, 608, b"\x00" * (800 * 608 * 3)),
                Box(0, 0, 800, 608),
                8,
                [],
            )
        self.assertEqual(
            {(d.x, d.y) for d in detections},
            set(centers),
        )

    def test_outline_apple_component_uses_compact_shape_signal(self) -> None:
        candidate = Box(10, 20, 10, 4)
        features = _PatchFeatures(
            (),
            edge_density=0.28,
            border_score=0.17,
            center_score=0.46,
        )
        profile = _ColorProfile(240, 240, 240, 0.0)

        self.assertTrue(
            _is_outline_apple_component(candidate, 0.47, features, profile)
        )
        self.assertFalse(
            _is_outline_apple_component(
                Box(10, 20, 18, 4),
                0.47,
                features,
                profile,
            )
        )
        self.assertFalse(
            _is_outline_apple_component(
                candidate,
                0.47,
                _PatchFeatures(
                    (),
                    edge_density=0.12,
                    border_score=0.17,
                    center_score=0.46,
                ),
                profile,
            )
        )

    def test_fragmented_outline_apple_recovers_monochrome_irkara89_sprite(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "irkara-89-game.png")
        room = detect_room_box(image)
        anchors = _detect_saves(image, room, 8)

        apples = _detect_apples(image, room, 8, anchors)

        self.assertEqual(
            {(detection.x, detection.y) for detection in apples},
            {(128, 368)},
        )

    def test_fragmented_outline_apple_gate_requires_compact_contour(self) -> None:
        weak = _PatchFeatures(
            tuple(True for _ in range(16 * 16)),
            edge_density=0.80,
            border_score=0.60,
            center_score=0.80,
        )
        self.assertFalse(
            _is_fragmented_outline_apple_patch(
                weak,
                dark_density=0.10,
                contour_score=0.95,
                contour_support=0.95,
                contour_precision=0.95,
            )
        )

    def test_fragmented_outline_warp_rejects_wide_neutral_label_join(self) -> None:
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "block_spike"
        image = load_png(fixture_dir / "irkara-89-game.png")

        self.assertEqual(
            _detect_outline_warps(image, detect_room_box(image), 8),
            [],
        )

    def test_weak_room_corner_apple_requires_strong_positive_evidence(self) -> None:
        self.assertTrue(_is_weak_room_corner_apple(16, 8, 0.76))
        self.assertFalse(_is_weak_room_corner_apple(16, 8, 0.95))
        self.assertFalse(_is_weak_room_corner_apple(152, 472, 0.76))

    def test_compact_killer_tile_suppresses_overlapping_apple(self) -> None:
        box = Box(0, 0, 20, 20)
        killer = Detection("killer_block_cross", 18, 672, 352, 0.95, box)
        apple = Detection("apple", OBJ_APPLE, 688, 376, 0.85, box)

        self.assertEqual(
            _prune_apples_overlapping_killers([apple, killer], [killer]),
            [killer],
        )

    def test_edge_outline_block_patch_accepts_hollow_edge_tile(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.18,
            center_score=0.02,
        )

        self.assertTrue(_is_edge_outline_block_patch(patch))

    def test_edge_outline_block_patch_rejects_weak_or_center_heavy_tile(self) -> None:
        weak_edge = _PatchFeatures(
            (),
            edge_density=0.11,
            border_score=0.18,
            center_score=0.02,
        )
        weak_border = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.17,
            center_score=0.02,
        )
        center_heavy = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.18,
            center_score=0.03,
        )

        self.assertFalse(_is_edge_outline_block_patch(weak_edge))
        self.assertFalse(_is_edge_outline_block_patch(weak_border))
        self.assertFalse(_is_edge_outline_block_patch(center_heavy))

    def test_edge_weak_block_patch_accepts_low_signal_room_edge_tile(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.08,
            center_score=0.0,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.21)

        self.assertTrue(_is_edge_weak_block_patch(patch, block))

    def test_edge_weak_block_patch_rejects_weak_components(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.21)
        weak_block = _GeometryClass("block", OBJ_BLOCK, 0.20)
        weak_edge = _PatchFeatures(
            (),
            edge_density=0.11,
            border_score=0.08,
            center_score=0.0,
        )
        weak_border = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.07,
            center_score=0.0,
        )

        self.assertFalse(
            _is_edge_weak_block_patch(
                _PatchFeatures((), 0.12, 0.08, 0.0),
                weak_block,
            )
        )
        self.assertFalse(_is_edge_weak_block_patch(weak_edge, block))
        self.assertFalse(_is_edge_weak_block_patch(weak_border, block))

    def test_block_run_gap_patch_rejects_weak_noise(self) -> None:
        weak_patch = _PatchFeatures(
            (),
            edge_density=0.05,
            border_score=0.04,
            center_score=0.0,
        )

        self.assertFalse(
            _accept_block_run_gap_patch(
                weak_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.04),
            )
        )

    def test_final_right_mini_stack_candidate_requires_clear_direction(self) -> None:
        patch = _PatchFeatures((), 0.394, 0.33, 0.50)
        block = _GeometryClass("block", OBJ_BLOCK, 0.453)
        candidate = _GeometryClass(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            0.498,
            0.129,
            0.268,
        )

        self.assertTrue(
            _is_final_right_mini_stack_candidate(patch, block, candidate)
        )
        self.assertFalse(
            _is_final_right_mini_stack_candidate(
                patch,
                block,
                _GeometryClass(
                    "mini_spike_right",
                    OBJ_MINI_SPIKE_RIGHT,
                    0.498,
                    0.11,
                    0.268,
                ),
            )
        )

    def test_final_right_mini_stack_support_requires_opposed_pair(self) -> None:
        right = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            96,
            512,
            0.52,
            Box(96, 512, 16, 16),
        )
        left = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            48,
            528,
            0.70,
            Box(48, 528, 16, 16),
        )

        self.assertTrue(_has_final_right_mini_stack_support([right, left], 96, 528))
        self.assertFalse(_has_final_right_mini_stack_support([right], 96, 528))

    def test_final_right_mini_corridor_candidate_accepts_faint_shape(self) -> None:
        patch = _PatchFeatures((), 0.102, 0.054, 0.188)
        block = _GeometryClass("block", OBJ_BLOCK, 0.108)
        candidate = _GeometryClass(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            0.106,
            -0.003,
            0.053,
        )

        self.assertTrue(
            _is_final_right_mini_corridor_candidate(patch, block, candidate)
        )
        self.assertFalse(
            _is_final_right_mini_corridor_candidate(
                _PatchFeatures((), 0.14, 0.054, 0.188),
                block,
                candidate,
            )
        )

    def test_final_right_mini_corridor_support_requires_both_walls(self) -> None:
        full = Detection(
            "spike_right",
            OBJ_SPIKE_RIGHT,
            24,
            96,
            0.32,
            Box(24, 96, 32, 32),
        )
        left_wall = Detection("block", OBJ_BLOCK, 0, 128, 0.30, Box(0, 128, 32, 32))
        right_wall = Detection(
            "block",
            OBJ_BLOCK,
            96,
            128,
            0.30,
            Box(96, 128, 32, 32),
        )

        self.assertTrue(
            _has_final_right_mini_corridor_support(
                [full, left_wall, right_wall],
                32,
                128,
            )
        )
        self.assertFalse(
            _has_final_right_mini_corridor_support(
                [full, left_wall],
                32,
                128,
            )
        )

    def test_profiled_full_spike_noise_rejects_low_edge_candidate(self) -> None:
        detection = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            64,
            64,
            0.50,
            Box(64, 64, 32, 32),
        )

        self.assertTrue(
            _is_profiled_full_spike_noise(
                "solid_dense",
                detection,
                _PatchFeatures((), 0.14, 0.20, 0.20),
                0.50,
                0.30,
                0.75,
                0.20,
                0.0,
                0.0,
                64.0,
                64.0,
            )
        )

    def test_low_contrast_platform_candidate_requires_long_thin_enclosure(self) -> None:
        self.assertTrue(
            _is_low_contrast_platform_candidate(
                _PlatformPatchFeatures(28, 14, 85, 2),
                0.05,
                0.12,
            )
        )
        self.assertFalse(
            _is_low_contrast_platform_candidate(
                _PlatformPatchFeatures(32, 15, 127, 2),
                0.01,
                0.125,
                block_score=0.07,
            )
        )
        self.assertTrue(
            _is_low_contrast_platform_candidate(
                _PlatformPatchFeatures(32, 15, 127, 2),
                0.01,
                0.125,
                block_score=0.08,
            )
        )
        self.assertFalse(
            _is_low_contrast_platform_candidate(
                _PlatformPatchFeatures(23, 14, 85, 2),
                0.05,
                0.12,
            )
        )
        self.assertFalse(
            _is_low_contrast_platform_candidate(
                _PlatformPatchFeatures(28, 14, 120, 2),
                0.25,
                0.12,
            )
        )
        self.assertFalse(
            _is_low_contrast_platform_candidate(
                _PlatformPatchFeatures(28, 14, 85, 1),
                0.05,
                0.12,
            )
        )
        self.assertFalse(
            _is_low_contrast_platform_candidate(
                _PlatformPatchFeatures(28, 14, 85, 2),
                0.05,
                0.0,
            )
        )

    def test_low_contrast_platform_requires_complete_local_context(self) -> None:
        self.assertTrue(_has_complete_low_contrast_platform_context(32, 480))
        self.assertFalse(_has_complete_low_contrast_platform_context(16, 0))
        self.assertFalse(_has_complete_low_contrast_platform_context(0, 592))

    def test_full_spike_scale_arbitration_removes_contained_mini_fragments(self) -> None:
        full_spikes = [
            Detection(
                "spike_right",
                OBJ_SPIKE_RIGHT,
                320 if index == 0 else index * 32,
                256 if index == 0 else 0,
                0.75,
                Box(0, 0, 32, 32),
            )
            for index in range(20)
        ]
        minis = [
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                320,
                y,
                0.64,
                Box(0, 0, 16, 16),
            )
            for y in (256, 272)
        ]
        with (
            mock.patch(
                "jtool_scanner.scanner._patch_features",
                return_value=_PatchFeatures((), 0.25, 0.25, 0.25),
            ),
            mock.patch(
                "jtool_scanner.scanner._classify_full_spike",
                return_value=_GeometryClass(
                    "spike_right",
                    OBJ_SPIKE_RIGHT,
                    0.75,
                    0.40,
                    0.60,
                ),
            ),
        ):
            result = _arbitrate_full_spike_scale_duplicates(
                [*full_spikes, *minis],
                RGBImage(1, 1, b"\x00\x00\x00"),
                Box(0, 0, 1, 1),
            )

        self.assertFalse(
            any(detection.type_id in {OBJ_MINI_SPIKE_RIGHT} for detection in result)
        )
        self.assertEqual(
            sum(detection.type_id == OBJ_SPIKE_RIGHT for detection in result),
            20,
        )

    def test_full_spike_scale_arbitration_preserves_mini_dense_room(self) -> None:
        full_spikes = [
            Detection("spike_right", OBJ_SPIKE_RIGHT, index * 32, 0, 0.75, Box(0, 0, 32, 32))
            for index in range(20)
        ]
        minis = [
            Detection("mini_spike_right", OBJ_MINI_SPIKE_RIGHT, 320, index * 16, 0.64, Box(0, 0, 16, 16))
            for index in range(4)
        ]
        result = _arbitrate_full_spike_scale_duplicates(
            [*full_spikes, *minis],
            RGBImage(1, 1, b"\x00\x00\x00"),
            Box(0, 0, 1, 1),
        )
        self.assertEqual(result, [*full_spikes, *minis])

    def test_local_spike_scale_demotes_fragment_full_with_two_strong_minis(self) -> None:
        full = Detection(
            "spike_right", OBJ_SPIKE_RIGHT, 320, 256, 0.62, Box(0, 0, 32, 32)
        )
        minis = [
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                320,
                y,
                0.64,
                Box(0, 0, 16, 16),
            )
            for y in (256, 272)
        ]
        with (
            mock.patch(
                "jtool_scanner.scanner._native_edge_component_extent",
                return_value=18.0,
            ),
            mock.patch(
                "jtool_scanner.scanner._patch_features",
                return_value=_PatchFeatures((False,) * 256, 0.2, 0.2, 0.55),
            ),
            mock.patch(
                "jtool_scanner.scanner._classify_full_spike",
                return_value=_GeometryClass(
                    "spike_right", OBJ_SPIKE_RIGHT, 0.40, 0.12, 0.18
                ),
            ),
            mock.patch(
                "jtool_scanner.scanner._classify_mini_spike",
                return_value=_GeometryClass(
                    "mini_spike_right", OBJ_MINI_SPIKE_RIGHT, 0.72, 0.25, 0.35
                ),
            ),
            mock.patch("jtool_scanner.scanner._accept_mini_spike", return_value=True),
            mock.patch("jtool_scanner.scanner._triangle_side_coverage", return_value=1.0),
            mock.patch(
                "jtool_scanner.scanner._triangle_min_side_coverage", return_value=1.0
            ),
        ):
            result = _reconcile_local_spike_scale_conflicts(
                [full, *minis],
                minis,
                RGBImage(1, 1, b"\x00\x00\x00"),
                Box(0, 0, 1, 1),
            )

        self.assertNotIn(full, result)
        self.assertEqual(result, minis)

    def test_local_spike_scale_suppresses_weak_mini_inside_coherent_full(self) -> None:
        full = Detection(
            "spike_right", OBJ_SPIKE_RIGHT, 320, 256, 0.72, Box(0, 0, 32, 32)
        )
        mini = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            320,
            256,
            0.40,
            Box(0, 0, 16, 16),
        )

        def patch_features(_image, _room, _x, _y, size):
            return _PatchFeatures((False,) * (size * size), 0.2, 0.2, 0.2)

        def minimum_side(patch, _direction):
            return 1.0 if len(patch.edge_mask) == 32 * 32 else 0.5

        with (
            mock.patch(
                "jtool_scanner.scanner._native_edge_component_extent",
                return_value=30.0,
            ),
            mock.patch(
                "jtool_scanner.scanner._patch_features", side_effect=patch_features
            ),
            mock.patch(
                "jtool_scanner.scanner._classify_full_spike",
                return_value=_GeometryClass(
                    "spike_right", OBJ_SPIKE_RIGHT, 0.40, 0.20, 0.20
                ),
            ),
            mock.patch("jtool_scanner.scanner._triangle_side_coverage", return_value=1.0),
            mock.patch(
                "jtool_scanner.scanner._triangle_min_side_coverage",
                side_effect=minimum_side,
            ),
        ):
            result = _reconcile_local_spike_scale_conflicts(
                [full, mini],
                [mini],
                RGBImage(1, 1, b"\x00\x00\x00"),
                Box(0, 0, 1, 1),
            )

        self.assertEqual(result, [full])

    def test_local_spike_scale_preserves_independently_strong_overlap(self) -> None:
        full = Detection(
            "spike_right", OBJ_SPIKE_RIGHT, 320, 256, 0.72, Box(0, 0, 32, 32)
        )
        mini = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            320,
            256,
            0.72,
            Box(0, 0, 16, 16),
        )
        with (
            mock.patch(
                "jtool_scanner.scanner._native_edge_component_extent",
                return_value=30.0,
            ),
            mock.patch(
                "jtool_scanner.scanner._patch_features",
                return_value=_PatchFeatures((False,) * 1024, 0.2, 0.2, 0.65),
            ),
            mock.patch(
                "jtool_scanner.scanner._classify_full_spike",
                return_value=_GeometryClass(
                    "spike_right", OBJ_SPIKE_RIGHT, 0.60, 0.25, 0.35
                ),
            ),
            mock.patch("jtool_scanner.scanner._triangle_side_coverage", return_value=1.0),
            mock.patch(
                "jtool_scanner.scanner._triangle_min_side_coverage", return_value=1.0
            ),
        ):
            result = _reconcile_local_spike_scale_conflicts(
                [full, mini],
                [mini],
                RGBImage(1, 1, b"\x00\x00\x00"),
                Box(0, 0, 1, 1),
            )

        self.assertEqual(result, [full, mini])

    def test_filled_cloud_warp_metrics_accept_compressed_shape_not_terrain(self) -> None:
        metrics = {
            "map_width": 18.0,
            "map_height": 20.4,
            "fill": 0.749,
            "row_multi": 0.12,
            "column_multi": 0.136,
            "run_sum": 2.296,
            "center_fill": 1.0,
            "ring_share": 0.0,
        }
        self.assertTrue(
            _is_filled_cloud_warp_metrics(**metrics, silhouette_iou=0.828)
        )
        self.assertFalse(
            _is_filled_cloud_warp_metrics(**metrics, silhouette_iou=0.807)
        )
        self.assertFalse(
            _is_filled_cloud_warp_metrics(
                **{**metrics, "ring_share": 0.30}, silhouette_iou=0.90
            )
        )

    def test_filled_cloud_warp_dense_spike_enclosure_is_a_high_confidence_veto(self) -> None:
        patch = _PatchFeatures((False,) * 256, 0.4, 0.3, 0.3)
        strong_spike = _GeometryClass(
            "spike_up", OBJ_SPIKE_UP, 0.70, 0.30, 0.45
        )
        weak_spike = _GeometryClass(
            "spike_up", OBJ_SPIKE_UP, 0.20, 0.01, 0.02
        )
        with mock.patch(
            "jtool_scanner.scanner._patch_features", return_value=patch
        ), mock.patch(
            "jtool_scanner.scanner._classify_block",
            return_value=_GeometryClass("block", OBJ_BLOCK, 0.10),
        ), mock.patch(
            "jtool_scanner.scanner._classify_full_spike",
            side_effect=[strong_spike] * 5 + [weak_spike] * 3,
        ):
            self.assertTrue(
                _filled_cloud_warp_is_dense_spike_enclosure(
                    RGBImage(1, 1, b"\x00\x00\x00"),
                    Box(0, 0, 1, 1),
                    384,
                    224,
                )
            )

        with mock.patch(
            "jtool_scanner.scanner._patch_features", return_value=patch
        ), mock.patch(
            "jtool_scanner.scanner._classify_block",
            return_value=_GeometryClass("block", OBJ_BLOCK, 0.10),
        ), mock.patch(
            "jtool_scanner.scanner._classify_full_spike",
            side_effect=[strong_spike] * 4 + [weak_spike] * 4,
        ):
            self.assertFalse(
                _filled_cloud_warp_is_dense_spike_enclosure(
                    RGBImage(1, 1, b"\x00\x00\x00"),
                    Box(0, 0, 1, 1),
                    384,
                    224,
                )
            )

    def test_filled_cloud_warp_neutral_bright_shadow_is_ambiguous(self) -> None:
        neutral = RGBImage(23, 25, bytes((118, 118, 118)) * 23 * 25)
        chromatic = RGBImage(23, 25, bytes((100, 116, 132)) * 23 * 25)
        dark = RGBImage(23, 25, bytes((88, 88, 88)) * 23 * 25)

        self.assertTrue(
            _filled_cloud_warp_has_ambiguous_neutral_shadow(
                neutral,
                Box(0, 0, 23, 25),
            )
        )
        self.assertFalse(
            _filled_cloud_warp_has_ambiguous_neutral_shadow(
                chromatic,
                Box(0, 0, 23, 25),
            )
        )
        self.assertFalse(
            _filled_cloud_warp_has_ambiguous_neutral_shadow(
                dark,
                Box(0, 0, 23, 25),
            )
        )

    def test_filled_cloud_warp_low_shadow_background_contrast_is_ambiguous(self) -> None:
        width, height = 64, 64
        player_like = bytearray([85, 105, 75] * width * height)
        portal_like = bytearray([20, 28, 36] * width * height)
        for data in (player_like, portal_like):
            for y in range(20, 45):
                for x in range(20, 43):
                    offset = (y * width + x) * 3
                    data[offset : offset + 3] = bytes((255, 255, 255))
            for y in range(40, 45):
                for x in range(20, 43):
                    offset = (y * width + x) * 3
                    data[offset : offset + 3] = bytes((105, 105, 105))

        box = Box(20, 20, 23, 25)
        self.assertTrue(
            _filled_cloud_warp_shadow_is_background_like(
                RGBImage(width, height, bytes(player_like)),
                Box(0, 0, width, height),
                box,
            )
        )
        self.assertFalse(
            _filled_cloud_warp_shadow_is_background_like(
                RGBImage(width, height, bytes(portal_like)),
                Box(0, 0, width, height),
                box,
            )
        )

    def test_component_silhouette_iou_distinguishes_cloud_from_rectangle(self) -> None:
        template = (
            0x0104,
            0x07DE,
            0x1FFF,
            0x1FFF,
            0x3FFF,
            0x1FFE,
            0x3FFC,
            0x7FFC,
            0x7FFC,
            0x7FF8,
            0x7FF0,
            0x7FFC,
            0x7FFC,
            0x7FFE,
            0x7FFC,
            0x303C,
        )
        cloud_pixels = [
            (x, y)
            for y, row in enumerate(template)
            for x in range(16)
            if row & (1 << x)
        ]
        rectangle_pixels = [(x, y) for y in range(16) for x in range(16)]

        self.assertEqual(
            _component_silhouette_iou(Box(0, 0, 16, 16), cloud_pixels, template),
            1.0,
        )
        self.assertLess(
            _component_silhouette_iou(
                Box(0, 0, 16, 16), rectangle_pixels, template
            ),
            0.82,
        )

    def test_outline_cloud_warp_requires_contrasting_enclosure_and_return(self) -> None:
        metrics = {
            "map_width": 17.9,
            "map_height": 21.2,
            "fill": 0.743,
            "row_multi": 0.077,
            "column_multi": 0.136,
            "run_sum": 2.252,
            "center_fill": 1.0,
            "silhouette_iou": 0.816,
            "inner_ring_share": 0.341,
            "outer_ring_share": 0.852,
        }
        self.assertTrue(_is_outline_cloud_warp_metrics(**metrics))
        self.assertFalse(
            _is_outline_cloud_warp_metrics(
                **{**metrics, "outer_ring_share": 0.55}
            )
        )
        self.assertFalse(
            _is_outline_cloud_warp_metrics(
                **{**metrics, "inner_ring_share": 0.60}
            )
        )

    def test_outline_cloud_warp_rejects_neutral_bright_player_shadow(self) -> None:
        width, height = 64, 64
        image = RGBImage(width, height, bytes((118, 118, 118)) * width * height)
        box = Box(20, 20, 23, 25)
        pixels = [
            (x, y)
            for y in range(box.y, box.bottom)
            for x in range(box.x, box.right)
        ]
        metrics = {
            "map_width": 17.9,
            "map_height": 21.2,
            "fill": 0.743,
            "row_multi": 0.077,
            "column_multi": 0.136,
            "run_sum": 2.252,
            "center_fill": 1.0,
            "silhouette_iou": 0.816,
            "inner_ring_share": 0.341,
            "outer_ring_share": 0.852,
        }
        with mock.patch(
            "jtool_scanner.scanner._connected_components",
            return_value=[(box, pixels)],
        ), mock.patch(
            "jtool_scanner.scanner._cloud_warp_palettes",
            return_value=(("bright", lambda _r, _g, _b: True),),
        ), mock.patch(
            "jtool_scanner.scanner._is_outline_cloud_warp_metrics",
            return_value=True,
        ):
            self.assertEqual(
                _detect_outline_cloud_warps(image, Box(0, 0, width, height), 8),
                [],
            )

    def test_bright_platform_candidate_requires_empty_lower_half(self) -> None:
        features = _PlatformPatchFeatures(32, 16, 255)
        patch = _PatchFeatures((), 0.117, 0.268, 0.0)

        self.assertTrue(
            _is_bright_outline_platform_candidate(
                features,
                patch,
                block_score=0.215,
                below_edge=0.004,
            )
        )
        self.assertFalse(
            _is_bright_outline_platform_candidate(
                features,
                patch,
                block_score=0.215,
                below_edge=0.04,
            )
        )

    def test_textured_platform_candidate_requires_internal_luminance_ramp(self) -> None:
        patch = _PatchFeatures((), 0.223, 0.348, 0.125)

        self.assertTrue(
            _is_textured_platform_candidate(
                _PlatformPatchFeatures(31, 13, 157),
                patch,
                block_score=0.329,
                below_edge=0.012,
            )
        )
        self.assertFalse(
            _is_textured_platform_candidate(
                _PlatformPatchFeatures(32, 14, 89),
                patch,
                block_score=0.329,
                below_edge=0.012,
            )
        )

    def test_textured_platform_requires_horizontal_material_isolation(self) -> None:
        self.assertTrue(
            _is_textured_platform_horizontally_isolated(
                _textured_platform_isolation_test_image(continuous=False),
                Box(0, 0, 800, 608),
                320,
                256,
            )
        )
        self.assertFalse(
            _is_textured_platform_horizontally_isolated(
                _textured_platform_isolation_test_image(continuous=True),
                Box(0, 0, 800, 608),
                320,
                256,
            )
        )

    def test_isolated_textured_platform_survives_weak_terrain_contact(self) -> None:
        detection = Detection(
            "platform",
            OBJ_PLATFORM,
            320,
            256,
            0.8,
            Box(320, 256, 32, 16),
        )
        image = _textured_test_image()
        with mock.patch(
            "jtool_scanner.scanner._is_textured_platform_detection",
            return_value=True,
        ):
            self.assertFalse(
                _platform_conflicts_supported_terrain(
                    detection,
                    frozenset({(320, 256), (320, 224)}),
                    image,
                    Box(0, 0, 800, 608),
                )
            )
            self.assertTrue(
                _platform_conflicts_supported_terrain(
                    detection,
                    frozenset({
                        (320, 256),
                        (320, 224),
                        (288, 256),
                    }),
                    image,
                    Box(0, 0, 800, 608),
                )
            )


def _textured_test_image(width: int = 800, height: int = 608) -> RGBImage:
    data = bytearray()
    for y in range(height):
        for x in range(width):
            value = 255 if (x // 2 + y // 2) % 2 else 0
            data.extend((value, value, value))
    return RGBImage(width, height, bytes(data))


def _textured_platform_isolation_test_image(*, continuous: bool) -> RGBImage:
    width, height = 800, 608
    data = bytearray((20, 24, 32) * (width * height))
    left = 304 if continuous else 320
    right = 368 if continuous else 352
    for y in range(256, 272):
        shade = 70 + (y - 256) * 6
        for x in range(left, right):
            offset = (y * width + x) * 3
            data[offset : offset + 3] = bytes((shade, shade, shade))
    return RGBImage(width, height, bytes(data))


def _repeated_terrain_test_image(
    *,
    width: int = 800,
    height: int = 608,
    background: tuple[int, int, int] = (212, 72, 164),
    terrain: tuple[int, int, int] = (18, 86, 205),
) -> RGBImage:
    data = bytearray(background * (width * height))
    for block_y in (64, 96, 128):
        for block_x in (0, 32, 64, 96):
            for y in range(block_y, block_y + 32):
                start = (y * width + block_x) * 3
                data[start : start + 32 * 3] = bytes(terrain * 32)
    return RGBImage(width, height, bytes(data))


def _supported_cell_terrain_test_image(
    *,
    width: int = 800,
    height: int = 608,
    background: tuple[int, int, int] = (132, 166, 174),
    terrain: tuple[int, int, int] = (76, 45, 48),
) -> RGBImage:
    data = bytearray(background * (width * height))
    for block_y in (64, 96, 128):
        for block_x in (0, 32, 64, 96, 128, 160):
            for y in range(block_y, block_y + 32):
                start = (y * width + block_x) * 3
                data[start : start + 32 * 3] = bytes(terrain * 32)
    return RGBImage(width, height, bytes(data))


def _multi_material_supported_terrain_test_image(
    *,
    width: int = 800,
    height: int = 608,
    include_disconnected_decoration: bool = False,
) -> RGBImage:
    data = bytearray((132, 166, 174) * (width * height))
    materials = (
        ((0, 128), (76, 45, 48)),
        ((128, 192), (196, 166, 118)),
        ((192, 256), (24, 28, 61)),
        ((256, 272), (54, 132, 83)),
    )
    for (left, right), color in materials:
        for y in range(64, 192):
            start = (y * width + left) * 3
            data[start : start + (right - left) * 3] = bytes(
                color * (right - left)
            )
    if include_disconnected_decoration:
        for y in range(384, 448):
            start = (y * width + 512) * 3
            data[start : start + 64 * 3] = bytes((196, 166, 118) * 64)
    return RGBImage(width, height, bytes(data))


def _water_backed_miniblock_material_test_image(
    *,
    width: int = 800,
    height: int = 608,
    water_width: int = 16,
) -> RGBImage:
    data = bytearray((132, 166, 174) * (width * height))
    for y in range(64, 192):
        primary_start = (y * width) * 3
        data[primary_start : primary_start + 128 * 3] = bytes(
            (76, 45, 48) * 128
        )
        cyan_start = (y * width + 288) * 3
        data[cyan_start : cyan_start + water_width * 3] = bytes(
            (70, 180, 215) * water_width
        )
    return RGBImage(width, height, bytes(data))


def _coherent_water_field_material_test_image() -> RGBImage:
    width, height = 800, 608
    data = bytearray((132, 166, 174) * (width * height))
    for y in range(64, 192):
        for x in range(288, 320):
            color = (70, 180, 215) if (x + y) % 4 < 2 else (40, 145, 180)
            start = (y * width + x) * 3
            data[start : start + 3] = bytes(color)
    return RGBImage(width, height, bytes(data))


def _yellowless_save_lattice_test_image(*, dark_center: bool) -> RGBImage:
    width = height = 64
    data = bytearray((190, 190, 190) * (width * height))
    for left, top in ((16, 24), (34, 24), (16, 36), (34, 36)):
        for y in range(top, top + 6):
            start = (y * width + left) * 3
            data[start : start + 10 * 3] = bytes((180, 40, 40) * 10)
    if dark_center:
        for y in range(29, 36):
            start = (y * width + 27) * 3
            data[start : start + 7 * 3] = bytes((24, 24, 24) * 7)
    return RGBImage(width, height, bytes(data))


def _repeated_terrain_support_detections() -> list[Detection]:
    image_box = Box(0, 0, 1, 1)
    return [
        Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            x,
            32,
            0.9,
            image_box,
        )
        for x in (0, 32, 64)
    ]


def _up_outline_patch(
    *,
    edge_density: float,
    border_score: float,
    center_score: float,
) -> _PatchFeatures:
    edge_mask = [False] * 256
    outline, _outside = _triangle_masks("up")
    for position in outline:
        edge_mask[position] = True
    return _PatchFeatures(tuple(edge_mask), edge_density, border_score, center_score)


def _up_spike_test_image(
    targets: list[tuple[int, int]],
    width: int = 800,
    height: int = 608,
) -> RGBImage:
    data = bytearray([255] * (width * height * 3))
    for x, y in targets:
        for local_y in range(32):
            for local_x in range(32):
                side = abs(local_x - 15.5) * 2
                if local_y < side - 2:
                    continue
                value = 0 if (local_x // 2 + local_y // 2) % 2 else 255
                offset = ((y + local_y) * width + x + local_x) * 3
                data[offset : offset + 3] = bytes((value, value, value))
    return RGBImage(width, height, bytes(data))


def _mini_left_test_image(
    targets: list[tuple[int, int]],
    width: int = 800,
    height: int = 608,
) -> RGBImage:
    data = bytearray([255] * (width * height * 3))
    for x, y in targets:
        for local_y in range(16):
            for local_x in range(16):
                side = abs(local_y - 7.5) * 2
                if local_x < side - 1:
                    continue
                value = 0 if (local_x // 2 + local_y // 2) % 2 else 255
                offset = ((y + local_y) * width + x + local_x) * 3
                data[offset : offset + 3] = bytes((value, value, value))
    return RGBImage(width, height, bytes(data))


if __name__ == "__main__":
    unittest.main()
