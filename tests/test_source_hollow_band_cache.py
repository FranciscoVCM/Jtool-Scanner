"""Lazy sample reuse preserves unknowns, directed identities and bounded memory."""
from collections import OrderedDict
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from scripts.source_hollow_glyphs import HollowGlyphEvidence


class HollowBandCacheTests(TestCase):
    def evidence(self, unknown=False):
        obj=object.__new__(HollowGlyphEvidence)
        obj.bands=OrderedDict()
        obj.library=SimpleNamespace(pixel=Mock(return_value=None if unknown else (4,8,12)))
        obj._position=Mock(side_effect=lambda x,y:(int(x),int(y)))
        return obj

    def test_early_stop_samples_only_requested_site_and_reuses_it(self):
        obj=self.evidence();a,b=(100,100),(132,100)
        first=next(obj.band(a,b,2))
        self.assertEqual(obj.library.pixel.call_count,5)
        self.assertEqual(first,next(obj.band(a,b,2)))
        self.assertEqual(obj.library.pixel.call_count,5)
        self.assertEqual(len(list(obj.band(a,b,2))),12)
        self.assertEqual(obj.library.pixel.call_count,60)
        self.assertEqual(len(list(obj.band(a,b,2))),12)
        self.assertEqual(obj.library.pixel.call_count,60)
        self.assertIsInstance(first[1],tuple)

    def test_unknown_samples_stay_unknown_and_are_not_resampled(self):
        obj=self.evidence(unknown=True);a,b=(100,100),(132,100)
        self.assertEqual(next(obj.band(a,b,2)),(None,None))
        self.assertEqual(next(obj.band(a,b,2)),(None,None))
        self.assertEqual(obj.library.pixel.call_count,5)

    def test_direction_and_width_have_independent_samples(self):
        obj=self.evidence();a,b=(100,100),(132,100)
        next(obj.band(a,b,2));next(obj.band(b,a,2));next(obj.band(a,b,1))
        self.assertEqual(obj.library.pixel.call_count,13)
        self.assertEqual(len(obj.bands),3)

    def test_lru_is_bounded_and_eviction_recomputes_same_samples(self):
        obj=self.evidence();a,b=(100,100),(132,100)
        first=next(obj.band(a,b,2))
        for i in range(256):next(obj.band((100,101+i),(132,101+i),2))
        self.assertEqual(len(obj.bands),256)
        self.assertNotIn((a,b,2),obj.bands)
        before=obj.library.pixel.call_count
        self.assertEqual(next(obj.band(a,b,2)),first)
        self.assertEqual(obj.library.pixel.call_count,before+5)
        self.assertEqual(len(obj.bands),256)

    def test_outside_native_band_does_not_sample_source(self):
        obj=self.evidence()
        self.assertEqual(next(obj.band((0,0),(32,0),2)),(None,None))
        obj.library.pixel.assert_not_called()
