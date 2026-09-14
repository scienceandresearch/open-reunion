"""Original product preview state, independently checked against extracted tables."""
import json
from pathlib import Path
import unittest

from openreunion.core import GameError
from openreunion.dos.product_preview_state import MODULUS, ProductPreviewState, angle_steps, initial_angles


PROJECT = Path(__file__).resolve().parents[1]
TABLES = PROJECT / 'local' / 'research' / 'product-model-r1' / 'tables.json'
ORIGINAL_STATE = PROJECT / 'reports' / 'original-product-preview-state-r1.json'


class ProductPreviewStateTests(unittest.TestCase):
    def test_bounded_original_initialization_and_update_cases(self):
        if not ORIGINAL_STATE.is_file():
            self.skipTest('Bounded original preview-state evidence is not present in this checkout.')
        report = json.loads(ORIGINAL_STATE.read_text(encoding='utf-8'))
        self.assertTrue(report['passed'])
        products = report['builds'][0]['products']
        self.assertEqual(len(products), 35)
        for row in products:
            product = row['product']
            with self.subTest(product=product, phase='initialization'):
                self.assertEqual(ProductPreviewState.initial(product).angles, tuple(row['initial']))
                self.assertEqual(ProductPreviewState.initial(product).steps, tuple(row['steps']))
            for case in row['cases']:
                with self.subTest(product=product, before=case['before']):
                    self.assertEqual(ProductPreviewState(product, tuple(case['before'])).advance().angles,
                                     tuple(case['after']))

    def test_extracted_steps_initializers_and_first_frame_for_every_product(self):
        if not TABLES.is_file():
            self.skipTest('Original preview table evidence is not present in this checkout.')
        report = json.loads(TABLES.read_text(encoding='utf-8'))
        self.assertTrue(report['passed'])
        rows = report['builds'][0]['rows']
        self.assertEqual(len(rows), 35)
        for row in rows:
            product = row['product']
            expected_steps = tuple(row['angle_steps_5713'])
            expected_initial = ((215, 45, 54) if product == 14 else
                                (0, 21, 32) if product == 24 else (0, 0, 300))
            with self.subTest(product=product):
                state = ProductPreviewState.initial(product)
                self.assertEqual(angle_steps(product), expected_steps)
                self.assertEqual(initial_angles(product), expected_initial)
                self.assertEqual(state.angles, expected_initial)
                self.assertEqual(state.transform_indices,
                                 tuple(value // 3 for value in expected_initial))
                self.assertEqual(state.advance().angles,
                                 tuple((value + step) % 1080
                                       for value, step in zip(expected_initial, expected_steps)))

    def test_update_wraps_each_word_and_indices_are_integer_division(self):
        state = ProductPreviewState(3, (1079, 1078, 1079)).advance()
        self.assertEqual(state.angles, (4, 1, 0))
        self.assertEqual(state.transform_indices, (1, 0, 0))
        state = ProductPreviewState.initial(14)
        self.assertEqual((state.angles, state.transform_indices), ((215, 45, 54), (71, 15, 18)))
        self.assertEqual(ProductPreviewState.initial(24).transform_indices, (0, 7, 10))
        self.assertEqual(MODULUS, 1080)

    def test_invalid_ids_and_states_reject(self):
        for product in (0, 36, True):
            with self.subTest(product=product):
                with self.assertRaises(GameError):
                    ProductPreviewState.initial(product)
        for angles in ((), (0, 0), (0, 0, 1080), (0, 0, -1), (0, 0, True)):
            with self.subTest(angles=angles):
                with self.assertRaises(GameError):
                    ProductPreviewState(1, angles)
