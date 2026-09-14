"""Fixed-point product transform behavior recovered from original entry 34150."""
import hashlib
import json
from pathlib import Path
import struct
import unittest

from openreunion.core import GameError
from openreunion.dos.product_transform import COSINE, rotation_matrix, transform_points


PROJECT = Path(__file__).resolve().parents[1]
EVIDENCE = PROJECT / 'local' / 'research' / 'product-transform-r1' / 'original-transform-r3.json'


class ProductTransformTests(unittest.TestCase):
    def test_bounded_original_matrix_and_output_cases(self):
        if not EVIDENCE.is_file():
            self.skipTest('Bounded original transform evidence is not present in this checkout.')
        report = json.loads(EVIDENCE.read_text(encoding='utf-8'))
        self.assertTrue(report['passed'])
        build = report['builds'][0]
        table = COSINE + (COSINE[0],)
        self.assertEqual(hashlib.sha256(struct.pack('<361i', *table)).hexdigest(), build['trig_sha256'])
        for case in build['cases']:
            # The runtime preview state already supplies 0..359.  The bounded
            # oracle also proves its looped 360+ inputs map to the same table.
            angles = tuple(value % 360 for value in case['angles_xyz'])
            expected_matrix = tuple(tuple(row) for row in case['matrix'])
            flat = case['output_flat_xyz']
            expected_output = tuple(tuple(flat[index:index + 3])
                                    for index in range(0, len(flat), 3))
            with self.subTest(mode=case['mode'], scale=case['scale'], angles=case['angles_xyz']):
                self.assertEqual(rotation_matrix(angles, case['mode']), expected_matrix)
                self.assertEqual(transform_points(tuple(map(tuple, case['points'])), angles,
                                                  case['scale'], case['mode']), expected_output)

    def test_identity_retains_xz_and_flips_y(self):
        self.assertEqual(rotation_matrix((0, 0, 0)),
                         ((500, 0, 0), (0, -500, 0), (0, 0, 500)))
        self.assertEqual(transform_points(((127, 127, 127),), (0, 0, 0), 67),
                         ((64, -65, 64),))

    def test_y_quarter_turn_and_mode_two_row_swap(self):
        basis = ((127, 0, 0), (0, 127, 0), (0, 0, 127))
        self.assertEqual(rotation_matrix((0, 90, 0)),
                         ((0, 0, 500), (0, -500, 0), (-500, 0, 0)))
        self.assertEqual(transform_points(basis, (0, 90, 0), 67),
                         ((0, 0, -65), (0, -65, 0), (64, 0, 0)))
        self.assertEqual(transform_points(basis, (0, 90, 0), 67, mode=2),
                         ((0, 0, -65), (-65, 0, 0), (0, 64, 0)))

    def test_signed_low_bytes_scale_and_negative_high_word_rounding(self):
        self.assertEqual(transform_points(((0x017f, 0x0180, 0x01ff),), (0, 0, 0), 255),
                         ((-1, -1, 0),))
        # The original writes DX, the signed high word of the 32-bit total:
        # -500 therefore remains -1 instead of truncating toward zero.
        self.assertEqual(transform_points(((1, 0, 0), (0, 1, 0)), (0, 0, 0), 1),
                         ((0, 0, 0), (0, -1, 0)))

    def test_invalid_domains_reject(self):
        for indices in ((), (0, 0), (0, 0, 360), (-1, 0, 0), (True, 0, 0)):
            with self.subTest(indices=indices):
                with self.assertRaises(GameError):
                    rotation_matrix(indices)
        for mode in (0, 3, True):
            with self.subTest(mode=mode):
                with self.assertRaises(GameError):
                    rotation_matrix((0, 0, 0), mode)
        for points, scale in (((), 1), (((0, 0),), 1), (((0, 0, 32768),), 1),
                              (((0, 0, 0),), 256), (((0, 0, 0),), True)):
            with self.subTest(points=points, scale=scale):
                with self.assertRaises(GameError):
                    transform_points(points, (0, 0, 0), scale)
