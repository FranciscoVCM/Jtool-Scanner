"""Independent source teachers, whole-frame negatives and exact polygon pruning."""
from copy import deepcopy
from math import cos, radians, sin
from unittest import TestCase
from unittest.mock import patch

from PIL import Image
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_glyph_prototypes import SourceGlyphLibrary, _contains
from scripts.source_block_prototypes import SourceBlockLibrary, _glyph_pixels_in_frame


TEACHERS = [(128,128), (256,128), (384,128)]


def scene(background=(20,30,45), foreground=(190,150,90), scale=1):
    image = Image.new('RGB', (800,608), background)
    for x, y in TEACHERS+[(256,320),(384,320)]:
        attenuation = .6 if (x,y)==(384,320) else 1
        for j in range(32):
            for i in range(32):
                delta = 35 if (i+2*j)%17<3 else -15 if (2*i-j)%13<2 else 0
                rgb = tuple(max(0,min(255,round((c+delta)*attenuation))) for c in foreground)
                image.putpixel((x+i,y+j), rgb)
    if scale != 1:
        image = image.resize((round(800*scale),round(608*scale)), Image.Resampling.BILINEAR)
    source = RGBImage(image.width,image.height,image.tobytes())
    library = SourceGlyphLibrary(source,Box(0,0,source.width,source.height),[])
    cells = {(x+dx,y+dy) for x,y in TEACHERS for dx in (0,16) for dy in (0,16)}
    return library, cells


class SourceBlockPrototypeTests(TestCase):
    def test_portable_texture_gain_and_whole_frame_shift_negatives(self):
        palettes = [((20,30,45),(190,150,90)), ((220,230,235),(70,90,110)),
                    ((0,130,0),(220,10,10)), ((35,45,50),(80,105,110))]
        for background, foreground in palettes:
            for scale in (1,1.25):
                with self.subTest(background=background,scale=scale):
                    library,cells=scene(background,foreground,scale)
                    model=SourceBlockLibrary(library,TEACHERS,cells,[])
                    self.assertTrue(model.support(256,320)['passed'])
                    self.assertTrue(model.support(384,320)['passed'])
                    self.assertFalse(model.support(272,320)['passed'])
                    self.assertFalse(model.support(512,320)['passed'])

    def test_original_pose_without_four_source_quarters_is_not_a_teacher(self):
        library,cells=scene();cells.remove((384,144))
        model=SourceBlockLibrary(library,TEACHERS,cells,[])
        self.assertNotIn((384,128),model.teachers)
        self.assertEqual(model.models,[])

    def test_duplicate_poses_do_not_supply_independent_teachers(self):
        library,cells=scene()
        model=SourceBlockLibrary(library,[TEACHERS[0]]*3,cells,[])
        self.assertEqual(model.teachers,[TEACHERS[0]])
        self.assertEqual(model.models,[])

    def test_query_and_returned_proof_mutation_cannot_change_teachers(self):
        library,cells=scene();model=SourceBlockLibrary(library,TEACHERS,cells,[])
        teachers,models=deepcopy(model.teachers),deepcopy(model.models)
        expected=model.support(256,320);altered=model.support(256,320)
        altered['source_teachers'].clear();altered['phase'][0]=999;altered['passed']=False
        self.assertEqual(model.support(256,320),expected)
        self.assertEqual(model.teachers,teachers);self.assertEqual(model.models,models)

    def test_competing_source_glyph_excludes_teacher_not_other_objects(self):
        library,cells=scene()
        polygon=[(128,128),(160,128),(144,160)]
        original=deepcopy(cells)
        model=SourceBlockLibrary(library,TEACHERS,cells,[polygon])
        self.assertNotIn((128,128),model.teachers)
        self.assertEqual(cells,original)
        self.assertEqual(model.models,[])

    def test_clipped_teachers_and_queries_abstain(self):
        library,cells=scene();cells.update({(-16,0),(0,0),(-16,16),(0,16)})
        model=SourceBlockLibrary(library,TEACHERS+[(-16,0)],cells,[])
        self.assertNotIn((-16,0),model.teachers)
        self.assertFalse(model.support(-64,0)['passed'])

    def test_polygon_pruning_exactly_matches_pixel_centre_exhaustion(self):
        polygons=[[(0,0),(32,0),(16,32)], [(15.5,15.5),(16.5,15.5),(16,16.5)],
                  [(32,0),(48,0),(40,16)], [(-8,-8),(8,-8),(0,8)],
                  [(200,200),(232,200),(216,232)]]
        bounded=[(p,min(x for x,y in p),min(y for x,y in p),max(x for x,y in p),max(y for x,y in p)) for p in polygons]
        for x,y in ((0,0),(16,0),(32,0),(-16,-16),(200,200),(224,208)):
            expected=any(_contains(p,x+i+.5,y+j+.5) for p in polygons for j in range(32) for i in range(32))
            self.assertEqual(_glyph_pixels_in_frame(x,y,bounded),expected)

    def test_nonoverlapping_polygons_do_not_trigger_pixel_enumeration(self):
        p=[(200,200),(232,200),(216,232)]
        with patch('scripts.source_block_prototypes._contains',side_effect=AssertionError('No overlap')):
            self.assertFalse(_glyph_pixels_in_frame(0,0,[(p,200,200,232,232)]))

    def test_correlated_chain_does_not_create_three_witness_model(self):
        class Library:
            pitch=(1,1)
            def signature(self,t,x,y):
                angle=dict(zip(TEACHERS,(0,20,40)))[x,y]
                return (cos(radians(angle)),sin(radians(angle)))+(0.,)*766
        cells={c for x,y in TEACHERS for c in ((x,y),(x+16,y),(x,y+16),(x+16,y+16))}
        model=SourceBlockLibrary(Library(),TEACHERS,cells,[])
        self.assertEqual(model.models,[])
