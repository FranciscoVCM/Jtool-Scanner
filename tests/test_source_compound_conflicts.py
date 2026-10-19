"""Generic source conflicts: never learn supplied answers or delete by overlap."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts import source_compound_conflicts as conflict
from scripts.source_block_prototypes import SourceBlockLibrary
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_glyph_prototypes import _contains
from scripts.source_sampling import SourceFrame


def scene(*, scale=1, transform=lambda c:c, direction=0, paint_candidate=False,
          background=(20,30,60),foreground=(210,150,70)):
    bg,fg=background,foreground
    raster=Image.new('RGB',(800,608),transform(bg))
    teachers=[(3,96,64),(4,208,64),(6,320,64)]
    group=[(3,224,224),(3,208,256),(3,240,256)]
    base=[(208,288),(240,288)]
    def rotate_point(p):
        x,y=p
        for _ in range(direction):x,y=240-(y-256),256+(x-240)
        return x,y
    rotated=[]
    for t,x,y in group:
        poly=[rotate_point((x+u,y+v)) for u,v in VERTICES[t]]
        kind=t
        for _ in range(direction):kind={3:4,4:6,6:5,5:3}[kind]
        rotated.append((kind,min(a for a,b in poly),min(b for a,b in poly)))
    base=[(min(a for a,b in points),min(b for a,b in points)) for x,y in base
          for points in [[rotate_point(p) for p in ((x,y),(x+32,y),(x+32,y+32),(x,y+32))]]]
    glyphs=teachers+rotated
    for t,x,y in glyphs:
        poly=[(x+u,y+v) for u,v in VERTICES[t]]
        for py in range(y,y+32):
            for px in range(x,x+32):
                if _contains(poly,px+.5,py+.5):raster.putpixel((px,py),transform(fg))
    terrain=[(96,416),(192,416),(288,416)]+base
    if paint_candidate:terrain.append((224,240))
    for x,y in terrain:
        for j in range(32):
            for i in range(32):
                delta=25 if (i+2*j)%17<3 else -15 if (2*i-j)%13<2 else 0
                raster.putpixel((x+i,y+j),transform(tuple(v+delta for v in (185,140,80))))
    if scale!=1:raster=raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image=RGBImage(raster.width,raster.height,raster.tobytes());room=Box(0,0,image.width,image.height)
    frame=SourceFrame(image,room)
    originals=[SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in glyphs]
    originals += [SimpleNamespace(type_id=1,x=x,y=y) for x,y in terrain if (x,y)!=(224,240)]
    originals.append(SimpleNamespace(type_id=1,x=224,y=240))
    cells=[(x+dx,y+dy) for x,y in terrain for dx in (0,16) for dy in (0,16)]
    material=dict(selected_clusters=[0],cluster_centers=[dict(zip(('r','g','b'),transform(c))) for c in (fg,bg)],
        tip_votes={1:3},background_back_votes={1:0},accepted=cells,source_flat_accepted_cells=[],
        intrinsic_geometry_appearance_evidence_retained=cells)
    return image,room,frame,originals,material


def run_scene(values,**kwargs):
    image,room,frame,originals,material=values
    return conflict.source_compound_conflicts(image,room,originals,source_grid=(25,19),
        source_frame=frame,source_material=material,**kwargs)


class SourceCompoundConflictTests(TestCase):
    def test_source_only_conflict_and_ten_other_originals_unchanged(self):
        values=scene();before=deepcopy(values[3:])
        retired,proof=run_scene(values)
        self.assertEqual(retired,{(1,224,240)},proof)
        self.assertEqual(values[3:],before)
        self.assertTrue(proof['no_objects_emitted'])
        self.assertTrue(proof['no_origin_changes'])

    def test_all_directions_palette_polarity_dim_and_fractional_scale(self):
        transforms=(lambda c:c,lambda c:tuple(255-v for v in c),
            lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(v*.25) for v in c))
        for direction,transform in enumerate(transforms):
            for scale in (1,1.25):
                with self.subTest(direction=direction,scale=scale):
                    retired,proof=run_scene(scene(scale=scale,transform=transform,direction=direction))
                    self.assertEqual(retired,{(1,224,240)},proof)

    def test_real_rectangle_and_partial_glyph_occlusion_are_preserved(self):
        retired,proof=run_scene(scene(paint_candidate=True))
        self.assertNotIn((1,224,240),retired,proof)

    def test_isoluminant_materials_are_not_collapsed_to_grayscale(self):
        bg,fg=(80,120,40),(150,80,65)
        self.assertEqual(Image.new('RGB',(1,1),bg).convert('L').getpixel((0,0)),
                         Image.new('RGB',(1,1),fg).convert('L').getpixel((0,0)))
        values=scene(background=bg,foreground=fg)
        self.assertEqual(run_scene(values)[0],{(1,224,240)})

    def test_original_nonterrain_marker_is_a_veto(self):
        values=scene();values[3].append(SimpleNamespace(type_id=12,x=224,y=240))
        retired,proof=run_scene(values)
        self.assertFalse(retired)
        self.assertTrue(any(r.get('abstained')=='original nongeometry overlap' for r in proof['rows']))

    def test_full_spikes_minis_and_nonconflicting_background_locators_never_retired(self):
        values=scene()
        values[3].extend([SimpleNamespace(type_id=2,x=224,y=240),
            SimpleNamespace(type_id=1,x=608,y=400)])
        retired,proof=run_scene(values)
        self.assertEqual(retired,{(1,224,240)},proof)
        self.assertTrue(all(k[0]==1 for k in retired))
        self.assertFalse(any(tuple(r['key'])==(1,608,400) for r in proof['rows']))

    def test_material_and_existing_original_evidence_can_be_reused(self):
        values=scene();image,room,frame,originals,material=values
        spikes=[(d.type_id,d.x,d.y) for d in originals if 3<=d.type_id<=10]
        context=SourceEvidenceContext(image,room,spikes);library=context.glyph_library(image,room,spikes)
        filled=FilledGlyphEvidence(frame,originals,source_library=library)
        polys=[[(a['key'][1]+u,a['key'][2]+v) for u,v in VERTICES[a['key'][0]]] for a in library.anchors]
        blocks=SourceBlockLibrary(library,{(d.x,d.y) for d in originals if d.type_id==1},material['accepted'],polys)
        with patch.object(conflict,'material_cells',side_effect=AssertionError('No duplicate material pass')):
            retired,proof=run_scene(values,source_context=context,source_block_library=blocks,source_filled_evidence=filled)
        self.assertEqual(retired,{(1,224,240)},proof)
        self.assertTrue(proof['source_material_reused'] and proof['source_block_library_reused'] and proof['source_filled_evidence_reused'])

    def test_original_context_rejects_new_fulls_even_if_spikes_did_not_change(self):
        values=scene();image,room,frame,originals,material=values
        context=SourceEvidenceContext(image,room,[(d.type_id,d.x,d.y) for d in originals if 3<=d.type_id<=10])
        run_scene(values,source_context=context)
        originals.append(SimpleNamespace(type_id=1,x=608,y=400))
        with self.assertRaisesRegex(ValueError,'original detections changed'):
            run_scene(values,source_context=context)

    def test_sampling_phase_does_not_move_native_ownership_geometry(self):
        image,room,frame,originals,material=scene(direction=2,scale=1.25)
        spikes=[(d.type_id,d.x,d.y) for d in originals if 3<=d.type_id<=10]
        context=SourceEvidenceContext(image,room,spikes);library=context.glyph_library(image,room,spikes)
        filled=FilledGlyphEvidence(frame,originals,source_library=library)
        query=conflict._ConflictQuery(frame,context,originals,material,library,None,filled)
        query.glyphs()
        registered=[p for p in query.glyph_proofs if p['proof']['passed'] and p['proof'].get('joint_source_phase')]
        self.assertTrue(registered)
        for row in registered:
            t,x,y=row['key']
            self.assertEqual(query.polygons[row['key']],[(x+u,y+v) for u,v in VERTICES[t]])

    def test_reused_block_model_cannot_add_unobserved_teachers(self):
        image,room,frame,originals,material=values=scene()
        spikes=[(d.type_id,d.x,d.y) for d in originals if 3<=d.type_id<=10]
        context=SourceEvidenceContext(image,room,spikes);library=context.glyph_library(image,room,spikes)
        blocks=SourceBlockLibrary(library,{(d.x,d.y) for d in originals if d.type_id==1},material['accepted'],[])
        blocks.models.append(dict(source_teachers=[(736,512)],signature=(0.,)*768))
        with self.assertRaisesRegex(ValueError,'only original source teachers'):
            run_scene(values,source_context=context,source_block_library=blocks)

    def test_reused_filled_model_cannot_add_unobserved_teachers(self):
        image,room,frame,originals,material=values=scene()
        filled=FilledGlyphEvidence(frame,originals)
        filled.library.models.append(dict(native_size=32,original_source_witnesses=[(3,736,512)],signature=(0.,)*768))
        with self.assertRaisesRegex(ValueError,'only original source teachers'):
            run_scene(values,source_filled_evidence=filled)

    def test_proof_mutation_does_not_change_source_or_later_result(self):
        values=scene();expected=run_scene(values)
        retired,proof=run_scene(values);proof['rows'].clear();proof['retired'].clear();retired.clear()
        self.assertEqual(run_scene(values),expected)

    def test_compact_extended_or_mismatched_source_cannot_supply_evidence(self):
        image,room,frame,originals,material=scene()
        retired,proof=conflict.source_compound_conflicts(image,room,originals,source_grid=(19,13),source_frame=frame)
        self.assertFalse(retired);self.assertIn('not qualified',proof['abstained'])
        extended=SourceFrame(image,room,extent=Box(-4,0,room.width+4,room.height),canonical=frame.original_snapshot())
        retired,proof=conflict.source_compound_conflicts(image,room,originals,source_grid=(25,19),source_frame=extended)
        self.assertFalse(retired)
        changed=RGBImage(image.width,image.height,bytes([0])*len(image.data))
        with self.assertRaisesRegex(ValueError,'original source'):
            conflict.source_compound_conflicts(changed,room,originals,source_grid=(25,19),source_frame=frame)

    def test_absent_roles_or_duplicate_glyph_teachers_abstain(self):
        values=scene();values[4]['tip_votes']={}
        self.assertFalse(run_scene(values)[0])
        values=scene();values[3][:]=[values[3][0]]*3+[SimpleNamespace(type_id=1,x=224,y=240)]
        self.assertFalse(run_scene(values)[0])

    def test_text_locator_is_not_an_independent_source_glyph_owner(self):
        image,room,frame,originals,material=scene()
        raster=Image.frombytes('RGB',(image.width,image.height),image.data)
        ImageDraw.Draw(raster).text((512,352),'8',fill=(210,150,70))
        changed=RGBImage(image.width,image.height,raster.tobytes());changed_frame=SourceFrame(changed,room)
        originals.extend([SimpleNamespace(type_id=3,x=512,y=352),SimpleNamespace(type_id=1,x=512,y=352)])
        retired,proof=conflict.source_compound_conflicts(changed,room,originals,source_grid=(25,19),
            source_frame=changed_frame,source_material=material)
        self.assertNotIn((1,512,352),retired)
        text=next(p for p in proof['original_glyph_proofs'] if p['key']==(3,512,352))
        self.assertFalse(text['proof']['passed'])

    def test_cropped_candidate_is_unknown_not_empty(self):
        image,room,frame,originals,material=scene()
        context=SourceEvidenceContext(image,room,[])
        query=conflict._ConflictQuery(frame,context,originals,material,None,None,None)
        self.assertEqual(query.query(SimpleNamespace(type_id=1,x=0,y=0))['abstained'],
                         'incomplete original source footprint')

    def test_raw_rectangle_geometry_veto_does_not_require_recognized_artwork(self):
        image,room,frame,originals,material=scene(paint_candidate=True)
        context=SourceEvidenceContext(image,room,[])
        blocks=SimpleNamespace(support=lambda x,y:dict(passed=False))
        query=conflict._ConflictQuery(frame,context,originals,material,None,blocks,None)
        proof=query.query(SimpleNamespace(type_id=1,x=224,y=240))
        self.assertFalse(proof['retire'])
        self.assertEqual(proof['abstained'],'coherent raw rectangle closure',proof)
