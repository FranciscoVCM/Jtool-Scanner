"""Foreground sprite identity can transfer without matching old sky colours."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_directional_body import SourceDirectionalBodyEvidence, _DirectedRGBField
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_hollow_glyphs import HollowGlyphEvidence
from scripts.source_interior_glyphs import INTERIOR_POINTS, SourceInteriorGlyphEvidence, _oriented
from scripts.source_sampling import SourceFrame
from tests.test_source_directional_texture import textured_scene
from tests.test_source_interior_glyphs import scene


def changed_background(*, rotation=0, scale=1, transform=lambda c:c,
                       foreground=(210,150,70), background=(20,30,60),
                       new_background=(140,70,180)):
    image, _, _, original, key = textured_scene(rotation=rotation,
        transform=transform, foreground=foreground, background=background)
    raster = Image.frombytes('RGB', (800,608), image.data)
    _, x, y = key
    for py in range(max(0,y-40),min(608,y+72)):
        for px in range(max(0,x-40),min(800,x+72)):
            if raster.getpixel((px,py)) == transform(background):
                raster.putpixel((px,py),transform(new_background))
    if scale != 1:
        raster = raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image = RGBImage(raster.width,raster.height,raster.tobytes())
    room = Box(0,0,image.width,image.height)
    return image,room,SourceFrame(image,room),original,key


def evidence(values, cls=SourceDirectionalBodyEvidence, **kwargs):
    _,_,frame,original,_ = values
    return cls(FilledGlyphEvidence(frame,original),original,source_grid=(25,19),**kwargs)


class SourceDirectionalBodyTests(TestCase):
    def test_transfer_across_unmatched_background_directions_palettes_and_scales(self):
        transforms=(lambda c:c,lambda c:tuple(255-v for v in c),
                    lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(v*.4) for v in c))
        for rotation,transform in enumerate(transforms):
            for scale in (1,1.25):
                with self.subTest(rotation=rotation,scale=scale):
                    values=changed_background(rotation=rotation,scale=scale,transform=transform)
                    old=evidence(values,SourceInteriorGlyphEvidence,require_directional_texture=True).support(values[4])
                    self.assertFalse(old['passed'])
                    proof=evidence(values).support(values[4])
                    self.assertTrue(proof['passed'],proof)
                    self.assertTrue(proof['directional_body_alternative'])
                    self.assertTrue(proof['no_background_absence_or_hollow_claim'])

    def test_existing_strict_positive_proof_is_preserved_entirely(self):
        for rotation in range(4):
            values=textured_scene(rotation=rotation)
            old=evidence(values,SourceInteriorGlyphEvidence,require_directional_texture=True).support(values[4])
            self.assertTrue(old['passed'])
            self.assertEqual(evidence(values).support(values[4]),old)

    def test_false_option_preserves_legacy_channel_without_new_geometry(self):
        values=scene()
        old=evidence(values,SourceInteriorGlyphEvidence,require_directional_texture=False).support(values[4])
        field=evidence(values,require_directional_texture=False)
        with patch.object(field,'geometry',side_effect=AssertionError('Legacy called new geometry')):
            self.assertEqual(field.support(values[4]),old)

    def test_rgb_isoluminant_foreground_and_original_background(self):
        values=changed_background(foreground=(150,80,65),background=(80,120,40))
        self.assertEqual(Image.new('RGB',(1,1),(150,80,65)).convert('L').getpixel((0,0)),
                         Image.new('RGB',(1,1),(80,120,40)).convert('L').getpixel((0,0)))
        self.assertTrue(evidence(values).support(values[4])['passed'])

    def test_no_three_same_direction_teachers_is_unknown_not_absence(self):
        values=scene();proof=evidence(values).support(values[4])
        self.assertFalse(proof['passed']);self.assertTrue(proof['unknown'])
        self.assertTrue(proof['no_retirement'])

    def test_palette_permutation_cannot_substitute_for_original_sprite_texture(self):
        values=changed_background();image,room,_,original,key=values;kind,x,y=key
        raster=Image.frombytes('RGB',(800,608),image.data)
        positions=[(x+a,y+b) for a,b in (_oriented(kind,*p) for p in INTERIOR_POINTS)]
        paints=[raster.getpixel(p) for p in positions]
        for point,rgb in zip(positions,reversed(paints)):raster.putpixel(point,rgb)
        changed=RGBImage(800,608,raster.tobytes())
        self.assertFalse(evidence((changed,room,SourceFrame(changed,room),original,key)).support(key)['passed'])

    def test_marker_body_cover_abstains_without_deleting_any_original(self):
        values=list(changed_background());values[3]=list(values[3])
        _,x,y=values[4];values[3].append(SimpleNamespace(type_id=12,x=x,y=y))
        before=deepcopy(values[3]);self.assertFalse(evidence(values).support(values[4])['passed'])
        self.assertEqual(values[3],before)

    def test_unknown_capture_padding_cannot_supply_a_boundary(self):
        image,_,frame,original,key=changed_background()
        raster=Image.frombytes('RGB',(800,608),image.data).crop((8,8,792,600))
        physical=RGBImage(raster.width,raster.height,raster.tobytes());room=Box(0,0,physical.width,physical.height)
        world=SourceFrame(physical,room,extent=Box(-8,-8,800,608),canonical=RGBImage(800,608,frame.canonical_rgb))
        field=evidence((physical,room,world,original,key));proof=field.support((3,0,0))
        self.assertFalse(proof['passed']);self.assertTrue(proof['unknown'])

    def test_unsupported_interior_paint_and_16px_impostor_are_rejected(self):
        image,room,_,original,key=changed_background();kind,x,y=key
        for mini in (False,True):
            raster=Image.frombytes('RGB',(800,608),image.data)
            if mini:
                ImageDraw.Draw(raster).rectangle((x,y,x+31,y+31),fill=(140,70,180))
                tip=VERTICES[kind][0]
                ImageDraw.Draw(raster).polygon([(x+tip[0]+(a-tip[0])/2,y+tip[1]+(b-tip[1])/2)
                    for a,b in VERTICES[kind]],fill=(210,150,70))
            else:
                a,b=_oriented(kind,17,23);raster.putpixel((x+a,y+b),(20,30,60))
            changed=RGBImage(800,608,raster.tobytes())
            with self.subTest(mini=mini):
                self.assertFalse(evidence((changed,room,SourceFrame(changed,room),original,key)).support(key)['passed'])

    def test_geometry_never_mixes_independent_best_phases(self):
        values=changed_background();field=evidence(values);key=values[4]
        # Across phases each face has good measurements, but no common phase
        # has all three. Original thresholds still apply to the conjunction.
        counter=iter(([12,12,0],[12,0,12],[0,12,12])*3)
        counts=[]
        for row in counter:counts.extend(row)
        with patch.object(field.directed_field,'directed',side_effect=counts):
            geometry=field.geometry(key)
        self.assertFalse(geometry['passed'])

    def test_gradient_reuse_does_not_construct_or_claim_hollow_models(self):
        values=changed_background()
        with patch.object(HollowGlyphEvidence,'__init__',side_effect=AssertionError('Hollow models constructed')):
            self.assertTrue(evidence(values).support(values[4])['passed'])
        with self.assertRaisesRegex(ValueError,'immutable source frame'):
            _DirectedRGBField(None)

    def test_geometry_queries_validate_and_cannot_mutate_cached_proofs(self):
        values=changed_background();field=evidence(values);key=values[4]
        proof=field.geometry(list(key));self.assertTrue(proof['passed'])
        proof['passed']=False;proof['phases'].clear()
        self.assertTrue(field.geometry(key)['passed'])
        self.assertTrue(field.geometry(key)['phases'])
        for invalid in (None,(),(2,0,0),(3,True,0),(3,float('nan'),0),(3,0,float('inf'))):
            with self.subTest(key=invalid),self.assertRaisesRegex(ValueError,'full type3..6'):
                field.geometry(invalid)

    def test_both_raw_and_directed_competing_rectangles_independently_abstain(self):
        for raw_closed in (False,True):
            values=changed_background();field=evidence(values)
            raw=[SimpleNamespace(support=12 if raw_closed else 0,unknown=False)]*4
            directed=([12]*3+[0 if raw_closed else 12]*4)*9
            with self.subTest(raw_closed=raw_closed), \
                    patch.object(field.field,'rectangle',return_value=raw), \
                    patch.object(field.directed_field,'directed',side_effect=directed):
                self.assertFalse(field.geometry(values[4])['passed'])

    def test_requirement_remains_explicit_and_boolean(self):
        values=changed_background();_,_,frame,original,_=values
        for value in (None,0,1,'yes',[]):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'boolean'):
                SourceDirectionalBodyEvidence(FilledGlyphEvidence(frame,original),original,
                    source_grid=(25,19),require_directional_texture=value)

    def test_originals_and_returned_proofs_remain_isolated(self):
        values=changed_background();before=deepcopy(values[3]);field=evidence(values)
        proof=field.support(values[4]);self.assertTrue(proof['passed'])
        proof['directed_geometry']['phases'].clear()
        self.assertTrue(field.support(values[4])['directed_geometry']['phases'])
        self.assertEqual(values[3],before)
