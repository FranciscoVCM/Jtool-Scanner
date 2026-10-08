"""Read-only contour diagnostics preserve RGB, scale independence and input pins."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_contours import SourceContours, probe


def field(foreground=(255,0,0), background=(0,130,0), scale=1):
    image = Image.new("RGB", (192,128), background)
    ImageDraw.Draw(image).rectangle((64,32,127,95), fill=foreground)
    if scale != 1:
        image = image.resize((round(192*scale),round(128*scale)),Image.Resampling.NEAREST)
    return SourceContours(RGBImage(image.width,image.height,image.tobytes()),
                          Box(0,0,image.width,image.height), (192,128))


class SourceContourTests(unittest.TestCase):
    def test_rgb_isoluminant_edge(self):
        edge = field().edge((64,48),(64,80))
        self.assertEqual(edge.support,12)
        self.assertFalse(edge.unknown)

    def test_one_byte_rgb_edge_no_brightness_floor(self):
        edge = field((129,128,128),(128,128,128)).edge((64,48),(64,80))
        self.assertEqual(edge.support,12)

    def test_constant_surface_has_no_edge(self):
        self.assertEqual(field((128,128,128),(128,128,128)).edge((64,48),(64,80)).support,0)

    def test_linear_illumination_is_not_a_boundary(self):
        data=bytes(value for y in range(128) for x in range(192) for value in (x,y,20))
        f=SourceContours(RGBImage(192,128,data),Box(0,0,192,128),(192,128))
        self.assertEqual(f.edge((64,48),(64,80)).support,0)

    def test_reverse_direction_and_cache(self):
        f=field();a=f.edge((64,48),(64,80))
        self.assertIs(a,f.edge((64,48),(64,80)))
        self.assertEqual(a.support,f.edge((64,80),(64,48)).support)

    def test_scale_does_not_multiply_source_witnesses(self):
        edge=field(scale=.25).edge((64,48),(64,80))
        self.assertLess(edge.support,9)
        self.assertEqual(edge.support,len(set(edge.independent_source_positions)))

    def test_clipped_samples_remain_unknown(self):
        edge=field().edge((0,48),(0,80))
        self.assertTrue(edge.unknown)
        self.assertEqual(edge.support,0)

    def test_invalid_dimensions_and_zero_edge(self):
        f=field()
        with self.assertRaises(ValueError):f.edge((32,32),(32,32))
        with self.assertRaises(ValueError):SourceContours(f.image,Box(0,0,0,128))
        with self.assertRaises(ValueError):f.triangle(12,32,32)

    def test_full_and_mini_directions_have_independent_contours(self):
        for type_id in range(3,11):
            with self.subTest(type_id=type_id):
                size=16 if type_id>6 else 32
                direction=type_id-4 if type_id>6 else type_id
                image=Image.new("RGB",(192,128),(25,35,45))
                ImageDraw.Draw(image).polygon([(80+a*size/32,48+b*size/32)
                    for a,b in VERTICES[direction]],fill=(220,190,130))
                f=SourceContours(RGBImage(192,128,image.tobytes()),Box(0,0,192,128),(192,128))
                faces=f.triangle(type_id,80,48)
                self.assertTrue(all(face.support>=9 and not face.unknown for face in faces))

    def test_probe_is_read_only_and_rejects_mismatched_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source.png";result=Path(directory)/"result.json"
            Image.new("RGB",(800,608),(10,20,30)).save(source)
            result.write_text(json.dumps(dict(inputs=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()),
                source_grid=[25,19],room_box=dict(x=0,y=0,width=800,height=608))))
            before=(source.read_bytes(),result.read_bytes())
            record=probe(source,result,[(1,32,32),(7,32,32)])
            self.assertTrue(record["complete"])
            self.assertTrue(record["not_object_identity_or_accuracy_certification"])
            self.assertEqual(before,(source.read_bytes(),result.read_bytes()))
            data=json.loads(result.read_text());data["inputs"]["source_sha256"]="wrong"
            result.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"SHA-256"):probe(source,result,[(1,32,32)])

    def test_compact_mapping_is_explicitly_unqualified(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source.png";result=Path(directory)/"result.json"
            Image.new("RGB",(608,416)).save(source)
            result.write_text(json.dumps(dict(inputs=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()),
                source_grid=[19,13],room_box=dict(x=0,y=0,width=608,height=416))))
            with self.assertRaisesRegex(ValueError,"not qualified"):probe(source,result,[(1,32,32)])
