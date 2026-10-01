"""Source-backed half-phase terrain without reference-dependent coordinates."""
from collections import Counter
from contextlib import ExitStack
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.constants import OBJ_BLOCK, OBJ_MINI_BLOCK, OBJ_SAVE, OBJ_SPIKE_UP
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.scanner import (
    Detection, ScanResult, _CaptureLatticeAxis, _CaptureLatticeNormalization,
    _detect_phase_free_outlined_blocks, _scan_lattice_normalized_room,
    _merge_source_supported_terrain_blocks, _outlined_terrain_threshold,
)
from jtool_scanner.terrain_material import cell_quad


def detection(kind, type_id, x, y, size=32):
    return Detection(kind, type_id, x, y, .9, Box(x, y, size, size))


def field(scale=1, background=(75,80,90), material=(18,25,30), border=(170,200,90)):
    image=Image.new('RGB',(800,608),background)
    draw=ImageDraw.Draw(image)
    # Continuous shafts, an offset horizontal strip and a disconnected cap.
    rectangles=((112,32,143,207),(288,272,319,575),(400,432,527,463),(624,256,655,287))
    for box in rectangles:
        draw.rectangle(box,fill=material,outline=border,width=2)
    if scale!=1:
        image=image.resize((round(800*scale),round(608*scale)))
    return RGBImage(image.width,image.height,image.tobytes()),Box(0,0,image.width,image.height)


