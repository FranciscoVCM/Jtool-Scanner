"""Portable positive-identity/abstention tests; the observer never deletes."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_glyph_prototypes import _contains
from scripts.source_repeated_identity import _components, repeated_material_support
from scripts.source_sampling import SourceFrame


def detection(x, y, type_id=1, kind='repeated_terrain_block'):
    return SimpleNamespace(type_id=type_id, x=x, y=y, kind=kind)


def scene(transform=lambda c: c, scale=1):
    raster = Image.new('RGB', (800, 608), transform((20, 30, 60)))
    draw = ImageDraw.Draw(raster)
    for x, y in ((128, 128), (160, 128), (256, 224)):
        draw.rectangle((x, y, x + 31, y + 31), fill=transform((210, 150, 70)))
        draw.rectangle((x, y, x + 31, y + 31), outline=transform((90, 50, 10)), width=2)
    if scale != 1:
        raster = raster.resize((round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR)
    image = RGBImage(raster.width, raster.height, raster.tobytes())
    return image, Box(0, 0, image.width, image.height)


class SourceRepeatedIdentityTests(TestCase):
    def test_no_profile_locators_do_not_build_source_evidence(self):
        image, room = scene()
        with patch('scripts.source_repeated_identity.SourceFrame', side_effect=AssertionError('No work')):
            proof = repeated_material_support(image, room, [detection(128, 128, kind='block')])
        self.assertEqual(proof['components'], [])
        self.assertEqual(proof['unsupported_known'], [])

    def test_components_connect_mixed_phases_but_not_single_corners(self):
        groups = list(_components(((32, 32), (64, 48), (80, 48), (112, 80))))
        self.assertEqual(groups, [((32, 32), (64, 48), (80, 48)), ((112, 80),)])

    def test_intrinsic_objects_and_separate_flat_impostor(self):
        image, room = scene()
        originals = [detection(128, 128), detection(160, 128), detection(256, 224), detection(416, 320)]
        before = deepcopy(originals)
        proof = repeated_material_support(image, room, iter(originals))
        self.assertEqual(proof['unsupported_known'], [(1, 416, 320)])
        self.assertEqual(originals, before)
        self.assertTrue(proof['unsupported_is_NOT_empty_background'])
        self.assertTrue(proof['no_objects_changed'])

    def test_palette_polarity_channels_brightness_fractional_capture(self):
        variants = ((lambda c: c, 1), (lambda c: tuple(255-v for v in c), 1),
                    (lambda c: (c[2], c[0], c[1]), 1),
                    (lambda c: tuple(round(v*.35) for v in c), 1), (lambda c: c, 1.25))
        for transform, scale in variants:
            with self.subTest(scale=scale, transform=transform):
                image, room = scene(transform, scale)
                proof = repeated_material_support(image, room, [detection(128, 128), detection(416, 320)])
                self.assertEqual(proof['unsupported_known'], [(1, 416, 320)])
                self.assertEqual(proof['components'][0]['disposition'], 'supported-intrinsic')

    def test_clipped_source_context_is_abstention_not_empty(self):
        image, room = scene()
        proof = repeated_material_support(image, room, [detection(0, 160)])
        self.assertEqual(proof['unsupported_known'], [])
        self.assertEqual(proof['components'][0]['disposition'], 'abstain-unknown-source')

    def test_unknown_member_keeps_entire_connected_structure_uncertain(self):
        image, room = scene()
        proof = repeated_material_support(image, room, [detection(0, 160), detection(32, 160)])
        self.assertEqual(proof['unsupported_known'], [])
        self.assertEqual(len(proof['components'][0]['members']), 2)

    def test_original_markers_cannot_be_evidence_for_deletion(self):
        image, room = scene()
        for kind in (11, 12, 14, 16, 19, 20, 22):
            with self.subTest(kind=kind):
                proof = repeated_material_support(image, room, [detection(416, 320), detection(424, 320, kind, 'marker')])
                self.assertEqual(proof['unsupported_known'], [])
                self.assertEqual(proof['components'][0]['disposition'], 'abstain-original-marker-overlap')

    def test_minis_and_other_full_origins_are_not_profile_members(self):
        image, room = scene()
        proof = repeated_material_support(image, room, [detection(416, 320, 2), detection(128, 128, kind='block')])
        self.assertEqual(proof['components'], [])

    def test_world_extent_is_not_silently_remapped(self):
        image, room = scene()
        frame = SourceFrame(image, room, extent=Box(-8, 0, 816, 608), canonical=image)
        proof = repeated_material_support(image, room, [detection(416, 320)], source_frame=frame)
        self.assertEqual(proof['unsupported_known'], [])
        self.assertIn('not qualified', proof['abstained'])

    def test_mismatched_original_context_fails(self):
        image, room = scene()
        context = SourceEvidenceContext(image, room, [])
        changed = RGBImage(image.width, image.height, bytes(reversed(image.data)))
        with self.assertRaises(ValueError):
            repeated_material_support(changed, room, [detection(416, 320)], source_context=context)

    def test_mismatched_frame_fails(self):
        image, room = scene()
        changed = RGBImage(image.width, image.height, bytes(reversed(image.data)))
        with self.assertRaises(ValueError):
            repeated_material_support(changed, room, [detection(416, 320)], source_frame=SourceFrame(image, room))

    def test_intrinsic_positive_short_circuits_expensive_channels(self):
        image, room = scene()
        context = SourceEvidenceContext(image, room, [])
        with patch.object(context, 'contours', side_effect=AssertionError('No contour work')):
            with patch.object(context, 'glyph_library', side_effect=AssertionError('No appearance work')):
                proof = repeated_material_support(image, room, [detection(128, 128)], source_context=context)
        self.assertEqual(proof['components'][0]['disposition'], 'supported-intrinsic')

    def test_real_rectangle_is_independent_of_intrinsic_score(self):
        image, room = scene()
        with patch('scripts.source_repeated_identity.scanner._classify_block',
                   return_value=SimpleNamespace(score=0)):
            proof = repeated_material_support(image, room, [detection(256, 224)])
        self.assertEqual(proof['unsupported_known'], [])
        self.assertEqual(proof['components'][0]['disposition'], 'supported-rectangle')

    def backing_scene(self, copies=False):
        raster = Image.new('RGB', (800, 608), (20, 30, 60))
        draw = ImageDraw.Draw(raster)
        poses = [(3, 160, 128), (3, 288, 128), (3, 416, 128)]
        for kind, x, y in poses:
            draw.rectangle((x, y + 32, x + 31, y + 63), fill=(130, 90, 30))
            poly = [(x + u, y + v) for u, v in VERTICES[kind]]
            for py in range(y, y + 32):
                for px in range(x, x + 32):
                    if _contains(poly, px + .5, py + .5):
                        draw.point((px, py), fill=(210, 150, 70))
        image = RGBImage(800, 608, raster.tobytes())
        teachers = [detection(x, y, kind, 'spike') for kind, x, y in poses]
        if copies:
            teachers = [deepcopy(teachers[0]) for _ in range(3)]
        return image, Box(0, 0, 800, 608), [detection(160, 160), *teachers]

    def test_real_original_backing_channel_uses_source_models(self):
        image, room, originals = self.backing_scene()
        before = deepcopy(originals)
        with patch('scripts.source_repeated_identity.scanner._classify_block',
                   return_value=SimpleNamespace(score=0)):
            with patch('scripts.source_repeated_identity._closed_rectangle', return_value=None):
                proof = repeated_material_support(image, room, originals)
        self.assertEqual(proof['components'][0]['disposition'], 'supported-original-backing')
        self.assertGreaterEqual(len(proof['components'][0]['evidence']['independently_known_original_contributors']), 3)
        self.assertEqual(originals, before)

    def test_three_copies_of_one_original_do_not_teach_backing(self):
        image, room, originals = self.backing_scene(copies=True)
        with patch('scripts.source_repeated_identity.scanner._classify_block',
                   return_value=SimpleNamespace(score=0)):
            with patch('scripts.source_repeated_identity._closed_rectangle', return_value=None):
                proof = repeated_material_support(image, room, originals)
        self.assertEqual(proof['unsupported_known'], [(1, 160, 160)])
        self.assertTrue(proof['unsupported_is_NOT_empty_background'])
