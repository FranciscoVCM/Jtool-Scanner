"""Source-background nuisance must not create geometry from known false gaps."""
import unittest

from jtool_scanner.spike_size import contour_size_changes
from scripts.local_material_scenes import create_local_material_scene, local_material_specs


class LocalMaterialRecognitionTests(unittest.TestCase):
    def test_local_background_variation_does_not_invent_geometry_or_erase_anchors(self):
        # All144 predeclared scenes, including true-mini AND empty controls.
        # In the true scenes a differently bright textured gap beside a real
        # mini must not become a second, opposing miniature. Known truth is
        # evaluation only; recognition gets pixels/room/coarse/solids, NEVER
        # the omitted mini's answer. Its recovery is allowed, not required by
        # this regression. The intentional old full alias remains an error
        # if retained; this test does not certify complete reconstruction.
        for spec in local_material_specs(mean_shifts=(0, -30, 30)):
            with self.subTest(**spec):
                image, room, truth, coarse, solids, _ = create_local_material_scene(**spec)
                added, rejected = contour_size_changes(image, room, coarse, solids)
                self.assertFalse(added - set(truth), 'new object unsupported by authored source')
                self.assertFalse((set(coarse) & set(truth)) & rejected,
                                 'existing true full anchor erased')


if __name__ == '__main__':
    unittest.main()
