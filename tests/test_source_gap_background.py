import unittest

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_gap_background import GapBackgroundEvidence
from scripts.source_sampling import SourceFrame


SKY = (107, 199, 234)
INK = (225, 224, 223)
FRINGE = (82, 146, 182)
GAP = (6, 96, 96)
UP = (3, 112, 96)


def evidence(*, motif='empty', factor=1., owner_poses=(), inverse=False):
    width, height = round(800*factor), round(608*factor)
    invert = lambda rgb: tuple(255-c for c in rgb) if inverse else rgb
    data = bytearray(bytes(invert(SKY))*(width*height))
    for sy in range(round(82*factor), round(133*factor)):
        y = (sy+.5)*608/height
        for sx in range(round(87*factor), round(150*factor)):
            x = (sx+.5)*800/width
            u,d = x-96,y-96
            if motif in ('filled','hollow','base_only','partial'):
                depth = min(2*u,2*(32-u))-d
                ink = ((motif=='filled' and 0<=d<=32 and depth>=0)
                       or (motif=='hollow' and 0<=d<=32 and depth>=0 and (d<1 or depth<1))
                       or (motif=='base_only' and 0<=d<1 and 5<=u<27)
                       or (motif=='partial' and 3<=d<12 and 10<=u<20))
                if ink:
                    i = (sy*width+sx)*3
                    data[i:i+3] = bytes(invert(INK))
            if motif not in ('bridge','detached','one_row','owner_blank') or not 0<=d<32:
                continue
            left,right = 128-d/2,128+d/2
            rgb = SKY
            if motif!='owner_blank' and left<=x<right:
                rgb=INK
            if motif=='bridge' and left-1.5<=x<left:
                rgb=FRINGE
            if motif=='detached' and sx==round(123*factor) and sy==round(103*factor):
                rgb=FRINGE
            if motif=='one_row' and left-1.5<=x<left and sy==round(103*factor):
                rgb=FRINGE
            if motif=='owner_blank' and 122.5<=x<125.5 and 102<=y<105:
                rgb=FRINGE
            i=(sy*width+sx)*3
            data[i:i+3]=bytes(invert(rgb))
    image=RGBImage(width,height,bytes(data))
    return GapBackgroundEvidence(SourceFrame(image,Box(0,0,width,height)),owner_poses=owner_poses)


class SourceGapBackgroundTests(unittest.TestCase):
    def test_open_original_backdrop_for_every_orientation_and_polarity(self):
        for factor in (1.,1.23):
            for inverse in (False,True):
                probe=evidence(factor=factor,inverse=inverse)
                for direction in (3,4,5,6):
                    with self.subTest(factor=factor,inverse=inverse,direction=direction):
                        self.assertTrue(probe.query((direction,96,96))['clear'])

    def test_filled_hollow_thin_base_and_partial_artwork_are_not_erased(self):
        for motif in ('filled','hollow','base_only','partial'):
            for factor in (1.,1.23):
                with self.subTest(motif=motif,factor=factor):
                    self.assertFalse(evidence(motif=motif,factor=factor).query(GAP)['clear'])

    def test_real_opposing_neighbor_can_account_for_consecutive_fringe(self):
        probe=evidence(motif='bridge',owner_poses=[UP])
        result=probe.query(GAP)
        self.assertTrue(result['clear'],result)
        self.assertGreaterEqual(len(result['bridges']),1)
        self.assertTrue(all(b['owner']==UP for b in result['bridges']))
        self.assertFalse(probe.query(UP)['clear'])
        self.assertFalse(evidence(motif='bridge').query(GAP)['clear'])

    def test_single_row_accidental_connection_cannot_authorize_absence(self):
        probe=evidence(motif='one_row',owner_poses=[UP])
        q=probe.query(GAP)
        self.assertFalse(q['clear'],q)
        self.assertEqual(q['qualified_owners'],[UP])

    def test_detached_ink_and_an_unproved_owner_are_preserved(self):
        for motif in ('detached','owner_blank'):
            with self.subTest(motif=motif):
                self.assertFalse(evidence(motif=motif,owner_poses=[UP]).query(GAP)['clear'])

    def test_clipped_original_or_reused_physical_samples_abstain(self):
        self.assertFalse(evidence().query((6,96,0))['clear'])
        self.assertFalse(evidence(factor=.4).query(GAP)['clear'])


if __name__=='__main__':
    unittest.main()
