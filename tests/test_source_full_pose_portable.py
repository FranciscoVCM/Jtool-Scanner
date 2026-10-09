"""Real raster pose recovery across palette/polarity/scale, not mocked evidence."""
from types import SimpleNamespace
from unittest import TestCase

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_full_pose import refit_full_poses


PALETTES = [((20, 30, 45), (190, 150, 90)), ((220, 230, 235), (70, 90, 110)),
            ((0, 130, 0), (220, 10, 10)), ((35, 45, 50), (80, 105, 110))]


def scene(background, foreground, scale):
    raster = Image.new('RGB', (800, 608), background)
    teachers = [(64, 64), (128, 64), (192, 64)]
    correct = (496, 160)
    for x, y in teachers + [correct]:
        for j in range(32):
            for i in range(32):
                delta = 35 if (i+2*j) % 17 < 3 else -15 if (2*i-j) % 13 < 2 else 0
                rgb = tuple(max(0, min(255, c+delta)) for c in foreground)
                raster.putpixel((x+i, y+j), rgb)
    spike_poses = [(160, 256), (256, 320), (352, 384)]
    draw = ImageDraw.Draw(raster)
    for x, y in spike_poses:
        draw.polygon([(x+u, y+v) for u, v in VERTICES[3]], fill=foreground)
    if scale != 1:
        raster = raster.resize((round(800*scale), round(608*scale)), Image.Resampling.BILINEAR)
    image = RGBImage(raster.width, raster.height, raster.tobytes())
    room = Box(0, 0, image.width, image.height)
    original = [SimpleNamespace(type_id=1, x=x, y=y) for x, y in teachers + [(512, 160)]]
    original += [SimpleNamespace(type_id=3, x=x, y=y) for x, y in spike_poses]
    material = dict(accepted=[(x+dx, y+dy) for x, y in teachers+[correct] for dx in (0, 16) for dy in (0, 16)],
        selected_clusters=[0], cluster_centers=[dict(zip(('r', 'g', 'b'), foreground)), dict(zip(('r', 'g', 'b'), background))],
        tip_votes={1: 3}, background_back_votes={1: 0})
    return image, room, original, material


class SourceFullPosePortableTests(TestCase):
    def test_actual32_texture_and_local_background_recover_all_eight_variants(self):
        for background, foreground in PALETTES:
            for scale in (1, 1.25):
                with self.subTest(background=background, foreground=foreground, scale=scale):
                    image, room, original, material = scene(background, foreground, scale)
                    spikes = [(d.type_id, d.x, d.y) for d in original if d.type_id == 3]
                    context = SourceEvidenceContext(image, room, spikes)
                    before = {(d.type_id, d.x, d.y) for d in original}
                    proposed, rejected, proof = refit_full_poses(image, room, original, {(1, 512, 160)}, set(), material,
                        source_context=context)
                    self.assertEqual(rejected, {(1, 512, 160)})
                    self.assertEqual(proposed, {(1, 496, 160)})
                    self.assertEqual((before-rejected)|proposed, before-{(1, 512, 160)}|{(1, 496, 160)})
                    self.assertEqual(len(proof['texture_pose_proofs']), 1)
                    self.assertTrue(proof['texture_pose_proofs'][0]['unmasked_source_full_texture']['passed'])
                    self.assertTrue(proof['texture_pose_proofs'][0]['all_old_source_foreground_pixels_retained'])