class OutlinedTerrainPhaseTests(unittest.TestCase):
    def test_complete_offset_rectangles_across_hues_brightness_and_scale(self):
        truth={(112,y) for y in range(32,208,16)}
        truth|={(128,y) for y in range(32,208,16)}
        truth|={(x,y) for x in (288,304) for y in range(272,576,16)}
        truth|={(x,y) for x in range(400,528,16) for y in (432,448)}
        truth|=cell_quad((624,256))
        for scale in (.75,1,1.25):
            for background,material,border in (
                ((75,80,90),(18,25,30),(170,200,90)),
                ((115,75,55),(30,20,14),(100,140,220)),
                ((95,100,110),(34,40,45),(200,120,160)),
            ):
                with self.subTest(scale=scale,material=material):
                    image,room=field(scale,background,material,border)
                    threshold=_outlined_terrain_threshold(sum(background)/3,sum(material)/3)
                    result=_detect_phase_free_outlined_blocks(image,room,threshold)
                    cells={c for d in result for c in cell_quad((d.x,d.y))}
                    self.assertEqual(cells,truth)
                    self.assertTrue(all(d.type_id==OBJ_BLOCK for d in result))

    def test_dark_triangle_centres_or_single_quadrants_are_not_rectangles(self):
        image=Image.new('RGB',(800,608),(80,90,95));draw=ImageDraw.Draw(image)
        for x in range(32,704,96):
            draw.polygon(((x+16,32),(x,63),(x+31,63)),fill=(20,20,20))
            draw.polygon(((x,128),(x+31,128),(x+16,159)),fill=(20,20,20))
        # An isolated solid quadrant and an adjacent 16x48 strip are not 32x32.
        draw.rectangle((64,240,79,255),fill=(20,20,20))
        draw.rectangle((160,240,175,287),fill=(20,20,20))
        rgb=RGBImage(800,608,image.tobytes())
        self.assertEqual(_detect_phase_free_outlined_blocks(rgb,Box(0,0,800,608),45),[])

    def test_late_merge_keeps_objects_and_requires_missing_half_block(self):
        block=detection('old',OBJ_BLOCK,112,32)
        marker=detection('save',OBJ_SAVE,400,432)
        spike=detection('partial',OBJ_SPIKE_UP,128,32)
        mini=detection('mini',OBJ_MINI_BLOCK,144,32,16)
        original=[block,marker,spike,mini]
        candidates=[detection('new',OBJ_BLOCK,112,32),
                    detection('new',OBJ_BLOCK,112,48),
                    detection('new',OBJ_BLOCK,144,32)]
        with patch('jtool_scanner.scanner._sample_map_patch_colors',side_effect=AssertionError('cached evidence only')):
            result=_merge_source_supported_terrain_blocks(original,candidates)
        self.assertTrue(all(a is b for a,b in zip(original,result)))
        self.assertEqual({(d.x,d.y) for d in result[len(original):]}, {(112,48),(144,32)})
        # One missing quadrant must not manufacture a whole block.
        three=[detection('mini',OBJ_MINI_BLOCK,x,y,16) for x,y in ((32,32),(48,32),(32,48))]
        self.assertIs(_merge_source_supported_terrain_blocks(three,[detection('new',OBJ_BLOCK,32,32)]),three)

    def test_unaligned_existing_block_does_not_claim_uncovered_quadrants(self):
        original=[detection('offset8',OBJ_BLOCK,8,8)]
        result=_merge_source_supported_terrain_blocks(original,[detection('new',OBJ_BLOCK,0,0)])
        self.assertEqual(len(result),2)
        self.assertIs(result[0],original[0])

    def test_capture_recovery_runs_after_consensus_and_all_marker_spike_guards(self):
        image=RGBImage(800,608,bytes((70,80,90))*800*608)
        room=Box(0,0,800,608)
        marker=detection('save',OBJ_SAVE,32,64)
        spike=detection('spike',OBJ_SPIKE_UP,160,64)
        block=detection('old',OBJ_BLOCK,160,96)
        new=detection('new',OBJ_BLOCK,112,32)
        source=ScanResult(800,608,room,[marker])
        canonical=ScanResult(800,608,room,[spike,block])
        normalization=_CaptureLatticeNormalization(room,_CaptureLatticeAxis(0,800,1,.5),_CaptureLatticeAxis(0,608,1,.5))
        stages=[]
        def unchanged(name):
            def inner(detections,*args,**kwargs):
                stages.append(name)
                self.assertNotIn(new,detections)
                return detections
            return inner
        names=('_reconcile_profiled_marker_anchors','_reconcile_walljump_terrain_anchors',
               '_reanchor_save_headers','_reconcile_mini_terrain_marker_anchors',
               '_prune_dense_minispike_direction_conflicts','_reconcile_directed_material_spikes',
               '_reconcile_source_supported_spike_phases','_prune_terrain_covered_spike_aliases',
               '_recover_directed_material_spikes','_recover_directed_mini_runs',
               '_recover_backed_native_mini_structures','_prune_source_exterior_block_aliases',
               '_prune_paired_mini_full_spike_conflicts')
        def recover(detections,*args):
            stages.append('phase_free_recovery')
            return [*detections,new]
        with ExitStack() as stack:
            scan=stack.enter_context(patch('jtool_scanner.scanner.scan_image',side_effect=(source,canonical)))
            stack.enter_context(patch('jtool_scanner.scanner._capture_lattice_consensus_enabled',return_value=False))
            stack.enter_context(patch('jtool_scanner.scanner._resample_capture_lattice_room',return_value=image))
            for name in names:stack.enter_context(patch('jtool_scanner.scanner.'+name,side_effect=unchanged(name)))
            stack.enter_context(patch('jtool_scanner.scanner._recover_phase_free_outlined_terrain_blocks',side_effect=recover))
            result=_scan_lattice_normalized_room(image,normalization,grid_step=8,include_color_objects=True,recognized_text='')
        self.assertEqual(stages[-1],'phase_free_recovery')
        self.assertEqual(set(stages[:-1]),set(names))
        self.assertTrue(all(call.kwargs['_apply_shape_refits'] is False for call in scan.call_args_list))
        self.assertEqual(Counter((d.type_id,d.x,d.y) for d in result.detections),Counter((d.type_id,d.x,d.y) for d in (marker,spike,block,new)))


if __name__=='__main__':
    unittest.main()
