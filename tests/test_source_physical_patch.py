"""Covered physical geometry is independent of colour and never implies BG."""
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import _contains
from scripts.source_physical_patch import physical_exclusive_patch
from scripts.source_sampling import SourceFrame


def frame(width=800,height=608,*,offset=0,rgb=(0,0,0)):
    image=RGBImage(width+2*offset,height+2*offset,bytes(rgb)*(width+2*offset)*(height+2*offset))
    return SourceFrame(image,Box(offset,offset,width,height))


class SourcePhysicalPatchTests(TestCase):
    def test_all320_covered_geometry_domains_and_default_argument_equality(self):
        known=0
        for width,height in ((800,608),(1000,760),(980,747),(1200,912),(600,456)):
            for offset in (0,9):
                source=frame(width,height,offset=offset)
                for kind in (3,4,5,6):
                    for amount in (8,16):
                        for dx,dy in ((amount,0),(-amount,0),(0,amount),(0,-amount)):
                            old=(kind,200,200);new=(kind,200+dx,200+dy)
                            proof=physical_exclusive_patch(source,old,new)
                            self.assertEqual(proof,physical_exclusive_patch(source,old,new,excluded_polygons=[]))
                            if not proof['known']:
                                continue
                            known+=1
                            a=[(200+u,200+v) for u,v in VERTICES[kind]]
                            b=[(new[1]+u,new[2]+v) for u,v in VERTICES[kind]]
                            self.assertEqual(len(proof['samples']),9)
                            self.assertEqual(len({tuple(s['physical']) for s in proof['samples']}),9)
                            for sample in proof['samples']:
                                self.assertEqual(source.original_position(*sample['native']),sample['physical'])
                                self.assertTrue(_contains(a,*sample['native']))
                                self.assertFalse(_contains(b,*sample['native']))
        self.assertGreaterEqual(known,280)

    def test_protected_neighbour_selection_reads_no_RGB(self):
        source=frame(1000,760)
        old,new=(4,232,240),(4,224,240)
        other=[(288,240),(256,224),(256,256)]
        before=physical_exclusive_patch(source,old,new)
        self.assertTrue(any(_contains(other,*s['native']) for s in before['samples']))
        with patch.object(SourceFrame,'original_sample',side_effect=AssertionError('RGB read')), \
                patch.object(SourceFrame,'original_pixel',side_effect=AssertionError('RGB read')):
            after=physical_exclusive_patch(source,old,new,excluded_polygons=[other])
        self.assertTrue(after['known'])
        self.assertTrue(all(not _contains(other,*s['native']) for s in after['samples']))
        self.assertNotEqual(before['center'],after['center'])
        self.assertEqual(after,physical_exclusive_patch(frame(1000,760,rgb=(255,10,90)),old,new,
            excluded_polygons=[other]))

    def test_unknown_full_exclusion_and_bad_geometry_cannot_supply_samples(self):
        source=frame(1000,760)
        cover=[(0,0),(800,0),(800,608),(0,608)]
        self.assertFalse(physical_exclusive_patch(source,(4,232,240),(4,224,240),
            excluded_polygons=[cover])['known'])
        self.assertFalse(physical_exclusive_patch(frame(),(6,64,56),(6,64,48))['known'])
        self.assertFalse(physical_exclusive_patch(source,(6,-40,-40),(6,-40,-48))['known'])
        for invalid in ([(0,0),(1,1)],[(0,0),(1,float('nan')),(2,2)]):
            with self.assertRaises(ValueError):
                physical_exclusive_patch(source,(4,232,240),(4,224,240),excluded_polygons=[invalid])
        for old,new in (((6,0,0),(6,0,0)),((3,0,0),(6,0,0)),
                        ((6,True,0),(6,0,8)),((6,0,float('nan')),(6,0,8))):
            with self.assertRaises(ValueError):
                physical_exclusive_patch(source,old,new)
