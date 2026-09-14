"""Headless regressions for bulk cargo, equipment and ground adjustments."""
from copy import deepcopy
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openreunion.core import GameError
from openreunion.dos.cargo import cargo_used
from openreunion.dos.cargo_screen import CargoView
from openreunion.dos.catalog import ORE_KEYS
from openreunion.dos.ground_setup import edit_ground_groups

from test_cargo import cargo_session
from test_equipment import equipment_session
from test_ground_setup import RULES, build, fixture, quantities, conserved


class BulkQuantityTests(unittest.TestCase):
    def test_cargo_maximum_item_and_ore_stop_at_capacity_and_conserve_stock(self):
        session = cargo_session()
        view = CargoView(0)
        item = view.transfer(session.state, session.catalog, "slot", 13, True, 1,
                             maximum=True)
        self.assertEqual(item["quantity"], 2)
        session.apply("transfer_cargo", **item)
        unload = view.transfer(session.state, session.catalog, "slot", 13, False, 3,
                               maximum=True)
        self.assertEqual(unload["quantity"], -2)
        session.apply("transfer_cargo", **unload)
        ore = view.transfer(session.state, session.catalog, "ore", ORE_KEYS[0], True, 1,
                            maximum=True)
        self.assertEqual(ore["quantity"], 1000)
        session.apply("transfer_cargo", **ore)
        self.assertEqual(cargo_used(session.state["fleets"]["moving"][0],
                                    session.catalog["cargo_rules"]), 1000)
        self.assertEqual(session.state["products"][1]["stock"], 5)

    def test_equipment_maximum_is_bounded_and_mixed_carrier_payload_returns(self):
        session = equipment_session()
        session.apply("create_fleet", fleet_type=4)
        # Carrier payload is shared across satellite component columns.
        for product in (5, 6, 27):
            session.state["products"][product - 1].update(stock=1000, research_state=5)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                      component=0, quantity=2)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                      component=1, quantity=1)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                      component=2, quantity=1)
        before = deepcopy(session.state)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                      component=0, quantity=-1, maximum=True)
        row = session.state["fleets"]["moving"][0]
        self.assertEqual(struct.unpack_from("<5h", bytes(row), 29)[:3], (0, 0, 0))
        self.assertEqual(session.state["products"][5]["stock"], before["products"][5]["stock"] + 2)

    def test_equipment_maximum_component_load_can_exceed_one_thousand_clicks(self):
        session = equipment_session()
        session.apply("create_fleet", fleet_type=2)
        cat = session.catalog["fleet_rules"][1]["categories"][0]
        cat["hulls"][0]["limits"] = [40, 40]
        session.state["products"][5].update(stock=32767, research_state=5)
        session.state["products"][4].update(stock=32767, research_state=5)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                      component=0, quantity=1, maximum=True)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                      component=1, quantity=1, maximum=True)
        row = session.state["fleets"]["moving"][0]
        # The component limit is per hull; the bulk path must not retain the
        # historical one-click/1000-unit ceiling when more capacity is legal.
        self.assertEqual(struct.unpack_from("<5h", bytes(row), 29)[1], 32767)

    def test_equipment_queued_headroom_blocks_component_and_automatic_hull_returns(self):
        session = equipment_session()
        session.apply("create_fleet", fleet_type=2)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1, quantity=1)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1, component=1)
        # A queued home-depot unit consumes the last signed-word slot.
        session.state["products"][4].update(stock=32766, queued=1)
        before = deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                          component=1, quantity=-1, maximum=True)
        self.assertEqual(session.state, before)
        session.state["products"][5].update(stock=32766, queued=1)
        before = deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                          quantity=-1, maximum=True)
        self.assertEqual(session.state, before)

    def test_equipment_remote_alias_maximum_unload_returns_to_local_slot(self):
        session = equipment_session()
        row = [0] * 161
        row[0] = 5; row[19:23] = [1, 5, 1, 7]
        row[29:39] = struct.pack("<5h", 2, 1, 1, 0, 0)
        row[133:137] = struct.pack("<hh", 2, 3)
        session.state["fleets"]["local"] = [row]
        raw = session.state["worlds"]["1:5:1"]["raw"]
        raw[0] = raw[6] = 1
        session.catalog["fleet_rules"][4]["categories"][0]["components"][1]["local_slot"] = 2
        session.apply("equip_fleet", fleet_index=0, bank="local", category=1,
                      hull=1, quantity=-1, maximum=True)
        actual = session.state["fleets"]["local"][0]
        self.assertEqual(struct.unpack_from("<5h", bytes(actual), 29)[:3], (0, 0, 0))
        self.assertEqual(struct.unpack_from("<hh", bytes(actual), 133), (4, 5))

    def test_equipment_transport_maximum_unload_stops_before_overloading_cargo(self):
        session = cargo_session()
        session.apply("transfer_cargo", fleet_index=0, slot=13, quantity=1)
        session.apply("equip_fleet", fleet_index=0, category=2, hull=1,
                      quantity=-1, maximum=True)
        row = session.state["fleets"]["moving"][0]
        self.assertEqual(struct.unpack_from("<h", bytes(row), 29)[0], 1)
        self.assertEqual(cargo_used(row, session.catalog["cargo_rules"]), 500)

    def test_equipment_bounded_partial_commits_but_default_transfer_rolls_back(self):
        session = equipment_session()
        session.apply("create_fleet", fleet_type=2)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1)
        session.state["products"][4].update(stock=1, research_state=5)
        before = deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                          component=1, quantity=2)
        self.assertEqual(session.state, before)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                      component=1, quantity=2, bounded=True)
        self.assertEqual(struct.unpack_from("<5h", bytes(session.state["fleets"]["moving"][0]), 29)[1], 1)
        with self.assertRaises(GameError):
            session.apply("equip_fleet", fleet_index=0, category=1, hull=1,
                          component=1, quantity=1, maximum=1)

    def test_ground_bulk_fill_and_empty_preserve_reserve_and_input(self):
        setup = build(fixture())
        original = deepcopy(setup)
        result = edit_ground_groups(setup, RULES, "increase", 1, amount=32767)
        self.assertEqual(quantities(result["friendly_groups"]), [30, 1])
        self.assertTrue(conserved(result))
        emptied = edit_ground_groups(result, RULES, "decrease", 1, amount=32767)
        self.assertEqual(quantities(emptied["friendly_groups"]), [0, 1])
        self.assertTrue(conserved(emptied))
        self.assertEqual(setup, original)

    def test_ground_bulk_invalid_amount_is_atomic(self):
        setup = build(fixture())
        for amount in (0, -1, 32768, True):
            before = deepcopy(setup)
            with self.assertRaises(GameError):
                edit_ground_groups(setup, RULES, "increase", 1, amount=amount)
            self.assertEqual(setup, before)


if __name__ == "__main__":
    unittest.main()
