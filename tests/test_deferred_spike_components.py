"""Source fields may be retried after aliases, never with weaker thresholds."""
from collections import Counter
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.constants import OBJ_SPIKE_UP, OBJ_SPIKE_DOWN, OBJ_SAVE, OBJ_MINI_SPIKE_UP
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.scanner import (
    Detection, _reconcile_bright_neutral_full_spike_components,
    _retry_deferred_bright_neutral_spike_components,
)


def full(x, y, direction=OBJ_SPIKE_UP):
    return Detection('fixture_full', direction, x, y, .9, Box(x, y, 32, 32))


def source_field(scale=1.0, background=(40, 30, 80), brightness=220):
    image = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(image)
    objects = []
    for i in range(20):
        x, y = 32 + i % 5 * 128, 32 + i // 5 * 128
        draw.polygon([(x+16,y+2), (x+2,y+30), (x+30,y+30)],
                     fill=(brightness,)*3)
        objects.append(full(x, y))
    if scale != 1:
        image = image.resize((round(800*scale), round(608*scale)))
    rgb = RGBImage(image.width, image.height, image.tobytes())
    return rgb, Box(0, 0, image.width, image.height), objects


class DeferredSpikeComponentsTests(unittest.TestCase):
    def test_real_components_defer_inflated_field_and_retry_after_pruning(self):
        for scale in (1.0, 1.25):
            for background, brightness in (((40,30,80),220), ((10,70,30),190)):
                with self.subTest(scale=scale, background=background):
                    image, room, truth = source_field(scale, background, brightness)
                    inflated = truth + [full(i*32, 576, OBJ_SPIKE_DOWN) for i in range(8)]
                    pending = []
                    early = _reconcile_bright_neutral_full_spike_components(
                        inflated, image, room, 8, deferred_fields=pending)
                    self.assertIs(early, inflated)
                    self.assertEqual(len(pending), 1)
                    # After three aliases are pruned, five remain but the
                    # unchanged source-coverage gate now passes.
                    cleaned = truth + inflated[-5:]
                    components, share = pending[0]
                    with patch('jtool_scanner.scanner._connected_components', side_effect=AssertionError('must not rescan pixels')):
                        late = _retry_deferred_bright_neutral_spike_components(cleaned, components, share)
                    self.assertEqual(Counter((d.type_id,d.x,d.y) for d in late),
                                     Counter((d.type_id,d.x,d.y) for d in truth))

    def test_early_accepted_field_is_not_deferred_or_rebuilt_twice(self):
        image, room, truth = source_field()
        pending = []
        result = _reconcile_bright_neutral_full_spike_components(truth, image, room, 8, deferred_fields=pending)
        self.assertEqual(len(result), 20)
        self.assertEqual(pending, [])

    def test_retry_preserves_all_non_full_types_and_uses_same_gate(self):
        components = tuple(full(i*32, 32) for i in range(20))
        marker = Detection('save', OBJ_SAVE, 0, 64, .8, Box(0,64,32,32))
        mini = Detection('mini', OBJ_MINI_SPIKE_UP, 0, 80, .8, Box(0,80,16,16))
        crowded = [full(i*16, 128) for i in range(28)] + [marker, mini]
        self.assertIs(_retry_deferred_bright_neutral_spike_components(crowded, components, .05), crowded)
        cleaned = crowded[:25] + [marker, mini]
        result = _retry_deferred_bright_neutral_spike_components(cleaned, components, .05)
        self.assertIs(result[0], marker)
        self.assertIs(result[1], mini)
        self.assertIs(_retry_deferred_bright_neutral_spike_components(cleaned, components, .20), cleaned)
        empty = [marker]
        self.assertIs(_retry_deferred_bright_neutral_spike_components(empty, components, .05), empty)

    def test_sparse_or_bright_background_evidence_cannot_defer(self):
        image, room, truth = source_field(background=(220,220,220))
        pending = []
        _reconcile_bright_neutral_full_spike_components(truth + truth, image, room, 8, deferred_fields=pending)
        self.assertEqual(pending, [])
        image, room, truth = source_field()
        # An image with no eligible components cannot become evidence merely
        # because its candidate count is large.
        blank = RGBImage(800, 608, bytes((30,40,50))*800*608)
        _reconcile_bright_neutral_full_spike_components(truth + truth, blank, room, 8, deferred_fields=pending)
        self.assertEqual(pending, [])
