"""Adversarial training invariants for scan-local source prototype groups."""
from math import cos, radians, sin
import unittest

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from tests.test_source_glyph_prototypes import scene


class SourceGlyphTrainingTests(unittest.TestCase):
    def test_correlated_chain_is_not_a_mutually_matching_model(self):
        raster = Image.new("RGB",(800,608),(0,0,0))
        draw = ImageDraw.Draw(raster)
        locators = []
        for i,angle in enumerate((0,20,40)):
            x,y = 160+96*i,160
            color = (round(200*cos(radians(angle))),round(200*sin(radians(angle))),0)
            draw.polygon([(x+a/2,y+b/2) for a,b in VERTICES[3]],fill=color)
            locators.append((7,x,y))
        image = RGBImage(800,608,raster.tobytes())
        library = SourceGlyphLibrary(image,Box(0,0,800,608),locators)
        self.assertEqual(len(library.anchors),3)
        self.assertGreaterEqual(library.pair_scores[0,1],.9)
        self.assertGreaterEqual(library.pair_scores[1,2],.9)
        self.assertLess(library.pair_scores[0,2],.9)
        self.assertEqual(library.models,[])

    def test_duplicate_locators_do_not_supply_three_source_witnesses(self):
        image,room,locators,queries,_ = scene(teachers=[(160,160)])
        library = SourceGlyphLibrary(image,room,locators*3)
        self.assertEqual(len(library.anchors),1)
        self.assertEqual(library.models,[])
        self.assertFalse(library.support(*queries[0])["passed"])

    def test_querying_does_not_add_training_examples(self):
        image,room,locators,queries,negatives = scene()
        library = SourceGlyphLibrary(image,room,locators)
        before_anchors = list(library.anchors)
        before_models = list(library.models)
        for key in queries+negatives:
            library.support(*key)
        self.assertEqual(library.anchors,before_anchors)
        self.assertEqual(library.models,before_models)

    def test_locator_order_does_not_change_source_models(self):
        image,room,locators,queries,_ = scene()
        first = SourceGlyphLibrary(image,room,locators)
        second = SourceGlyphLibrary(image,room,reversed(locators))
        self.assertEqual(first.anchors,second.anchors)
        self.assertEqual(first.models,second.models)
        self.assertEqual(first.support(*queries[0]),second.support(*queries[0]))
