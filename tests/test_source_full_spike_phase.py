"""Portable phase-evidence tests; not whole-scanner/reserve qualification."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase,main
from unittest.mock import patch

from PIL import Image,ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_sampling import SourceFrame
from scripts.source_interior_glyphs import INTERIOR_POINTS,_normalized
from tests.test_source_directional_texture import textured_scene
from scripts.source_full_spike_phase import SourceFullSpikePhaseEvidence


def fixture(*,rotation=0,scale=1.25,amount=8,transform=lambda c:c,
            foreground=(210,150,70),background=(20,30,60),isolated=False):
    image,room,frame,original,target=textured_scene(rotation=rotation,scale=1,
        transform=transform,foreground=foreground,background=background)
    raster=Image.frombytes('RGB',(800,608),image.data)
    if isolated:
        # A16px wrong locator can intersect the other true cluster members.
        # Isolate this positive test so its intended pose is unambiguous; the
        # original touching cluster remains the8px all-direction test domain.
        from scripts.source_full_spike_phase import _glyph_polygon
        from scripts.source_glyph_prototypes import _contains
        poly=_glyph_polygon(target)
        for py in range(target[2]-40,target[2]+72):
            for px in range(target[1]-40,target[1]+72):
                if not _contains(poly,px+.5,py+.5):
                    raster.putpixel((px,py),transform(background))
        original=[d for d in original if not (max(d.x,target[1]-40)<min(d.x+32,target[1]+72)
            and max(d.y,target[2]-40)<min(d.y+32,target[2]+72))]
    if scale!=1:
        raster=raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image=RGBImage(raster.width,raster.height,raster.tobytes())
    room=Box(0,0,image.width,image.height);frame=SourceFrame(image,room)
    axis={3:(0,-amount),4:(amount,0),5:(-amount,0),6:(0,amount)}
    dx,dy=axis[target[0]]
    old=(target[0],target[1]+dx,target[2]+dy)
    locator=SimpleNamespace(type_id=old[0],x=old[1],y=old[2],origin='unaltered original')
    original=tuple(original)+(locator,)
    return image,room,frame,original,target,old


def evidence(values):
    image,room,frame,original,target,old=values
    return SourceFullSpikePhaseEvidence(FilledGlyphEvidence(frame,original),original,source_grid=(25,19))


class SourceFullSpikePhaseTests(TestCase):
    def test_source_positive_phase_all_directions_and_palettes(self):
        transforms=(lambda c:c,lambda c:tuple(255-v for v in c),
                    lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(.4*v) for v in c))
        for rotation,transform in enumerate(transforms):
            values=fixture(rotation=rotation,transform=transform)
            proof=evidence(values).probe(values[5],values[3])
            with self.subTest(rotation=rotation):
                self.assertEqual(proof['proposed'],values[4],proof)
                self.assertEqual(proof['qualified_alternatives'],[values[4]])
                row=next(r for r in proof['candidates'] if r['new']==values[4])
                self.assertEqual(len(row['physical_patch']['samples']),9)
                self.assertTrue(any(c['passed'] and c['new_only_independent_FG']>=4 for c in row['cohorts']))

    def test_native_sixteen_and_fractional_capture(self):
        for scale,amount in ((1,16),(1.25,8),(1.5,16)):
            values=fixture(scale=scale,amount=amount,isolated=amount==16)
            with self.subTest(scale=scale,amount=amount):
                self.assertEqual(evidence(values).probe(values[5],values[3])['proposed'],values[4])

    def test_isoluminant_RGB_and_anisotropic_capture(self):
        values=fixture(foreground=(150,80,65),background=(80,120,40))
        self.assertEqual(Image.new('RGB',(1,1),(150,80,65)).convert('L').getpixel((0,0)),
                         Image.new('RGB',(1,1),(80,120,40)).convert('L').getpixel((0,0)))
        self.assertEqual(evidence(values).probe(values[5],values[3])['proposed'],values[4])
        image,_,_,original,target,old=fixture(scale=1)
        raster=Image.frombytes('RGB',(image.width,image.height),image.data).resize((980,747),Image.Resampling.BILINEAR)
        image=RGBImage(980,747,raster.tobytes());room=Box(0,0,980,747)
        values=(image,room,SourceFrame(image,room),original,target,old)
        self.assertEqual(evidence(values).probe(old,original)['proposed'],target)

    def test_correct_original_contour_cannot_be_rewritten(self):
        values=fixture()
        image,room,frame,original,target,old=values
        original=tuple(d for d in original if (d.type_id,d.x,d.y)!=old)+(SimpleNamespace(type_id=target[0],x=target[1],y=target[2]),)
        field=evidence((image,room,frame,original,target,target))
        proof=field.probe(target,original)
        self.assertIsNone(proof['proposed'])
        self.assertIn('positive old original contour',proof['abstained'])

    def test_metadata_changed_original_and_non_original_are_unknown(self):
        values=fixture();field=evidence(values)
        current=deepcopy(values[3]);current[-1].origin='changed elsewhere'
        self.assertIsNone(field.probe(values[5],current)['proposed'])
        self.assertIsNone(field.probe(values[4],values[3])['proposed'])

    def test_marker_contact_keeps_the_original(self):
        values=list(fixture());old=values[5]
        values[3]=values[3]+(SimpleNamespace(type_id=12,x=old[1],y=old[2]),)
        proof=evidence(values).probe(old,values[3])
        self.assertIsNone(proof['proposed'])
        self.assertIn('marker contact',proof['abstained'])

    def test_already_current_target_does_not_merge_two_existing_objects(self):
        values=fixture();field=evidence(values);target=values[4]
        current=values[3]+(SimpleNamespace(type_id=target[0],x=target[1],y=target[2]),)
        self.assertIsNone(field.probe(values[5],current)['proposed'])

    def test_other_current_solid_in_negative_patch_is_not_declared_background(self):
        values=fixture();field=evidence(values)
        proof=field.probe(values[5],values[3]);self.assertEqual(proof['proposed'],values[4])
        row=next(r for r in proof['candidates'] if r['new']==values[4])
        x,y=row['physical_patch']['samples'][0]['native']
        current=values[3]+(SimpleNamespace(type_id=2,x=int(x)-8,y=int(y)-8),)
        self.assertIsNone(field.probe(values[5],current)['proposed'])

    def test_unknown_capture_and_unqualified_grid_do_not_propose(self):
        values=fixture()
        field=SourceFullSpikePhaseEvidence(FilledGlyphEvidence(values[2],values[3]),values[3],source_grid=(19,13))
        self.assertIsNone(field.probe(values[5],values[3])['proposed'])
        # Existing source and model stay real; only availability is unknown.
        field=evidence(values)
        with patch.object(SourceFrame,'rectangle_available',return_value=False):
            self.assertIsNone(field.probe(values[5],values[3])['proposed'])

    def test_one_positive_pixel_in_negative_patch_keeps_original(self):
        values=fixture();field=evidence(values)
        proof=field.probe(values[5],values[3]);self.assertEqual(proof['proposed'],values[4])
        row=next(r for r in proof['candidates'] if r['new']==values[4])
        image,room,_,original,target,old=values
        raster=Image.frombytes('RGB',(image.width,image.height),image.data)
        raster.putpixel(tuple(row['physical_patch']['samples'][0]['physical']),(210,150,70))
        changed=RGBImage(image.width,image.height,raster.tobytes())
        altered=(changed,room,SourceFrame(changed,room),original,target,old)
        self.assertIsNone(evidence(altered).probe(old,original)['proposed'])

    def test_positive_old_body_outside_replacement_is_preserved(self):
        # Guard control-flow with a deliberately positive old-body observation;
        # independent image semantics are covered by the actual-scene tests.
        from scripts.source_full_spike_phase import _glyph_polygon
        from scripts.source_glyph_prototypes import _contains
        from scripts.source_interior_glyphs import _oriented
        values=fixture(amount=16,isolated=True,scale=1)
        field=evidence(values);target,old=values[4:]
        self.assertEqual(field.probe(old,values[3])['proposed'],target)
        points=[(old[1]+u+.5,old[2]+v+.5) for u,v in
                (_oriented(old[0],*p) for p in INTERIOR_POINTS)]
        index=next(i for i,p in enumerate(points) if not _contains(_glyph_polygon(target),*p))
        original_body=field.body._body
        changed=list(original_body(old));changed[index]=original_body(target)[0]
        with patch.object(field.body,'_body',side_effect=lambda key:
                tuple(changed) if tuple(key)==old else original_body(key)):
            proof=field.probe(old,values[3])
        self.assertIsNone(proof['proposed'])
        row=next(r for r in proof['candidates'] if r['new']==target)
        self.assertTrue(any(c.get('old_positive_body_outside_replacement') for c in row['cohorts']))

    def test_mini_solid_and_text_impostors_do_not_supply_full_contour(self):
        from scripts.source_full_spike_phase import _glyph_polygon
        from scripts.source_glyph_prototypes import _contains
        for shape in ('mini','solid','text'):
            image,room,frame,original,target,old=fixture()
            raster=Image.frombytes('RGB',(image.width,image.height),image.data)
            sx,sy=image.width/800,image.height/608
            box=(round((target[1]-1)*sx),round((target[2]-1)*sy),
                 round((target[1]+33)*sx),round((target[2]+33)*sy))
            draw=ImageDraw.Draw(raster);draw.rectangle(box,fill=(20,30,60))
            if shape=='solid':
                draw.rectangle((round(target[1]*sx),round(target[2]*sy),
                    round((target[1]+32)*sx)-1,round((target[2]+32)*sy)-1),fill=(210,150,70))
            elif shape=='text':
                draw.text((round(target[1]*sx)+5,round(target[2]*sy)+8),'7',fill=(210,150,70))
            else:
                poly=_glyph_polygon(target);tip=poly[0]
                draw.polygon([(round((tip[0]+(x-tip[0])/2)*sx),round((tip[1]+(y-tip[1])/2)*sy))
                              for x,y in poly],fill=(210,150,70))
            changed=RGBImage(image.width,image.height,raster.tobytes())
            values=(changed,room,SourceFrame(changed,room),original,target,old)
            with self.subTest(shape=shape):
                self.assertIsNone(evidence(values).probe(old,original)['proposed'])

    def test_real_partial_wall_hidden_spike_is_not_shifted_to_a_crop(self):
        image,room,frame,original,target,old=fixture()
        original=tuple(d for d in original if (d.type_id,d.x,d.y)!=old)
        original+=(SimpleNamespace(type_id=target[0],x=target[1],y=target[2]),)
        raster=Image.frombytes('RGB',(image.width,image.height),image.data)
        sx,sy=image.width/800,image.height/608
        # Target is RIGHT; an8-native-pixel wall covers its base, leaving24.
        ImageDraw.Draw(raster).rectangle((round(target[1]*sx),round(target[2]*sy),
            round((target[1]+8)*sx)-1,round((target[2]+32)*sy)-1),fill=(120,35,110))
        original+=(SimpleNamespace(type_id=1,x=target[1]-24,y=target[2]),)
        changed=RGBImage(image.width,image.height,raster.tobytes())
        values=(changed,room,SourceFrame(changed,room),original,target,target)
        self.assertIsNone(evidence(values).probe(target,original)['proposed'])

    def test_two_complete_mocked_hypotheses_abstain_instead_of_picking_first(self):
        # Control-flow test ONLY: deliberately fake geometry/body evidence.
        # No claim that this featureless image contains a source-positive spike.
        image=RGBImage(800,608,bytes((20,20,20))*800*608)
        frame=SourceFrame(image,Box(0,0,800,608))
        old=(6,200,200);original=(SimpleNamespace(type_id=6,x=200,y=200),)
        field=object.__new__(SourceFullSpikePhaseEvidence)
        field.original=original;field.original_keys=frozenset((old,));field.frame=frame
        field.filled=SimpleNamespace(library=SimpleNamespace(anchors=[],raw=None))
        teachers=((3,32,32),(3,96,32),(3,160,32))
        FG=(200,200,200);BG=(20,20,20)
        model=dict(foreground=FG,background=BG,limit=50,
            pattern=_normalized([180]*(3*len(INTERIOR_POINTS))))
        field.body=SimpleNamespace(qualified=True,_cohorts=(teachers,),
            geometry=lambda key:dict(passed=tuple(key)!=old),
            _body=lambda key:tuple([BG if tuple(key)==old else FG]*len(INTERIOR_POINTS)),
            _model=lambda teachers:model,
            _paint_support=lambda model,values:dict(passed=all(v==FG for v in values),
                max_original_paint_distance=0 if all(v==FG for v in values) else 300))
        with patch('scripts.source_full_spike_phase.SourceLocalBackground') as background:
            background.return_value.predict.return_value=dict(valid=True,prediction=BG)
            proof=field.probe(old,original)
        self.assertGreaterEqual(len(proof['qualified_alternatives']),2,proof)
        self.assertIsNone(proof['proposed'])

    def test_original_lists_and_models_and_returned_proofs_are_isolated(self):
        values=fixture();before=deepcopy(values[3]);field=evidence(values)
        model=deepcopy((field.filled.library.anchors,field.filled.library.models))
        proof=field.probe(values[5],values[3]);self.assertEqual(proof['proposed'],values[4])
        proof['candidates'].clear()
        self.assertEqual(field.probe(values[5],values[3])['proposed'],values[4])
        self.assertEqual(before,values[3])
        self.assertEqual(model,(field.filled.library.anchors,field.filled.library.models))


if __name__=='__main__':
    main(verbosity=2)
