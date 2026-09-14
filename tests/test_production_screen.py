"""Purchase draft isolation, station-cap regression and malformed model inputs."""
from copy import deepcopy
import struct
import unittest

from test_recovered import fixture
from openreunion.core import GameError
from openreunion.dos.session import RecoveredSession
from openreunion.dos.production_screen import ProductionView, order_limit
from openreunion.dos.product_models import decode_model


class ProductionTests(unittest.TestCase):
    def test_capital_orders_need_station_stock_and_fail_atomically(self):
        for pid in (23, 33):
            catalog, state = fixture()
            catalog['products'][pid-1].update(manufacturable=0, special_ship=1)
            session = RecoveredSession(catalog, state)
            before = deepcopy(session.state)
            with self.assertRaisesRegex(GameError, 'Space station'):
                session.apply('order', product_id=pid, quantity=1)
            self.assertEqual(session.state, before)
            session.state['products'][23]['stock'] = 2
            session.apply('order', product_id=pid, quantity=2)
            before = deepcopy(session.state)
            with self.assertRaises(GameError):
                session.apply('order', product_id=pid, quantity=3)
            self.assertEqual(session.state, before)
            # Losing capacity or importing an old oversized queue must not trap it.
            session.state['products'][23]['stock'] = 0
            session.apply('order', product_id=pid, quantity=1)
            session.apply('order', product_id=pid, quantity=0)
            self.assertEqual(session.state['products'][pid-1]['queued'], 0)

    def test_draft_clamps_to_ore_and_keeps_selection_visible_without_mutation(self):
        catalog, state = fixture()
        state['products'][0]['research_state'] = 0
        state['resources']['detoxin'] = 3
        before = deepcopy(state)
        view = ProductionView()
        view.sync(state)
        self.assertEqual(view.selected, 2)
        view.step(state, 100)
        self.assertEqual((view.selected, view.first), (35, 21))
        view.quantity = 5
        view.step(state, -10)
        self.assertEqual(view.selected, 35)
        self.assertEqual(order_limit(state, catalog['products'][34], state['products'][34]), 1)
        self.assertEqual(state, before)

    def test_model_record_bounds_and_vertex_references(self):
        body = (struct.pack('<H9hH6BH', 3, 0, 0, 0, 10, 0, 0, 0, 10, 0, 3, 1, 2, 2, 3, 3, 1, 1)
                +bytes([1, 2, 3, 255])+bytes(16))
        valid = struct.pack('<H', len(body))+body+b'\xff\xff'
        self.assertEqual(decode_model(valid)[0][1], ((0, 1, 2),))
        bad_index = bytearray(valid)
        bad_index[24] = 4
        for data in (valid[:-1], valid+b'\0', bytes(bad_index), b'\xff\xff', valid[:2]+b'\xff\x7f'+valid[4:]):
            with self.assertRaises(GameError):
                decode_model(data)
