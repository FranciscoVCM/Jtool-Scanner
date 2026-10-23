"""Closed material/geometry conjunction, not a room or texture answer lookup."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_directional_body import SourceClosedInteriorGlyphEvidence
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_interior_glyphs import SourceInteriorGlyphEvidence
from scripts.source_sampling import SourceFrame
from tests.test_source_directional_texture import textured_scene


def compound_scene(*, rotation=0, scale=1, transform=lambda c:c,
                   foreground=(224,177,111), background=(18,27,49),
                   outline=(35,39,50), rectangle=False, large_triangle=False):
    """Two differently directed fulls share an ink edge; teachers stay isolated."""
    teachers=[(3,96,64),(4,208,64),(6,320,64),(5,432,64)]
    members=[(3,320,256),(6,336,256)]
    def pose(key):
        kind,x,y=key
        for _ in range(rotation):
            kind={3:4,4:6,6:5,5:3}[kind]
            x,y=768-y,x
        return kind,x,y
    teachers=list(map(pose,teachers));members=list(map(pose,members))
    # Rotate about the origin within a square, then shift the scene vertically
    # only if necessary. This is a scene transform, not a detector answer.
    all_keys=teachers+members
    shift=max(0,max(y+32 for _,x,y in all_keys)-584)
    teachers=[(t,x,y-shift) for t,x,y in teachers]
    members=[(t,x,y-shift) for t,x,y in members]
    raster=Image.new('RGB',(3200,2432),transform(background));draw=ImageDraw.Draw(raster)
    for t,x,y in teachers+members:
        poly=[(round((x+a)*4),round((y+b)*4)) for a,b in VERTICES[t]]
        draw.polygon(poly,fill=transform(foreground))
        draw.line(poly+[poly[0]],fill=transform(outline),width=4)
    target=members[1]
    if rectangle:
        _,x,y=target
        draw.rectangle((4*x,4*y,4*(x+32),4*(y+32)),fill=transform(foreground),outline=transform(outline),width=4)
    if large_triangle:
        kind,x,y=target
        draw.rectangle((4*(x-8),4*(y-8),4*(x+72),4*(y+72)),fill=transform(background))
        poly=[(4*(x+2*a),4*(y+2*b)) for a,b in VERTICES[kind]]
        draw.polygon(poly,fill=transform(foreground));draw.line(poly+[poly[0]],fill=transform(outline),width=4)
    raster=raster.resize((800,608),Image.Resampling.LANCZOS)
    if scale!=1:raster=raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image=RGBImage(raster.width,raster.height,raster.tobytes());room=Box(0,0,image.width,image.height)
    frame=SourceFrame(image,room)
    original=[SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in teachers]
    return image,room,frame,original,target,members


def evidence(values,cls=SourceClosedInteriorGlyphEvidence,**kwargs):
    _,_,frame,original,_,_=values
    return cls(FilledGlyphEvidence(frame,original),original,source_grid=(25,19),**kwargs)


class SourceClosedInteriorTests(TestCase):
    def test_real_flat_shared_edge_needs_no_same_direction_texture(self):
        values=compound_scene()
        old=evidence(values,SourceInteriorGlyphEvidence,require_directional_texture=True).support(values[4])
        self.assertFalse(old['passed']);self.assertTrue(old['unknown'])
        proof=evidence(values).support(values[4])
        self.assertTrue(proof['passed'],proof)
        self.assertTrue(proof['source_closed_body_alternative'])
        self.assertTrue(proof['whole_original_body_AND_directed_edges_required'])

    def test_both_members_survive_shared_edge_without_empty_exterior_requirement(self):
        values=compound_scene();field=evidence(values)
        for key in values[5]:
            with self.subTest(key=key):self.assertTrue(field.support(key)['passed'])

    def test_directions_brightness_polarity_palette_and_fractional_capture(self):
        transforms=(lambda c:c,lambda c:tuple(255-v for v in c),
                    lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(v*.4) for v in c))
        for rotation,transform in enumerate(transforms):
            for scale in (1,1.25):
                with self.subTest(rotation=rotation,scale=scale):
                    values=compound_scene(rotation=rotation,scale=scale,transform=transform)
                    self.assertTrue(evidence(values).support(values[4])['passed'])

    def test_isoluminant_original_rgb_material_not_grayscale(self):
        foreground=(150,80,65);background=(80,120,40)
        self.assertEqual(Image.new('RGB',(1,1),foreground).convert('L').getpixel((0,0)),
                         Image.new('RGB',(1,1),background).convert('L').getpixel((0,0)))
        values=compound_scene(foreground=foreground,background=background,outline=(30,30,30))
        self.assertTrue(evidence(values).support(values[4])['passed'])

    def test_unsigned_interior_alone_cannot_override_failed_directed_geometry(self):
        values=compound_scene();field=evidence(values)
        with patch.object(field,'geometry',return_value={'passed':False}):
            proof=field.support(values[4])
        self.assertFalse(proof['passed']);self.assertTrue(proof['no_retirement'])

    def test_geometry_alone_cannot_override_unknown_material(self):
        values=list(compound_scene());values[3]=values[3][:2]
        field=evidence(values)
        with patch.object(field,'geometry',side_effect=AssertionError('No original material proof')):
            self.assertFalse(field.support(values[4])['passed'])

    def test_legacy_false_option_is_entirely_unchanged(self):
        values=compound_scene();field=evidence(values,require_directional_texture=False)
        old=evidence(values,SourceInteriorGlyphEvidence).support(values[4])
        with patch.object(field,'geometry',side_effect=AssertionError('Legacy called extra geometry')):
            self.assertEqual(field.support(values[4]),old)

    def test_existing_strict_texture_positive_proof_is_entirely_unchanged(self):
        values=textured_scene();image,room,frame,original,key=values
        filled=FilledGlyphEvidence(frame,original)
        old=SourceInteriorGlyphEvidence(filled,original,source_grid=(25,19),require_directional_texture=True).support(key)
        self.assertTrue(old['passed'])
        field=SourceClosedInteriorGlyphEvidence(filled,original,source_grid=(25,19))
        with patch.object(field,'geometry',side_effect=AssertionError('Existing proof changed')):
            self.assertEqual(field.support(key),old)

    def test_rectangle_and_larger_triangle_crops_are_not_full32_objects(self):
        for option in ('rectangle','large_triangle'):
            with self.subTest(option=option):
                values=compound_scene(**{option:True})
                self.assertFalse(evidence(values).support(values[4])['passed'])

    def test_original_marker_cannot_become_a_new_triangle(self):
        values=list(compound_scene());_,x,y=values[4]
        values[3]=values[3]+[SimpleNamespace(type_id=12,x=x,y=y)]
        self.assertFalse(evidence(values).support(values[4])['passed'])

    def test_query_proofs_are_independent_and_teachers_unchanged(self):
        values=compound_scene();field=evidence(values)
        before=deepcopy((field._closed_original,field._closed_filled.original_spikes,
            field._closed_filled.library.anchors,field._closed_filled.library.models))
        proof=field.support(values[4]);self.assertTrue(proof['passed'])
        proof['appearance']['original_teachers']=[];proof['directed_geometry']['passed']=False
        self.assertTrue(field.support(values[4])['directed_geometry']['passed'])
        self.assertEqual((field._closed_original,field._closed_filled.original_spikes,
            field._closed_filled.library.anchors,field._closed_filled.library.models),before)

    def test_compact_grid_abstains_without_extra_geometry(self):
        values=compound_scene();_,_,frame,original,key,_=values
        field=SourceClosedInteriorGlyphEvidence(FilledGlyphEvidence(frame,original),original,source_grid=(19,13))
        with patch.object(field,'geometry',side_effect=AssertionError('Compact queried new geometry')):
            self.assertFalse(field.support(key)['passed'])

    def test_existing_world_crop_padding_cannot_supply_a_closed_edge(self):
        values=compound_scene();image,_,full_frame,original,key,_=values
        raster=Image.frombytes('RGB',(image.width,image.height),image.data)
        raster=raster.crop((0,0,key[1]+16,image.height))
        cropped=RGBImage(raster.width,raster.height,raster.tobytes())
        room=Box(0,0,cropped.width,cropped.height)
        frame=SourceFrame(cropped,room,extent=Box(0,0,800,608),
            canonical=RGBImage(800,608,full_frame.canonical_rgb))
        field=SourceClosedInteriorGlyphEvidence(FilledGlyphEvidence(frame,original),original,source_grid=(25,19))
        with patch.object(field,'geometry',side_effect=AssertionError('Unknown body reached geometry')):
            proof=field.support(key)
        self.assertFalse(proof['passed']);self.assertTrue(proof['unknown'])
        self.assertTrue(proof['no_retirement'])

    def test_wrong_direction_and_small_capture_are_not_answers_from_colour(self):
        values=compound_scene(scale=.75);field=evidence(values);kind,x,y=values[4]
        self.assertTrue(field.support(values[4])['passed'])
        for other in (3,4,5,6):
            if other!=kind:
                with self.subTest(direction=other):self.assertFalse(field.support((other,x,y))['passed'])

    def test_no_unmatched_background_alternative_is_implicitly_activated(self):
        from tests.test_source_directional_body import changed_background
        image,room,frame,original,key=changed_background()
        field=SourceClosedInteriorGlyphEvidence(FilledGlyphEvidence(frame,original),original,source_grid=(25,19))
        old=SourceInteriorGlyphEvidence(FilledGlyphEvidence(frame,original),original,
            source_grid=(25,19),require_directional_texture=True).support(key)
        self.assertFalse(old['passed'])
        self.assertEqual(field.support(key),old)

    def test_later_caller_marker_move_cannot_remove_original_body_cover(self):
        values=list(compound_scene());_,x,y=values[4]
        marker=SimpleNamespace(type_id=12,x=x,y=y)
        values[3]=values[3]+[marker]
        field=evidence(values)
        marker.x+=128
        self.assertFalse(field.support(values[4])['passed'])

    def test_later_caller_spike_move_cannot_reteach_the_lazy_view(self):
        values=compound_scene();expected=evidence(values).support(values[4])
        field=evidence(values)
        values[3][0].x+=16
        self.assertEqual(field.support(values[4]),expected)
