"""Local-source semantics tests, without a scanner recall assertion."""
import unittest

from scripts.local_material_scenes import (
    create_local_material_scene, local_material_specs,
)


class LocalMaterialSceneTests(unittest.TestCase):
    def test_complete_default_lattice_has_fixed_truth_roles(self):
        specs = local_material_specs()
        self.assertEqual(len(specs), 48)
        self.assertEqual(sum(spec['include_mini'] for spec in specs), 24)
        self.assertEqual(len({tuple(sorted(spec.items())) for spec in specs}), 48)
        for spec in specs:
            image, room, truth, coarse, solids, options = create_local_material_scene(**spec)
            self.assertEqual((image.width, image.height),
                             (round(800*spec['scale']), round(608*spec['scale'])))
            self.assertEqual((room.width, room.height), (image.width, image.height))
            self.assertEqual((7, 352, 336) in truth, spec['include_mini'])
            self.assertNotIn((7, 352, 336), coarse)
            self.assertIn((3, 336, 320), coarse)
            self.assertNotIn((3, 336, 320), truth)
            self.assertEqual(solids, [(304, 352, 112, 32)])
            self.assertEqual(options['mean_shift'], 0)

    def test_seeded_sources_are_reproducible(self):
        for variation in ('checker3px_delta60', 'seeded_noise_delta60', 'smooth_x_gradient_delta60'):
            first = create_local_material_scene(variation)
            second = create_local_material_scene(variation)
            self.assertEqual(first[0].data, second[0].data)
            self.assertEqual(first[2:], second[2:])

    def test_nuisance_is_local_and_does_not_change_authored_object_pixels(self):
        scenes = [create_local_material_scene(variation) for variation in (
            'checker3px_delta60', 'seeded_noise_delta60', 'smooth_x_gradient_delta60')]
        for image, _, _, _, _, _ in scenes:
            self.assertEqual(image.pixel(200, 200), (140, 165, 163))
            self.assertEqual(image.pixel(360, 340), (132, 137, 144))
            self.assertEqual(image.pixel(310, 360), (83, 49, 47))
        self.assertEqual(len({image.data for image, *_ in scenes}), 3)

    def test_invalid_parameters_are_rejected(self):
        for kwargs in (dict(variation='unrecognized'), dict(full_outline_width=True),
                       dict(mini_outline_width=0), dict(scale=0), dict(scale=float('inf')),
                       dict(polarity='unsupported'), dict(include_mini=1), dict(mean_shift=61)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                create_local_material_scene(**{'variation': 'seeded_noise_delta60', **kwargs})

    def test_mean_shift_extension_keeps_geometry_and_object_interiors(self):
        specs = local_material_specs(mean_shifts=(-30, 30))
        self.assertEqual(len(specs), 96)
        self.assertEqual(sum(spec['include_mini'] for spec in specs), 48)
        for variation in ('checker3px_delta60', 'seeded_noise_delta60', 'smooth_x_gradient_delta60'):
            original = create_local_material_scene(variation)
            for shift in (-30, 30):
                shifted = create_local_material_scene(variation, mean_shift=shift)
                self.assertEqual(shifted[2:5], original[2:5])
                self.assertEqual(shifted[0].pixel(360, 340), original[0].pixel(360, 340))
                self.assertEqual(shifted[0].pixel(200, 200), original[0].pixel(200, 200))
                self.assertEqual(shifted[0].pixel(374, 330),
                                 tuple(value + shift for value in original[0].pixel(374, 330)))
                self.assertEqual(shifted[5]['mean_shift'], shift)


if __name__ == '__main__':
    unittest.main()
