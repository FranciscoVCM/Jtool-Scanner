"""Read-only source teaching is independent of palette, locator direction and answers."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import SourceGlyphLibrary, SourceGlyphEvidence, probe


PALETTES = [((25,35,45),(220,190,130)), ((220,230,235),(35,45,65)),
            ((0,130,0),(255,0,0)), ((110,125,135),(75,90,100))]


def scene(size=16, palette=0, scale=1., teachers=None):
    background, foreground = PALETTES[palette]
    raster = Image.new("RGB", (800,608), background)
    draw = ImageDraw.Draw(raster)
    teachers = [(160,160),(256,160),(352,160),(448,160)] if teachers is None else teachers
    def triangle(direction, x, y):
        draw.polygon([(x+a*size/32,y+b*size/32) for a,b in VERTICES[direction]], fill=foreground)
    for x,y in teachers:
        triangle(3,x,y)
    positives = []
    for i,d in enumerate((3,4,5,6)):
        x,y = 160+96*i,320
        triangle(d,x,y)
        positives.append((d+(4 if size==16 else 0),x,y))
    negatives = []
    for i in range(4):
        x,y = 160+96*i,448
        draw.rectangle((x,y,x+size-1,y+size-1), fill=foreground)
        negatives.append((3+(4 if size==16 else 0),x,y))
    if scale != 1:
        raster = raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image = RGBImage(raster.width,raster.height,raster.tobytes())
    # Intentionally incorrect direction; pixels must teach Up regardless.
    locators = [(4+(4 if size==16 else 0),x,y) for x,y in teachers]
    return image, Box(0,0,image.width,image.height), locators, positives, negatives


class SourceGlyphPrototypeTests(unittest.TestCase):
    def test_portable64_positives64_negatives_and_wrong_locator_direction(self):
        for size in (16,32):
            for palette in range(4):
                for scale in (1.,1.25):
                    with self.subTest(size=size,palette=palette,scale=scale):
                        image,room,locators,positives,negatives = scene(size,palette,scale)
                        before = hashlib.sha256(image.data).hexdigest()
                        library = SourceGlyphLibrary(image,room,locators)
                        self.assertEqual(len(library.anchors),4)
                        self.assertTrue(all(a["key"][0] == (7 if size==16 else 3) for a in library.anchors))
                        for key in positives:
                            result = library.support(*key)
                            self.assertTrue(result["passed"])
                            self.assertGreaterEqual(result["model"]["independent_regions"],3)
                            self.assertTrue(result["model"]["all_source_pairs_mutually_correlated"])
                            self.assertLessEqual(abs(result["query_phase"][0]),800/room.width)
                            self.assertLessEqual(abs(result["query_phase"][1]),608/room.height)
                        self.assertFalse(any(library.support(*key)["passed"] for key in negatives))
                        self.assertEqual(before,hashlib.sha256(image.data).hexdigest())

    def test_two_examples_cannot_teach_a_model(self):
        image,room,locators,queries,_ = scene(teachers=[(160,160),(256,160)])
        library = SourceGlyphLibrary(image,room,locators)
        self.assertEqual(len(library.anchors),2)
        self.assertEqual(library.models,[])
        self.assertFalse(library.support(*queries[0])["passed"])

    def test_same_region_does_not_supply_three_independent_witnesses(self):
        image,room,locators,queries,_ = scene(teachers=[(160,160),(176,160),(160,176)])
        library = SourceGlyphLibrary(image,room,locators)
        self.assertTrue(all(a["key"][1]//32 == 5 and a["key"][2]//32 == 5 for a in library.anchors))
        self.assertEqual(library.models,[])
        self.assertFalse(library.support(*queries[0])["passed"])

    def test_empty_and_constant_sources_are_not_training_examples(self):
        raster = Image.new("RGB",(800,608),(120,130,140))
        image = RGBImage(800,608,raster.tobytes())
        room = Box(0,0,800,608)
        library = SourceGlyphLibrary(image,room,[(7,160,160),(7,256,160),(7,352,160)])
        self.assertEqual(library.anchors,[])
        self.assertEqual(library.models,[])
        self.assertFalse(library.support(7,256,320)["passed"])

    def test_native_sizes_do_not_borrow_unqualified_size_identity(self):
        image,room,locators,queries,_ = scene(size=32)
        library = SourceGlyphLibrary(image,room,locators)
        self.assertTrue(library.support(*queries[0])["passed"])
        self.assertFalse(library.support(7,queries[0][1],queries[0][2])["passed"])

    def test_clipped_sources_and_queries_remain_unqualified(self):
        image,room,locators,_,_ = scene()
        field = SourceGlyphEvidence(image,room)
        self.assertIsNone(field.owner(7,-8,160))
        library = SourceGlyphLibrary(image,room,locators)
        self.assertFalse(library.support(7,-32,320)["passed"])

    def test_invalid_dimensions_types_and_source_bounds(self):
        image,room,locators,_,_ = scene()
        with self.assertRaises(ValueError):SourceGlyphLibrary(image,Box(0,0,0,608),locators)
        with self.assertRaises(ValueError):SourceGlyphLibrary(image,Box(-1,0,800,608),locators)
        with self.assertRaises(ValueError):SourceGlyphLibrary(image,Box(0,0,801,608),locators)
        with self.assertRaises(ValueError):SourceGlyphLibrary(image,room,[(12,160,160)])
        library = SourceGlyphLibrary(image,room,locators)
        with self.assertRaises(ValueError):library.support(12,256,320)

    def test_probe_verifies_source_and_is_read_only(self):
        image,room,locators,queries,_ = scene()
        with tempfile.TemporaryDirectory() as directory:
            source,result = Path(directory)/"source.png",Path(directory)/"result.json"
            Image.frombytes("RGB",(image.width,image.height),image.data).save(source)
            record = dict(inputs=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()),
                          source_grid=[25,19],room_box=dict(x=0,y=0,width=800,height=608),
                          detections=[dict(type_id=t,x=x,y=y) for t,x,y in locators])
            result.write_text(json.dumps(record))
            before = source.read_bytes(),result.read_bytes()
            output = probe(source,result,queries)
            self.assertTrue(output["read_only"])
            self.assertTrue(output["not_object_emission_map_edit_or_accuracy_certification"])
            self.assertTrue(all(r["evidence"]["passed"] for r in output["rows"]))
            self.assertEqual(before,(source.read_bytes(),result.read_bytes()))
            record["inputs"]["source_sha256"] = "wrong"
            result.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError,"SHA-256"):probe(source,result,queries)

    def test_compact_transform_is_explicitly_unqualified(self):
        with tempfile.TemporaryDirectory() as directory:
            source,result = Path(directory)/"source.png",Path(directory)/"result.json"
            Image.new("RGB",(608,416)).save(source)
            result.write_text(json.dumps(dict(inputs=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()),
                                             source_grid=[19,13])))
            with self.assertRaisesRegex(ValueError,"not qualified"):probe(source,result,[(7,64,64)])
