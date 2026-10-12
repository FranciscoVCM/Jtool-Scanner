"""Source calibration is not permission to emit an unsupported new mini-block."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_geometry_pipeline import joint_proposals
from scripts.source_material_evidence import SourceRectangles
from scripts.source_material_patterns import _NewCellEvidence, pattern_cells


def teacher_scene(kind, palette=0, scale=1., shift=0):
    palettes = [((25,35,45),(220,190,130)), ((220,230,235),(35,45,65)),
                ((0,130,0),(255,0,0)), ((110,125,135),(75,90,100))]
    background, foreground = [tuple(max(0,min(255,c+shift)) for c in rgb)
                              for rgb in palettes[palette]]
    raster = Image.new('RGB',(800,608),background)
    draw = ImageDraw.Draw(raster)
    cells = {(160+16*i,160) for i in range(5)}
    for x,y in cells:
        if kind == 'textured_strip':
            for dy in range(16):
                for dx in range(16):
                    factor = .86 if (dx//2+dy//2)%2 else 1.
                    draw.point((x+dx,y+dy),fill=tuple(round(b+factor*(f-b))
                        for b,f in zip(background,foreground)))
        elif kind == 'triangles':
            draw.polygon([(x,y),(x+15,y+8),(x,y+15)],fill=foreground)
        else:
            draw.rectangle((x,y,x+15,y+15),fill=foreground)
    raster = raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image = RGBImage(raster.width,raster.height,raster.tobytes())
    room = Box(0,0,raster.width,raster.height)
    diag = dict(selected_clusters=[0],
        cluster_centers=[dict(zip(('r','g','b'),rgb)) for rgb in (foreground,background)],
        native16_primitive=sorted(cells),closed_cells=[],strip_cells=sorted(cells))
    return image,room,cells,diag


class SourceNewCellCertaintyTests(TestCase):
    def evaluate(self, kind, palette=0, scale=1., shift=0, mode='local'):
        image,room,cells,diag = teacher_scene(kind,palette,scale,shift)
        with patch('scripts.source_material_patterns.boundary_primitives',return_value=(cells,diag)), \
             patch('scripts.source_material_patterns.container_primitives',return_value=(cells,diag)):
            accepted,proof = pattern_cells(image,room,[],mode=mode)
        return cells,accepted,proof

    def test_joined_triangles_keep_calibration_but_cannot_teach_new_solid(self):
        for palette in range(4):
            for scale in (1.,1.25):
                with self.subTest(palette=palette,scale=scale):
                    cells,accepted,proof = self.evaluate('triangles',palette,scale)
                    self.assertTrue(cells<=accepted,'Do not alter existing pose/calibration evidence')
                    certain = set(map(tuple,proof.get('source_new_cell_certainty',accepted)))
                    self.assertFalse(cells&certain)

    def test_real_narrow_texture_retained_across_rgb_polarity_brightness_scale(self):
        for palette in range(4):
            for scale in (1.,1.25):
                for shift in (-10,0,10):
                    with self.subTest(palette=palette,scale=scale,shift=shift):
                        cells,accepted,proof = self.evaluate('textured_strip',palette,scale,shift)
                        self.assertTrue(cells<=accepted)
                        self.assertTrue(cells<=set(map(tuple,proof.get('source_new_cell_certainty',accepted))))

    def test_intrinsic_and_flat_calibration_remain_available(self):
        for kind,mode in (('textured_strip','intrinsic'),('flat','intrinsic'),('flat','local')):
            with self.subTest(kind=kind,mode=mode):
                cells,accepted,proof = self.evaluate(kind,mode=mode)
                self.assertTrue(cells<=accepted)
                self.assertTrue(cells<=set(map(tuple,proof.get('source_new_cell_certainty',accepted))))

    def test_new_mini_certainty_does_not_rewrite_raw_material_or_old_objects(self):
        image = RGBImage(800,608,bytes(800*608*3))
        intrinsic,qualified,unknown = (64,64),(128,128),(192,192)
        old = SimpleNamespace(type_id=2,x=256,y=256)
        raw = {intrinsic,qualified,unknown}
        material = dict(accepted=sorted(raw),source_new_cell_certainty=[qualified],
            intrinsic_geometry_appearance_evidence_retained=[intrinsic])
        with patch('scripts.source_geometry_pipeline.source_size_repair',return_value=(set(),set(),
                {'source_calibration':{'accepted':[intrinsic]}})), \
             patch('scripts.source_geometry_pipeline.material_cells',return_value=(raw,material)):
            proposed,rejected,proof = joint_proposals(image,Box(0,0,800,608),[old])
        self.assertEqual(proposed,{(2,*intrinsic),(2,*qualified)})
        self.assertEqual(rejected,set())
        self.assertEqual(proof['source_material']['accepted'],sorted(raw))
        self.assertEqual((old.type_id,old.x,old.y),(2,256,256))

    def phase_field(self, nominal):
        image = RGBImage(1000,760,bytes(1000*760*3))
        field = SourceRectangles(image,Box(0,0,1000,760))
        evidence = _NewCellEvidence(field,bytes(800*608*3),lambda rgb:1,{0})
        def rectangle(x,y,size=32):
            support = ([12]*4 if size==32 and (x,y)==(160.8,159.2) else
                       nominal if size==32 and (x,y)==(160,160) else [0]*4)
            return [SimpleNamespace(support=n,unknown=False) for n in support]
        return field,evidence,rectangle

    def test_one_original_source_pixel_completes_only_an_already_supported_frame(self):
        field,evidence,rectangle = self.phase_field([12,12,12,8])
        with patch.object(field.contours,'rectangle',side_effect=rectangle) as query:
            self.assertFalse(evidence.majority((176,176)))
            self.assertTrue(evidence.closed_rectangle((176,176)))
            calls = query.call_count
            self.assertTrue(evidence.closed_rectangle((176,176)))
            self.assertEqual(query.call_count,calls,'Reuse the scan-local geometric proof')
            self.assertTrue(evidence.rectangular_teacher((176,176)))

    def test_shift_cannot_promote_a_two_face_background_frame(self):
        field,evidence,rectangle = self.phase_field([12,8,12,8])
        with patch.object(field.contours,'rectangle',side_effect=rectangle) as query:
            self.assertFalse(evidence.closed_rectangle((176,176)))
            self.assertNotIn((160.8,159.2,32),[call.args for call in query.call_args_list])

    def test_hollow_rectangle_priority_does_not_waive_independent_distributed_regions(self):
        field,evidence,rectangle = self.phase_field([12,12,12,8])
        cells = [(160,160),(176,160),(160,176)]
        with patch.object(field.contours,'rectangle',side_effect=rectangle):
            pattern = lambda *p: {'flat':False}
            self.assertEqual(evidence.seeds([(cells[0],cells)],pattern,'local'),[cells[0]])
            self.assertEqual(evidence.seeds([(cells[0],cells)],pattern,'distributed'),[])
