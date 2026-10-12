"""Independent source containers qualify texture without teaching from new output."""
from unittest import TestCase

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_material_evidence import SourceRectangles
from scripts.source_material_patterns import _NewCellEvidence


class SourceBoundaryTeacherCertaintyTests(TestCase):
    def evidence(self, points, counts, bounded, *, scale=1., palette=0, faces=None):
        palettes = [((20,30,40),(220,180,100)), ((230,220,210),(30,45,60)),
                    ((0,130,0),(255,0,0)), ((110,125,135),(75,90,100))]
        background, foreground = palettes[palette]
        raw = bytearray(bytes(background)*(800*608))
        for (x,y),count in zip(points,counts):
            for i in range(count):
                px,py = x+2+i%12,y+2+i//12
                start = (py*800+px)*3
                raw[start:start+3] = bytes(foreground)
        image = RGBImage(round(800*scale),round(608*scale),
                         bytes(round(800*scale)*round(608*scale)*3))
        field = SourceRectangles(image,Box(0,0,image.width,image.height))
        nearest = lambda rgb: int(sum((a-b)**2 for a,b in zip(rgb,foreground)) >
                                  sum((a-b)**2 for a,b in zip(rgb,background)))
        containers = [dict(cells=[p],faces=faces or [(12,False)]*3+[(0,True)])
                      for p in bounded]
        evidence = _NewCellEvidence(field,bytes(raw),nearest,{0},containers)
        # These patterned interiors lack an isolated raw rectangle. Container
        # proofs originate upstream; this isolates their qualification contract.
        evidence.closed_rectangle = lambda p: False
        evidence.rectangular_teacher = lambda p: False
        return evidence

    def seeds(self, evidence, points, mode='distributed'):
        return evidence.seeds([(points[0],points)],lambda *p: {'flat':False},mode)

    def test_three_bounded_material_witnesses_without_raw_rectangle(self):
        points = [(160,160),(192,160),(224,160)]
        for palette in range(4):
            for scale in (1.,1.25):
                with self.subTest(palette=palette,scale=scale):
                    evidence = self.evidence(points,[73,74,72],points,
                                             palette=palette,scale=scale)
                    self.assertEqual(self.seeds(evidence,points),[points[0]])

    def test_two_bounded_peers_bridge_only_a_third_image_edge_witness(self):
        for border in ((16,80),(784,80),(80,16),(80,592)):
            points = [(160,160),(192,160),border]
            with self.subTest(border=border):
                evidence = self.evidence(points,[73,72,20],points[:2])
                self.assertEqual(self.seeds(evidence,points),[points[0]])

    def test_unbounded_interior_witness_is_not_a_clipped_frame(self):
        points = [(160,160),(192,160),(224,160)]
        for interior in ((32,80),(752,80),(80,32),(80,560),(224,160)):
            for count in (20,73):
                trial = points[:2]+[interior]
                with self.subTest(interior=interior,count=count):
                    evidence = self.evidence(trial,[73,72,count],trial[:2])
                    self.assertEqual(self.seeds(evidence,trial),[])

    def test_bridge_requires_three_original_witnesses_and_two_bounded_regions(self):
        cases = [([(160,160),(16,80)],[(160,160)]),
                 ([(160,160),(176,160),(16,80)],[(160,160),(176,160)]),
                 ([(160,160),(16,80),(16,112)],[(160,160)])]
        for points,bounded in cases:
            with self.subTest(points=points):
                evidence = self.evidence(points,[73]*len(points),bounded)
                for mode in ('local','distributed'):
                    self.assertEqual(self.seeds(evidence,points,mode),[])

    def test_exact_color_tie_needs_independent_container_geometry(self):
        point = (160,160)
        self.assertFalse(self.evidence([point],[72],[]).majority(point))
        self.assertTrue(self.evidence([point],[72],[point]).majority(point))
        self.assertFalse(self.evidence([point],[71],[point]).majority(point))
        self.assertTrue(self.evidence([point],[73],[]).majority(point))

    def test_weak_or_unknown_container_faces_do_not_qualify_ties(self):
        point = (160,160)
        for faces in ([(12,False)]*2+[(8,False)]*2,
                      [(12,False)]*2+[(12,True),(12,True)]):
            with self.subTest(faces=faces):
                evidence = self.evidence([point],[72],[point],faces=faces)
                self.assertFalse(evidence.majority(point))

    def test_three_bounded_cells_in_one_region_do_not_qualify_distributed_model(self):
        points = [(160,160),(176,160),(160,176)]
        evidence = self.evidence(points,[73]*3,points)
        self.assertEqual(self.seeds(evidence,points,'local'),[points[0]])
        self.assertEqual(self.seeds(evidence,points),[])

    def test_old_raw_rectangular_path_and_flat_models_remain_available(self):
        points = [(160,160),(192,160),(224,160)]
        evidence = self.evidence(points,[73]*3,[])
        evidence.rectangular_teacher = lambda p: True
        self.assertEqual(self.seeds(evidence,points),[points[0]])
        self.assertEqual(evidence.seeds([(points[0],[points[0]])],
                                       lambda *p: {'flat':True},'distributed'),[points[0]])

    def test_existing_four_argument_constructor_remains_compatible(self):
        image = RGBImage(800,608,bytes(800*608*3))
        evidence = _NewCellEvidence(SourceRectangles(image,Box(0,0,800,608)),
                                    image.data,lambda rgb:1,{0})
        self.assertFalse(evidence.majority((160,160)))
