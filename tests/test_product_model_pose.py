"""Original product model pose arithmetic remains pure and fully bounded."""
import json
from pathlib import Path
import unittest

from openreunion.core import GameError
from openreunion.dos.content import ContentSource
from openreunion.dos.product_model_pose import adjusted_pivot, model_centroid
from openreunion.dos.product_models import decode_model


PROJECT = Path(__file__).resolve().parents[1]


def first_build(name):
    report = json.loads((PROJECT / 'reports' / name).read_text(encoding='utf-8'))
    assert report['passed']
    return report['builds'][0]


class ProductModelPoseTests(unittest.TestCase):
    def test_every_bounded_synthetic_pivot_case(self):
        evidence = PROJECT / 'reports' / 'original-product-model-pivots-r1.json'
        if not evidence.is_file():
            self.skipTest('Bounded original pivot evidence is not present in this checkout.')
        for row in first_build(evidence.name)['cases']:
            with self.subTest(product=row['product'], part=row['part'], centroid=row['input']):
                self.assertEqual(adjusted_pivot(row['product'], row['part'], row['input']),
                                 tuple(row['output']))

    def test_every_actual_centroid_and_pivot_case(self):
        evidence = PROJECT / 'reports' / 'original-product-model-centroids-r1.json'
        vectors = PROJECT.parent / 'VECTORS'
        if not evidence.is_file() or not vectors.is_dir():
            self.skipTest('Bounded centroid evidence or original product models are not present in this checkout.')
        cases = first_build(evidence.name)['cases']
        content = ContentSource(PROJECT.parent)
        models = {product: decode_model(content.product_model_data(product))
                  for product in range(1, 36)}
        self.assertEqual(len(cases), 254)
        for row in cases:
            points, _ = models[row['product']][row['part'] - 1]
            with self.subTest(product=row['product'], part=row['part']):
                centroid = model_centroid(points)
                self.assertEqual(centroid, tuple(row['centroid']))
                self.assertEqual(adjusted_pivot(row['product'], row['part'], centroid),
                                 tuple(row['pivot']))

    def test_scaling_ties_signed_words_and_zero_divisor_rejection(self):
        self.assertEqual(model_centroid(((15, -15, 19), (25, -25, -19))), (2, -2, 0))
        self.assertEqual(model_centroid(((-19, 19, -10), (-11, 11, 10))), (-1, 1, 0))
        self.assertEqual(adjusted_pivot(6, 1, (30000, 0, 30000)), (24464, 0, 24464))
        self.assertEqual(adjusted_pivot(11, 2, (0, 32767, 0)), (0, -32758, 0))
        self.assertEqual(adjusted_pivot(24, 1, (-32768, 0, 0)), (-32668, 0, 0))
        with self.assertRaisesRegex(GameError, 'nonzero x'):
            adjusted_pivot(24, 1, (0, 4, 0))
        for bad in ((0, 1, (0, 0, 0)), (36, 1, (0, 0, 0)), (1, 0, (0, 0, 0)),
                    (1, 18, (0, 0, 0)), (1, 1, (0, 0)), (1, 1, (0, 0, 32768))):
            with self.subTest(bad=bad):
                with self.assertRaises(GameError):
                    adjusted_pivot(*bad)
        with self.assertRaises(GameError):
            model_centroid(())
