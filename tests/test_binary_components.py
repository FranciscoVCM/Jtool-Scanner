"""Portable exact-output regressions for the binary stroke traversal."""

import random
import unittest

from jtool_scanner.binary_components import dilated_ink_components


def flood_reference(foreground, width, height, minimum):
    """Independent deliberately slow pixel oracle, including clipped dilation."""
    expanded = set()
    for index, value in enumerate(foreground):
        if value:
            x, y = index % width, index // width
            expanded.update(
                (xx, yy)
                for yy in range(max(0, y - 1), min(height, y + 2))
                for xx in range(max(0, x - 1), min(width, x + 2))
            )
    result = []
    for y in range(height):
        for x in range(width):
            if (x, y) not in expanded:
                continue
            expanded.remove((x, y))
            pending = [(x, y)]
            points = []
            while pending:
                px, py = pending.pop()
                points.append((px, py))
                neighbors = {
                    (xx, yy)
                    for yy in range(py - 1, py + 2)
                    for xx in range(px - 1, px + 2)
                } & expanded
                expanded.difference_update(neighbors)
                pending.extend(neighbors)
            ink = sum(foreground[py * width + px] for px, py in points)
            if ink >= minimum:
                xs, ys = zip(*points)
                result.append((min(xs), min(ys), max(xs) - min(xs) + 1,
                               max(ys) - min(ys) + 1, ink))
    return result


class BinaryComponentTests(unittest.TestCase):
    def test_all_three_by_three_masks_match_pixel_oracle(self):
        for bits in range(512):
            data = bytearray((bits >> index) & 1 for index in range(9))
            for minimum in (0, 3, 10):
                with self.subTest(bits=bits, minimum=minimum):
                    self.assertEqual(flood_reference(data, 3, 3, minimum),
                                     dilated_ink_components(data, 3, 3, minimum))

    def test_random_masks_thin_images_borders_and_thresholds_match_oracle(self):
        rng = random.Random(130926)
        for width, height in ((1, 1), (1, 23), (27, 1), (8, 9), (33, 47), (61, 49)):
            for trial in range(15):
                density = (trial % 5) / 4
                data = bytearray(rng.random() < density for _ in range(width * height))
                for minimum in (0, 2, 19):
                    with self.subTest(size=(width, height), trial=trial, minimum=minimum):
                        self.assertEqual(flood_reference(data, width, height, minimum),
                                         dilated_ink_components(data, width, height, minimum))

    def test_nested_disconnected_ink_is_not_counted_in_surrounding_ring(self):
        data = bytearray(24 * 24)
        for y in range(2, 21):
            for x in range(2, 21):
                if x in (2, 20) or y in (2, 20):
                    data[y * 24 + x] = 1
        data[11 * 24 + 11] = 1
        self.assertEqual([(1, 1, 21, 21, 72), (10, 10, 3, 3, 1)],
                         dilated_ink_components(data, 24, 24))
        self.assertEqual([(1, 1, 21, 21, 72)],
                         dilated_ink_components(data, 24, 24, 2))

    def test_diagonal_connection_and_gap_remain_distinct(self):
        data = bytearray(10 * 10)
        for x, y in ((1, 1), (4, 4), (8, 8)):
            data[y * 10 + x] = 1
        self.assertEqual([(0, 0, 6, 6, 2), (7, 7, 3, 3, 1)],
                         dilated_ink_components(data, 10, 10))

    def test_first_pixel_order_and_input_are_preserved(self):
        data = bytearray(40 * 30)
        for x, y in ((30, 1), (1, 15), (12, 25)):
            data[y * 40 + x] = 1
        original = bytes(data)
        expected = [(29, 0, 3, 3, 1), (0, 14, 3, 3, 1), (11, 24, 3, 3, 1)]
        self.assertEqual(expected, dilated_ink_components(data, 40, 30))
        self.assertEqual(expected, dilated_ink_components(original, 40, 30))
        self.assertEqual(original, data)

    def test_invalid_masks_fail_explicitly(self):
        for data, width, height, minimum in ((b'', 0, 1, 1), (b'\0', 2, 1, 1),
                                             (b'\x02', 1, 1, 1), (b'\0', 1, 1, -1)):
            with self.subTest(data=data, size=(width, height), minimum=minimum):
                with self.assertRaises(ValueError):
                    dilated_ink_components(data, width, height, minimum)


if __name__ == '__main__':
    unittest.main()
