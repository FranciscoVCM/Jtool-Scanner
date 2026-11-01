"""Pixel-only artwork keeps independent witnesses and strict ownership vetoes."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts import source_compound_conflicts as compound
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_pixel_artwork import PixelArtworkConflictQuery
from tests import test_source_compound_conflicts as legacy


class PixelArtworkOwnershipContracts(legacy.SourceCompoundConflictTests):
    """Run the existing ownership assertions through the explicit new mode."""

    def setUp(self):
        run = legacy.run_scene
        replacement = lambda values, **kwargs: run(values, pixel_artwork=True, **kwargs)
        self.override = patch.object(legacy, 'run_scene', side_effect=replacement)
        self.override.start()
        self.addCleanup(self.override.stop)


class SourcePixelArtworkTests(TestCase):
    def setUp(self):
        self.values = legacy.scene()
        image, room, frame, original, material = self.values
        self.query = PixelArtworkConflictQuery(frame,
            SourceEvidenceContext(image, room, []), original, material, None, None, None)
        self.query.separation = 8
        self.owner = (3, 224, 224)
        self.query.artwork = {self.owner: dict(phase=(0, 0),
            teachers=((3, 96, 64), (4, 208, 64), (6, 320, 64)))}
        self.rgb = (102, 100, 100)

    @staticmethod
    def cell(frame, x, y):
        return dict(positions=[(int(x), int(y))],
                    RGB=[(100, 100, 100), (104, 100, 100)])

    def physical_owner(self, cell=None):
        # Isolate resampling evidence, not glyph qualification or room accuracy.
        with patch.object(compound._ConflictQuery, 'art_owner', return_value=None), \
             patch('scripts.source_pixel_artwork.source_cell', side_effect=cell or self.cell):
            return self.query.art_owner(240.5, 240.5, self.rgb)

    def test_three_disjoint_cells_explain_only_repeated_artwork(self):
        self.assertEqual(self.physical_owner(), self.owner)
        proof = self.query.new_art_witnesses
        self.assertEqual(len(proof), 1)
        self.assertEqual(len(proof[0]['witnesses']), 3)
        self.assertEqual(proof[0]['limit'], 2)
        self.assertTrue(all(v['error'] == 0 for v in proof[0]['witnesses']))

    def test_two_cells_cannot_establish_artwork(self):
        self.query.artwork[self.owner]['teachers'] = ((3, 96, 64), (4, 208, 64))
        self.assertIsNone(self.physical_owner())
        self.assertEqual(self.query.new_art_witnesses, [])

    def test_shared_physical_pixels_cannot_count_as_independent_witnesses(self):
        def shared(frame, x, y):
            return {**self.cell(frame, x, y), 'positions': [(10, 20)]}
        self.assertIsNone(self.physical_owner(shared))

    def test_unknown_cells_are_not_omitted_or_padded(self):
        self.assertIsNone(self.physical_owner(lambda *args: None))
        self.assertEqual(self.query.new_art_witnesses, [])

    def test_rgb_must_fit_the_cell_not_a_per_channel_colour_box(self):
        def incompatible(frame, x, y):
            return dict(positions=[(int(x), int(y))],
                        RGB=[(100, 100, 110), (110, 100, 100)])
        self.assertIsNone(self.physical_owner(incompatible))

    def test_individually_close_but_inconsistent_cells_cannot_vote_together(self):
        self.rgb = (100, 100, 100)
        colours = iter(((98.1, 100, 100), (101.9, 100, 100), (100, 100, 100)))
        def incompatible(frame, x, y):
            return dict(positions=[(int(x), int(y))], RGB=[next(colours)])
        self.assertIsNone(self.physical_owner(incompatible))

    def test_legacy_artwork_owner_wins_without_new_pixel_queries(self):
        with patch.object(compound._ConflictQuery, 'art_owner', return_value=self.owner), \
             patch('scripts.source_pixel_artwork.source_cell',
                   side_effect=AssertionError('Existing evidence needs no new cell')):
            self.assertEqual(self.query.art_owner(240.5, 240.5, self.rgb), self.owner)
        self.assertEqual(self.query.new_art_witnesses, [])

    def test_pixel_mode_never_constructs_affine_or_directional_body_models(self):
        with patch('scripts.source_calibrated_conflicts.SourceGlyphBackdrop',
                   side_effect=AssertionError('No affine background')), \
             patch('scripts.source_directional_body.SourceDirectionalBodyEvidence.__init__',
                   side_effect=AssertionError('No new body queries')):
            retired, _ = legacy.run_scene(self.values, pixel_artwork=True)
        self.assertEqual(retired, {(1, 224, 240)})

    def test_wrong_background_label_stays_unresolved_without_affine_fallback(self):
        self.values[4]['cluster_centers'][1] = dict(r=80, g=100, b=140)
        self.assertFalse(legacy.run_scene(self.values, pixel_artwork=True)[0])

    def test_default_and_explicit_false_preserve_entire_proof(self):
        before = deepcopy(self.values[3:])
        self.assertEqual(legacy.run_scene(self.values),
                         legacy.run_scene(self.values, pixel_artwork=False))
        self.assertEqual(self.values[3:], before)

    def test_pixel_mode_requires_boolean_and_cannot_hide_affine_activation(self):
        for value in (0, 1, None, 'true', []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'boolean'):
                legacy.run_scene(self.values, pixel_artwork=value)
        with self.assertRaisesRegex(ValueError, 'not both'):
            legacy.run_scene(self.values, pixel_artwork=True, calibrated_background=True)

    def test_current_query_excludes_teachers_including_source_context(self):
        # The third teacher's geometry is disjoint but its four-pixel context
        # overlaps the query. Two independent teachers must not become three.
        self.query.artwork[self.owner]['teachers'] = ((3, 96, 64), (4, 208, 64), (6, 257, 240))
        original = deepcopy(self.query.artwork)
        observed = []
        def inspect(query, detection):
            observed.append(deepcopy(query.artwork))
            return dict(retire=False)
        with patch.object(compound._ConflictQuery, 'query', inspect):
            result = self.query.query(SimpleNamespace(x=224, y=240))
        self.assertEqual(observed, [{}])
        self.assertEqual(result['artwork_query_excluded_teachers'], [(6, 257, 240)])
        self.assertEqual(self.query.artwork, original)

    def test_query_decision_caches_cannot_escape_to_another_block(self):
        art_cache, cell_queries = self.query.art_cache, self.query.cell_queries
        art_cache[240.5, 240.5] = self.owner
        cell_queries[240.5, 240.5] = self.owner
        seen = []
        def inspect(query, detection):
            seen.append((dict(query.art_cache), dict(query.cell_queries)))
            query.art_cache[240.5, 240.5] = self.owner
            query.cell_queries[240.5, 240.5] = self.owner
            return dict(retire=False)
        with patch.object(compound._ConflictQuery, 'query', inspect):
            self.query.query(SimpleNamespace(x=224, y=240))
            self.query.query(SimpleNamespace(x=240, y=240))
        self.assertEqual(seen, [({}, {}), ({}, {})])
        self.assertIs(self.query.art_cache, art_cache)
        self.assertIs(self.query.cell_queries, cell_queries)

    def test_query_restores_models_and_caches_even_after_an_exception(self):
        artwork, art_cache, cell_queries = self.query.artwork, self.query.art_cache, self.query.cell_queries
        with patch.object(compound._ConflictQuery, 'query', side_effect=RuntimeError('probe')):
            with self.assertRaisesRegex(RuntimeError, 'probe'):
                self.query.query(SimpleNamespace(x=224, y=240))
        self.assertIs(self.query.artwork, artwork)
        self.assertIs(self.query.art_cache, art_cache)
        self.assertIs(self.query.cell_queries, cell_queries)
