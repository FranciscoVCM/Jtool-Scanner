"""Original platform-veto ledger, real source corroboration and marker protections."""
import unittest
from jtool_scanner.geometry import Box
from jtool_scanner.scanner import Detection
from scripts.source_rgb_distribution import SourceRGBDistribution
from scripts.source_deferred_platforms import original_platform_vetoes, recover_deferred_platform_blocks
from tests.test_source_rgb_distribution import scene, PARENTS, GLYPHS


def det(type_id, x=352, y=160, score=.5):
    return Detection('test', type_id, x, y, score, Box(x, y, 32, 32))


class DeferredPlatformTests(unittest.TestCase):
    def setUp(self):
        self.frame = scene()
        self.model = SourceRGBDistribution(self.frame, PARENTS, GLYPHS)
        self.platform, self.block = det(13), det(1)
        self.vetoes = original_platform_vetoes([self.platform, self.block])

    def recover(self, final, vetoes=None, models=None, grid=(25, 19), frame=None):
        return recover_deferred_platform_blocks(final, self.vetoes if vetoes is None else vetoes,
            [self.model] if models is None else models, source_grid=grid,
            source_frame=self.frame if frame is None else frame)

    def test_dead_false_platform_allows_only_source_proved_original_block(self):
        final = [det(12, 64, 320)]
        merged, proof = self.recover(final)
        self.assertEqual(merged, final + [self.block])
        self.assertIs(merged[0], final[0])
        self.assertIs(merged[1], self.block)
        self.assertEqual(proof['added'], [(1, 352, 160)])
        self.assertTrue(proof['no_objects_retired'])

    def test_surviving_platform_or_reanchored_platform_still_vetoes(self):
        for platform in (self.platform, det(13, 368, 160)):
            final = [platform]
            merged, proof = self.recover(final)
            self.assertIs(merged, final)
            self.assertFalse(proof['added'])

    def test_late_diagonal_real_marker_protection_is_preserved(self):
        final = [det(12, 368, 176)]
        merged, proof = self.recover(final)
        self.assertIs(merged, final)
        self.assertEqual(proof['abstained'][0]['reason'], 'surviving marker conflict')

    def test_original_save_or_mixed_veto_never_becomes_platform_recovery(self):
        for anchors in ([det(12)], [self.platform, det(12)]):
            vetoes = original_platform_vetoes([self.block, *anchors])
            merged, proof = self.recover([], vetoes=vetoes)
            self.assertFalse(merged)
            self.assertFalse(proof['queries'])

    def test_raw_spikes_are_not_queued_or_restored(self):
        vetoes = original_platform_vetoes([self.platform, det(3)])
        self.assertFalse(vetoes)
        self.assertFalse(self.recover([], vetoes=vetoes)[1]['added'])

    def test_exact_survivor_is_not_replaced_or_relabelled(self):
        final = [self.block]
        merged, proof = self.recover(final)
        self.assertIs(merged, final)
        self.assertIs(merged[0], self.block)
        self.assertFalse(proof['queries'])

    def test_veto_is_not_positive_evidence_for_an_empty_source_patch(self):
        block, platform = det(1, 400, 400), det(13, 400, 400)
        vetoes = original_platform_vetoes([block, platform])
        merged, proof = self.recover([], vetoes=vetoes)
        self.assertFalse(merged)
        self.assertFalse(proof['queries'][0]['source'][0]['proof']['passed'])

    def test_existing_mini_union_and_half_strip_rule_prevent_retile_claim(self):
        final = [det(2, x, y) for x in (352, 368) for y in (160, 176)]
        merged, proof = self.recover(final)
        self.assertIs(merged, final)
        self.assertFalse(proof['added'])

    def test_nonstandard_grid_or_no_model_bypasses_without_changes(self):
        for grid in ((19, 13), (9, 9), None):
            final = []
            merged, proof = self.recover(final, grid=grid)
            self.assertIs(merged, final)
            self.assertIn('bypassed', proof)
        self.assertIn('bypassed', self.recover([], models=[])[1])

    def test_another_frame_cannot_relabel_model_evidence(self):
        with self.assertRaisesRegex(ValueError, 'share the original'):
            self.recover([], frame=scene())


if __name__ == '__main__':
    unittest.main()
