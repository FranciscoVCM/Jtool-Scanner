"""Portable source evidence/explicit provenance; research is not app activation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_growth_confidence import (
    OriginalForegroundQuery, bounded_texture_parents, precision_aware_edge,
    qualify_independent_growth, qualify_source_roles,
)
from scripts.source_material_evidence import SourceRectangles


POINTS = ((160, 128), (208, 128), (256, 128))


def field(background=(20, 40, 70), foreground=(80, 170, 210), scale=1):
    image = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(image)
    for x, y in POINTS:
        draw.rectangle((x, y, x+15, y+15), fill=foreground)
    if scale != 1:
        image = image.resize((round(800*scale), round(608*scale)), Image.Resampling.BILINEAR)
    return SourceRectangles(RGBImage(image.width, image.height, image.tobytes()),
                            Box(0, 0, image.width, image.height))


def role_proof(points=POINTS):
    return [dict(label=1, original_source_geometry=[dict(native=list(p), raw_faces=[12]*4) for p in points],
                 independent_color_roles=[dict(foreground=0, background=2)])]


class PrecisionRoleTests(TestCase):
    def test_true_rectangle_roles_keep_original_evidence_unchanged(self):
        selected, proof = {0}, role_proof()
        snapshot = deepcopy((selected, proof))
        approved, qualified, observations = qualify_source_roles(field(), selected, proof, ())
        self.assertEqual(approved, {0, 1})
        self.assertEqual(len(qualified[0]['original_source_geometry']), 3)
        self.assertTrue(observations[0]['passed'])
        self.assertEqual((selected, proof), snapshot)

    def test_rgb_permutation_polarity_brightness_and_isoluminant_edges(self):
        palettes = [((20, 40, 70), (80, 170, 210)), ((90, 20, 35), (180, 130, 65)),
                    ((80, 120, 40), (150, 80, 65))]
        transforms = (lambda c: c, lambda c: (c[2], c[0], c[1]),
                      lambda c: tuple(255-v for v in c), lambda c: tuple(round(v*.25) for v in c))
        for bg, fg in palettes:
            for transform in transforms:
                with self.subTest(bg=bg, transform=transform):
                    self.assertEqual(qualify_source_roles(field(transform(bg), transform(fg)), {0}, role_proof(), ())[0], {0, 1})

    def test_unknown_weak_duplicate_or_nonterrain_contaminated_witness_cannot_teach(self):
        cases = [(field(), role_proof(((0, 128), *POINTS[:2])), ()),
                 (field((20, 20, 20), (22, 22, 22)), role_proof(), ()),
                 (field(), role_proof((POINTS[0],)*3), ()),
                 (field(), role_proof(), (SimpleNamespace(type_id=12, image_box=Box(160, 128, 32, 32)),))]
        for source, proof, originals in cases:
            self.assertEqual(qualify_source_roles(source, {0}, proof, originals)[:2], ({0}, []))

    def test_physical_scale_and_half_scale_uncertainty(self):
        for scale in (1., 1.25, 1.5):
            self.assertEqual(qualify_source_roles(field(scale=scale), {0}, role_proof(), ())[0], {0, 1})
        self.assertEqual(qualify_source_roles(field(scale=.5), {0}, role_proof(), ())[0], {0})

    def test_rgb_gradient_is_not_a_teacher_but_real_tiles_on_it_remain(self):
        for tiles in (False, True):
            pixels = bytearray()
            for y in range(608):
                for x in range(800):
                    rgb = (round(20+.13*x+.04*y), round(60+.06*x+.11*y), round(170-.09*x-.04*y))
                    if tiles and any(px <= x < px+16 and py <= y < py+16 for px, py in POINTS):
                        rgb = tuple(v+change for v, change in zip(rgb, (40, 30, -30)))
                    pixels.extend(rgb)
            for inverse in (False, True):
                data = bytes(255-v for v in pixels) if inverse else bytes(pixels)
                source = SourceRectangles(RGBImage(800, 608, data), Box(0, 0, 800, 608))
                with self.subTest(tiles=tiles, inverse=inverse):
                    approved, _, _ = qualify_source_roles(source, {0}, role_proof(), ())
                    self.assertEqual(approved, {0, 1} if tiles else {0})

    def test_physical_padding_and_crop_origin_preserve_entire_edge_evidence(self):
        source = field(scale=1.25)
        original = Image.frombytes('RGB', (source.image.width, source.image.height), source.image.data)
        padded = Image.new('RGB', (original.width+29, original.height+23), (247, 3, 99))
        padded.paste(original, (11, 7))
        shifted = SourceRectangles(RGBImage(padded.width, padded.height, padded.tobytes()),
                                   Box(11, 7, original.width, original.height))
        for x, y in POINTS:
            first, second = (x, y), (x+16, y)
            self.assertEqual(precision_aware_edge(source, first, second),
                             precision_aware_edge(shifted, first, second))

    def test_context_owned_edge_memo_reuses_values_but_not_other_fields(self):
        cache = {}
        good, flat = field(), field((20, 20, 20), (20, 20, 20))
        first = qualify_source_roles(good, {0}, role_proof(), (), edge_memo=cache)
        count = len(cache)
        self.assertEqual(first, qualify_source_roles(good, {0}, role_proof(), (), edge_memo=cache))
        self.assertEqual(len(cache), count)
        self.assertEqual(qualify_source_roles(flat, {0}, role_proof(), (), edge_memo=cache)[0], {0})

    def test_independent_parallel_sources_equal_serial_without_global_patches(self):
        sources = [field(), field((30, 30, 30), (30, 30, 30))]
        compute = lambda source: qualify_source_roles(source, {0}, role_proof(), ())
        serial = list(map(compute, sources))
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(compute, sources)), serial)

    def test_returned_proofs_cannot_mutate_source_witnesses_or_edge_memo(self):
        source, proof, cache = field(), role_proof(), {}
        before = deepcopy(proof)
        expected = qualify_source_roles(source, {0}, proof, (), edge_memo=cache)
        actual = qualify_source_roles(source, {0}, proof, (), edge_memo=cache)
        actual[1][0]['original_source_geometry'][0]['native'][0] = -100
        actual[2][0]['qualified_witnesses'][0]['precision_aware_faces'][0]['support'] = 0
        self.assertEqual(proof, before)
        self.assertEqual(qualify_source_roles(source, {0}, proof, (), edge_memo=cache), expected)

    def test_degenerate_edge_is_rejected_and_capture_edge_unknown(self):
        source = field()
        with self.assertRaises(ValueError):
            precision_aware_edge(source, (4, 4), (4, 4))
        self.assertTrue(precision_aware_edge(source, (0, 128), (0, 144))['unknown'])


class IndependentGrowthTests(TestCase):
    def apply(self, keys, *, existing=(), sizing=(), joint=(), retired=(), phase=(), roles=(), libraries=(), queries=()):
        return qualify_independent_growth(keys, existing, sizing=sizing, sizing_retired=retired,
            joint_cells=joint, phase_positive=phase, calibrations=roles, room=Box(0, 0, 800, 608),
            original_texture_libraries=libraries, original_foreground_queries=queries)

    def test_only_new_sizing_or_joint_terrain_is_qualified(self):
        full, mini, unrelated, spike, marker = (1, 32, 32), (2, 96, 32), (2, 128, 32), (3, 160, 32), (12, 192, 32)
        keys = {full, mini, unrelated, spike, marker}
        snapshot = keys.copy()
        result, diag = self.apply(keys, sizing={full}, joint={(96, 32)})
        self.assertEqual(result, {unrelated, spike, marker})
        self.assertEqual(set(diag['held']), {full, mini})
        self.assertEqual(keys, snapshot)

    def test_existing_required_replacements_and_positive_phase_keys_are_preserved(self):
        existing, replacement, phase = (2, 32, 32), (2, 96, 32), (1, 160, 32)
        keys = {existing, replacement, phase}
        self.assertEqual(self.apply(keys, existing={existing}, sizing=keys,
                                    retired={(1, 96, 32)}, phase={phase})[0], keys)

    def test_full_needs_four_known_source_cells_mini_needs_one(self):
        full, mini = (1, 32, 32), (2, 96, 32)
        labels = {(32, 32): 0, (48, 32): 0, (32, 48): 0, (96, 32): 0}
        roles = [dict(labels=labels, approved={0})]
        self.assertEqual(self.apply({full, mini}, sizing={full}, joint={(96, 32)}, roles=roles)[0], {mini})
        labels[48, 48] = 0
        self.assertEqual(self.apply({full, mini}, sizing={full}, joint={(96, 32)}, roles=roles)[0], {full, mini})

    def test_original_texture_is_query_only_and_not_called_for_qualified_role(self):
        class Texture:
            def __init__(self):
                self.calls = []
            def support(self, x, y):
                self.calls.append((x, y))
                return dict(passed=True, original_teachers_only=True)
        library = Texture()
        mini = (2, 32, 32)
        result, diag = self.apply({mini}, joint={(32, 32)}, libraries=[library])
        self.assertEqual(result, {mini})
        self.assertEqual(library.calls, [(16, 16), (16, 32), (32, 16), (32, 32)])
        self.assertTrue(diag['proof'][0]['texture_is_query_only'])
        library.calls.clear()
        self.apply({mini}, joint={(32, 32)}, libraries=[library],
                   roles=[dict(labels={(32, 32): 0}, approved={0})])
        self.assertEqual(library.calls, [])

    def test_texture_diagnostics_cannot_mutate_the_original_library(self):
        class Texture:
            def __init__(self):
                self.result = dict(passed=True, source_teachers=[[64, 64]])
            def support(self, x, y):
                return self.result
        library, mini = Texture(), (2, 32, 32)
        _, diag = self.apply({mini}, joint={(32, 32)}, libraries=[library])
        diag['proof'][0]['original_full_texture'][0]['source_teachers'].clear()
        self.assertEqual(library.result['source_teachers'], [[64, 64]])

    def test_containing_parent_frames_require_real_physical_margin(self):
        self.assertEqual(bounded_texture_parents((2, 0, 0), Box(0, 0, 800, 608)), [])
        self.assertEqual(bounded_texture_parents((2, 16, 16), Box(0, 0, 800, 608)), [(16, 16)])
        self.assertEqual(bounded_texture_parents((2, 32, 32), None), [])
        self.assertEqual(bounded_texture_parents((2, 32, 32), Box(0, 0, 1, 1)), [])
        self.assertEqual(bounded_texture_parents((1, 0, 0), None), [(0, 0)])
        with self.assertRaises(ValueError):
            bounded_texture_parents((3, 32, 32), Box(0, 0, 800, 608))

    def test_additive_original_rgb_can_corroborate_full_without_exact_role_ids(self):
        key, query = (1, 32, 32), foreground_query(size=32)
        result, diag = self.apply({key}, sizing={key}, queries=[query])
        self.assertEqual(result, {key})
        self.assertFalse(diag['proof'][0]['qualified_source_roles'])
        self.assertTrue(diag['proof'][0]['original_foreground_positive'])

    def test_one_positive_quarter_cannot_corroborate_a_whole_full_block(self):
        full, mini, query = (1, 32, 32), (2, 32, 32), foreground_query()
        self.assertEqual(self.apply({full, mini}, sizing={full}, joint={(32, 32)}, queries=[query])[0], {mini})

    def test_unknown_query_cannot_claim_positive_even_with_an_inconsistent_pass_flag(self):
        query = SimpleNamespace(support=lambda *a: dict(passed=True, unknown=True))
        key = (2, 32, 32)
        self.assertEqual(self.apply({key}, joint={(32, 32)}, queries=[query])[0], set())


QUERY_BG, QUERY_FG, QUERY_HIGHLIGHT = (20, 40, 70), (150, 160, 180), (175, 184, 202)


def foreground_query(color=QUERY_HIGHLIGHT, *, transform=lambda c: c, background_pixels=0, scale=1, size=16):
    image = Image.new('RGB', (800, 608), transform(QUERY_BG))
    ImageDraw.Draw(image).rectangle((32, 32, 32+size-1, 32+size-1), fill=transform(color))
    for i in range(background_pixels):
        image.putpixel((36+i%8, 36+i//8), transform(QUERY_BG))
    if scale != 1:
        image = image.resize((round(800*scale), round(608*scale)), Image.Resampling.BILINEAR)
    source = SimpleNamespace(image=RGBImage(image.width, image.height, image.tobytes()),
                             room=Box(0, 0, image.width, image.height))
    return OriginalForegroundQuery(source, {1}, [transform(QUERY_BG), transform(QUERY_FG)], {0: 5}, {0: 0})


class OriginalForegroundTests(TestCase):
    def test_brighter_highlight_passes_without_exact_cluster_identity(self):
        proof = foreground_query().support(32, 32)
        self.assertTrue(proof['passed'])
        self.assertEqual(proof['foreground_fraction'], 1.)
        self.assertLessEqual(proof['mean_error'], proof['unchanged_mean_limit'])
        self.assertTrue(proof['query_only_no_new_teacher'])

    def test_background_and_excessive_mean_distance_are_not_positive(self):
        self.assertFalse(foreground_query(QUERY_BG).support(32, 32)['passed'])
        self.assertFalse(foreground_query((255, 255, 255)).support(32, 32)['passed'])

    def test_original_fraction_threshold_is_not_relaxed(self):
        self.assertTrue(foreground_query(background_pixels=3).support(32, 32)['passed'])
        self.assertFalse(foreground_query(background_pixels=4).support(32, 32)['passed'])

    def test_channel_permutation_polarity_and_brightness(self):
        transforms = (lambda c: c, lambda c: (c[2], c[0], c[1]),
                      lambda c: tuple(255-v for v in c), lambda c: tuple(round(v*.5) for v in c))
        for transform in transforms:
            self.assertTrue(foreground_query(transform=transform).support(32, 32)['passed'])
            self.assertFalse(foreground_query(QUERY_BG, transform=transform).support(32, 32)['passed'])

    def test_isoluminant_background_and_material_still_use_original_rgb(self):
        background, foreground, highlight = (80, 120, 40), (150, 80, 65), (155, 85, 70)
        luminance = lambda color: Image.new('RGB', (1, 1), color).convert('L').getpixel((0, 0))
        self.assertEqual(luminance(background), luminance(foreground))
        image = Image.new('RGB', (800, 608), background)
        ImageDraw.Draw(image).rectangle((32, 32, 47, 47), fill=highlight)
        source = SimpleNamespace(image=RGBImage(800, 608, image.tobytes()), room=Box(0, 0, 800, 608))
        query = OriginalForegroundQuery(source, {1}, [background, foreground], {0: 5}, {})
        self.assertTrue(query.support(32, 32)['passed'])
        self.assertFalse(query.support(64, 64)['passed'])

    def test_identical_foreground_background_is_unknown_not_positive(self):
        source = foreground_query().field
        query = OriginalForegroundQuery(source, {1}, [QUERY_BG, QUERY_BG], {0: 5}, {})
        proof = query.support(32, 32)
        self.assertTrue(proof['unknown'])
        self.assertFalse(proof['passed'])

    def test_original_physical_sampling_at_fractional_capture_scales(self):
        for scale in (.75, 1., 1.25, 1.5):
            self.assertTrue(foreground_query(scale=scale).support(32, 32)['passed'])

    def test_unknown_coverage_and_missing_calibration_never_pass(self):
        query = foreground_query()
        for point in ((-16, 32), (800, 32), (32, 608)):
            proof = query.support(*point)
            self.assertTrue(proof['unknown'])
            self.assertFalse(proof['passed'])
        missing = OriginalForegroundQuery(query.field, set(), [QUERY_BG, QUERY_FG], {0: 5}, {})
        self.assertFalse(missing.support(32, 32)['passed'])
        self.assertTrue(missing.support(32, 32)['unknown'])

    def test_returned_proof_cannot_poison_cached_source_answers(self):
        query = foreground_query()
        expected = query.support(32, 32)
        actual = query.support(32, 32)
        actual['native'][0] = -100
        actual['passed'] = False
        self.assertEqual(query.support(32, 32), expected)

    def test_image_or_frame_mutation_rejects_even_a_cached_result(self):
        for mutate in ('data', 'room', 'dimensions'):
            query = foreground_query()
            query.support(32, 32)
            if mutate == 'data':
                query.field.image.data = bytes(len(query.field.image.data))
            elif mutate == 'room':
                query.field.room = Box(0, 0, 768, 608)
            else:
                query.field.image.width -= 1
            with self.assertRaises(ValueError):
                query.support(32, 32)

    def test_independent_parallel_source_queries_match_serial(self):
        sources = [foreground_query(), foreground_query(QUERY_BG)]
        compute = lambda query: query.support(32, 32)
        expected = list(map(compute, sources))
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(compute, sources)), expected)

    def test_invalid_native_origins_are_not_truncated_into_source(self):
        query = foreground_query()
        for point in ((True, 32), (32.5, 32), (32, float('nan'))):
            with self.assertRaises(ValueError):
                query.support(*point)

    def test_mutating_input_palette_and_votes_cannot_change_a_query(self):
        source = foreground_query().field
        colors, approved, tips, backs = [list(QUERY_BG), list(QUERY_FG)], {1}, {0: 5}, {0: 0}
        query = OriginalForegroundQuery(source, approved, colors, tips, backs)
        colors[1][:] = (0, 0, 0)
        approved.clear()
        tips.clear()
        backs[0] = 100
        self.assertTrue(query.support(32, 32)['passed'])
