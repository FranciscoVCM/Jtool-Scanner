"""Portable source evidence/explicit provenance; research is not app activation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_growth_confidence import (
    bounded_texture_parents, precision_aware_edge, qualify_independent_growth, qualify_source_roles,
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
    def apply(self, keys, *, existing=(), sizing=(), joint=(), retired=(), phase=(), roles=(), libraries=()):
        return qualify_independent_growth(keys, existing, sizing=sizing, sizing_retired=retired,
            joint_cells=joint, phase_positive=phase, calibrations=roles, room=Box(0, 0, 800, 608),
            original_texture_libraries=libraries)

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
