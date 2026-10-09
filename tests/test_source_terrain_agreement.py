"""Direct causal arbitration tests: unknown, explicit owner, rectangle and true full."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_terrain_agreement import agree_new_fulls


class EvidenceLibrary:
    anchors=[]
    def __init__(self, owned=True, rectangle=False):
        self.owned=owned
        self.raw=SimpleNamespace(raw=SimpleNamespace(edge=lambda a,b:(12 if rectangle else 0,False)))
    def support(self,t,x,y):
        return dict(passed=self.owned and t==6, original_source_only=True)


class SourceTerrainAgreementTests(TestCase):
    def setUp(self):
        self.image=RGBImage(800,608,bytes(800*608*3))
        self.room=Box(0,0,800,608)
        self.detections=[SimpleNamespace(type_id=6,x=160,y=160)]
        self.full=(1,160,160)
        self.cells={(176,160),(160,176),(176,176)}

    def run_rule(self,library,full_pass=False,proposed=None,detections=None):
        with patch('scripts.source_terrain_agreement.SourceGlyphLibrary',return_value=library), \
             patch('scripts.source_terrain_agreement.SourceBlockLibrary') as block:
            block.return_value.support.return_value=dict(passed=full_pass,source_only=True)
            return agree_new_fulls(self.image,self.room,self.detections if detections is None else detections,
                                   {self.full} if proposed is None else proposed,set(),self.cells)

    def test_unknown_without_positive_competitor_is_not_a_negative(self):
        output,proof=self.run_rule(EvidenceLibrary(owned=False))
        self.assertIn(self.full,output)
        self.assertTrue(proof['new_full_source_disagreement'][0]['unknown_alone_does_not_disprove_terrain'])

    def test_explicit_glyph_owner_abstains_from_full_and_preserves_supported_quarters(self):
        output,proof=self.run_rule(EvidenceLibrary())
        self.assertNotIn(self.full,output)
        self.assertEqual(output,{(2,x,y) for x,y in self.cells})
        self.assertTrue(proof['new_full_source_disagreement'][0]['abstained'])

    def test_independent_rectangle_retains_priority_over_overlapping_glyph(self):
        output,proof=self.run_rule(EvidenceLibrary(rectangle=True))
        self.assertIn(self.full,output)
        self.assertFalse(proof['new_full_source_disagreement'][0]['abstained'])

    def test_positive_whole32_appearance_can_retain_true_occluded_full(self):
        output,proof=self.run_rule(EvidenceLibrary(),full_pass=True)
        self.assertIn(self.full,output)
        self.assertFalse(proof['new_full_source_disagreement'][0]['abstained'])

    def test_original_full_and_mini_are_not_deleted_by_overlap(self):
        original=self.detections+[SimpleNamespace(type_id=1,x=160,y=160),SimpleNamespace(type_id=2,x=160,y=160)]
        output,proof=self.run_rule(EvidenceLibrary(),proposed={self.full,(2,160,160)},detections=original)
        self.assertEqual(output,{self.full,(2,160,160)})
        self.assertEqual(proof['new_full_source_disagreement'],[])

    def test_inputs_do_not_mutate_and_new_proposal_never_becomes_teacher(self):
        proposed={self.full};cells=set(self.cells);original=list(self.detections)
        with patch('scripts.source_terrain_agreement.SourceGlyphLibrary',return_value=EvidenceLibrary()) as glyph, \
             patch('scripts.source_terrain_agreement.SourceBlockLibrary') as block:
            block.return_value.support.return_value=dict(passed=False)
            agree_new_fulls(self.image,self.room,self.detections,proposed,set(),cells)
            self.assertEqual(glyph.call_args.args[2],[(6,160,160)])
            self.assertEqual(block.call_args.args[1],set())
        self.assertEqual(proposed,{self.full});self.assertEqual(cells,self.cells);self.assertEqual(self.detections,original)

    def test_supported_quarters_already_covered_are_not_emitted_twice(self):
        original=self.detections+[SimpleNamespace(type_id=2,x=x,y=y) for x,y in self.cells]
        output,proof=self.run_rule(EvidenceLibrary(),detections=original)
        self.assertEqual(output,set())
        self.assertEqual(proof['source_supported_quarter_repacking'],[])

    def test_all_four_qualified_quarters_need_no_additional_teaching(self):
        cells=self.cells|{(160,160)}
        with patch('scripts.source_terrain_agreement.SourceGlyphLibrary',side_effect=AssertionError('Not needed')):
            output,proof=agree_new_fulls(self.image,self.room,self.detections,{self.full},set(),cells)
        self.assertEqual(output,{self.full})
        self.assertTrue(proof['original_source_size_preserved'])
