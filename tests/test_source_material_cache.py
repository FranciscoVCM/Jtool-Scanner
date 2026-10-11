"""Exact scan-local material reuse, bounded storage and independent proofs."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock, patch

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_material_patterns import eligible_primitives, pattern_cells


class SourceMaterialCacheTests(TestCase):
    def setUp(self):
        self.image = RGBImage(800,608,bytes(800*608*3))
        self.room = Box(0,0,800,608)
        self.spikes = [(3,160,160)]
        self.context = SourceEvidenceContext(self.image,self.room,self.spikes)

    def run_cache(self, stage='intrinsic', settings=(), compute=None, context=None):
        return (context or self.context).material_result(self.image,self.room,self.spikes,
            stage,settings,compute or Mock(return_value=({(160,160)}, {'models':[{'witnesses':[[1,2]]}]})))

    def test_first_result_hit_and_nested_mutation_are_isolated(self):
        compute = Mock(return_value=({(160,160)}, {'models':[{'witnesses':[[1,2]]}]}))
        first = self.run_cache(compute=compute); expected = deepcopy(first)
        first[0].clear();first[1]['models'][0]['witnesses'][0][0] = 99
        hit = self.run_cache(compute=compute)
        self.assertEqual(hit,expected)
        hit[1]['models'].clear()
        self.assertEqual(self.run_cache(compute=compute),expected)
        compute.assert_called_once()
        self.assertEqual(self.context.material_statistics(),dict(limit=4,entries=1,builds=1,hits=2))

    def test_native_cell_iteration_is_preserved_with_independent_set_storage(self):
        # Rebuilding a native set during deepcopy changes its hash-table layout.
        # Distributed teacher diagnostics consume that iteration order.
        cells = {(x,y) for x in range(0,784,16) for y in range(0,592,16) if (x+y)%48 == 0}
        compute = Mock(return_value=(cells,{'models':[]}))
        first = self.run_cache(compute=compute)
        hit = self.run_cache(compute=compute)
        self.assertEqual(list(hit[0]),list(first[0]))
        self.assertIsNot(hit[0],first[0])
        hit[0].clear()
        self.assertEqual(self.run_cache(compute=compute)[0],cells)

    def test_modes_and_overlay_geometry_never_collide(self):
        compute = Mock(side_effect=lambda: ({(160,160)}, {'generation':compute.call_count}))
        for stage in ('intrinsic','local','distributed','eligible'):
            self.run_cache(stage,((0,0,32,32),),compute)
        self.run_cache('intrinsic',((0,0,32,32),),compute)
        self.run_cache('intrinsic',((8,0,32,32),),compute)
        self.assertEqual(compute.call_count,5)
        self.assertEqual(self.context.material_statistics()['entries'],4)

    def test_full_capacity_falls_back_without_eviction_or_truncation(self):
        context = SourceEvidenceContext(self.image,self.room,self.spikes,material_cache_limit=1)
        first = Mock(return_value=({(160,160)}, {'all':[1,2,3]}))
        other = Mock(return_value=({(320,320)}, {'all':[4,5,6]}))
        self.run_cache(compute=first,context=context)
        for _ in range(2):
            self.assertEqual(self.run_cache('local',compute=other,context=context),other.return_value)
        self.assertEqual(self.run_cache(compute=first,context=context),first.return_value)
        first.assert_called_once();self.assertEqual(other.call_count,2)
        self.assertEqual(context.material_statistics()['entries'],1)

    def test_zero_limit_ablation_and_separate_contexts_do_not_share(self):
        compute = Mock(return_value=(set(),{'unknown':True}))
        zero = SourceEvidenceContext(self.image,self.room,self.spikes,material_cache_limit=0)
        for _ in range(2):self.run_cache(compute=compute,context=zero)
        self.assertEqual(compute.call_count,2)
        self.assertEqual(zero.material_statistics()['entries'],0)
        self.run_cache(compute=compute)
        separate = SourceEvidenceContext(self.image,self.room,self.spikes)
        self.run_cache(compute=compute,context=separate)
        self.assertEqual(compute.call_count,4)

    def test_changed_source_frame_or_teacher_locators_rejected_even_on_hit(self):
        self.run_cache()
        for image,room,spikes in (
            (RGBImage(800,608,self.image.data),self.room,self.spikes),
            (self.image,Box(0,0,768,608),self.spikes),
            (self.image,self.room,self.spikes+[(7,176,176)])):
            with self.assertRaises(ValueError):
                self.context.material_result(image,room,spikes,'intrinsic',(),Mock())
        original = self.image.data
        self.image.data = bytes(bytearray(original))
        with self.assertRaises(ValueError):self.run_cache()

    def test_invalid_limits_stages_and_failed_producer_never_leave_a_result(self):
        for limit in (-1,True,1.5):
            with self.assertRaises(ValueError):
                SourceEvidenceContext(self.image,self.room,self.spikes,material_cache_limit=limit)
        with self.assertRaises(ValueError):self.run_cache('unknown')
        with self.assertRaises(RuntimeError):self.run_cache(compute=Mock(side_effect=RuntimeError('failed')))
        self.assertEqual(self.context.material_statistics()['entries'],0)
        good = Mock(return_value=(set(),{'unknown':True}))
        self.run_cache(compute=good);good.assert_called_once()

    def test_pattern_wrapper_keys_mutable_overlay_coordinates_and_mode(self):
        water = [[0,0,32,32]]
        with patch('scripts.source_material_patterns._pattern_cells',return_value=(set(),{'models':[]})) as build:
            a = pattern_cells(self.image,self.room,self.spikes,water,source_context=self.context)
            a[1]['models'].append('poison')
            self.assertEqual(pattern_cells(self.image,self.room,self.spikes,water,source_context=self.context),
                (set(),{'models':[]}))
            water[0][0] = 8
            pattern_cells(self.image,self.room,self.spikes,water,source_context=self.context)
            pattern_cells(self.image,self.room,self.spikes,water,mode='local',source_context=self.context)
            self.assertEqual(build.call_count,3)

    def test_eligible_wrapper_reuses_original_proof_only(self):
        with patch('scripts.source_material_patterns._eligible_primitives',return_value=({(160,160)},{'proof':[1]})) as build:
            first = eligible_primitives(self.image,self.room,self.spikes,source_context=self.context)
            first[0].clear();first[1]['proof'].clear()
            self.assertEqual(eligible_primitives(self.image,self.room,self.spikes,source_context=self.context),
                ({(160,160)},{'proof':[1]}))
            build.assert_called_once()

    def test_stateful_overlay_iterable_retains_uncached_behavior(self):
        with patch('scripts.source_material_patterns._pattern_cells',return_value=(set(),{})) as build:
            for _ in range(2):
                pattern_cells(self.image,self.room,self.spikes,iter([(0,0,32,32)]),source_context=self.context)
            self.assertEqual(build.call_count,2)
            self.assertEqual(self.context.material_statistics()['entries'],0)

    def test_overlay_snapshot_cannot_change_during_producer_call(self):
        water = [[0,0,32,32]]
        def compute(image,room,spikes,boxes,**kwargs):
            water[0][0] = 8
            return set(),{'used_water':boxes}
        with patch('scripts.source_material_patterns._pattern_cells',side_effect=compute):
            first = pattern_cells(self.image,self.room,self.spikes,water,source_context=self.context)
        self.assertEqual(first[1]['used_water'],((0,0,32,32),))
        self.assertEqual(water,[[8,0,32,32]])

    def test_empty_unknown_proof_is_cached_without_becoming_a_positive(self):
        with patch('scripts.source_material_patterns.container_primitives',return_value=(set(),{'unknown':True})) as provider:
            first = pattern_cells(self.image,self.room,self.spikes,source_context=self.context)
            second = pattern_cells(self.image,self.room,self.spikes,source_context=self.context)
            self.assertEqual(first,second)
            self.assertEqual(first,(set(),{'unknown':True,'models':[]}))
            provider.assert_called_once()
