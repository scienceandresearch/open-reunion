"""Ground force eligibility, power arithmetic, reserves and group commands."""
from copy import deepcopy
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.core import GameError
from openreunion.dos.aliens import store_fleet, fleet_at
from openreunion.dos.ground_setup import build_ground_setup, edit_ground_groups
from openreunion.dos.space_roster import build_space_battle
from openreunion.dos.space_combat import space_tick, survivor_roster
from openreunion.dos.space_casualties import apply_casualties
from openreunion.dos.space_outcome import space_outcome
from test_space_outcome import fixture as campaign_fixture
from test_space_roster import fixture as space_fixture, player, alien


RULES = {"equipment_weights": [2, 7, 9], "primary": [2, 13, 28, 0],
         "secondary": [0, 0, 9, 45], "group_limits": [30, 30, 10, 5]}


def fixture():
    state = campaign_fixture();row = player();row[69:79] = struct.pack("<5h", 31, 2, 3, 4, 999)
    state["fleets"]["moving"] = [row]
    return state


def build(state):return build_ground_setup(state["fleets"], state["civilizations"], state["worlds"], (1, 5, 0), RULES)


def quantities(groups):return [struct.unpack("<h", bytes(row[1:3]))[0] for row in groups]


def conserved(setup):
    totals = list(setup["friendly_reserve"])
    for row in setup["friendly_groups"]:totals[row[0]-1] += struct.unpack("<h", bytes(row[1:3]))[0]
    return totals == setup["friendly_totals"]


class GroundSetupTests(unittest.TestCase):
    def test_player_power_uses_distinct_equipment_components(self):
        state = fixture();before = deepcopy(state);result = build(state)
        self.assertEqual(result["friendly_totals"], [31, 0, 0, 0])
        self.assertEqual(result["friendly_primary"], [25, 0, 0, 0])
        self.assertEqual(result["friendly_secondary"], [36, 0, 0, 0])
        self.assertEqual(quantities(result["friendly_groups"]), [30, 1]);self.assertEqual(state, before)

    def test_only_exact_world_army_local_and_stationary_aliens_participate(self):
        state = fixture();rows = [deepcopy(state["fleets"]["moving"][0]) for _ in range(4)]
        rows[0][0] = 3;rows[1][21] = 1;rows[2][22] = 6;rows[3][0] = 5;rows[3][22] = 7
        state["fleets"]["moving"] = rows;alien(state["civilizations"])
        row = fleet_at(state["civilizations"][1], 1);row[19] = 20;row[2] = 2;store_fleet(state["civilizations"][1], 1, row)
        result = build(state);self.assertEqual(result["friendly_totals"], [31, 0, 0, 0]);self.assertEqual(result["hostile_totals"], [0]*4)

    def test_both_alien_relationships_pool_ground_stock_and_power(self):
        state = fixture()
        for race, relation in ((3, 2), (4, 6)):
            alien(state["civilizations"], race=race, relation=relation)
            row = fleet_at(state["civilizations"][race-2], 1);row[19:27] = struct.pack("<4H", 0, 0, 3000, 10)
            store_fleet(state["civilizations"][race-2], 1, row)
        result = build(state)
        for side in ("friendly", "hostile"):
            self.assertEqual(result[side+"_primary"][2], 84000)
            self.assertEqual(result[side+"_secondary"][2:], [27000, 450])

    def test_allied_planetary_secondary_power_is_not_omitted(self):
        state = fixture();state["civilizations"][1][27] = 6;raw = state["worlds"]["1:5:0"]["raw"];raw[0] = 3
        raw[51:59] = struct.pack("<2I", 2, 10)
        result = build(state);self.assertEqual(result["friendly_secondary"][2:], [18, 450])

    def test_group_cap_preserves_large_unsigned_reserves_in_class_order(self):
        state = fixture();state["civilizations"][1][27] = 2;raw = state["worlds"]["1:5:0"]["raw"];raw[0] = 3
        raw[43:59] = struct.pack("<4I", 2**32-1, 100, 50, 10)
        result = build(state);groups = result["hostile_groups"]
        self.assertEqual(len(groups), 20);self.assertEqual(quantities(groups), [30]*20)
        self.assertEqual(result["hostile_reserve"], [2**32-1-600, 100, 50, 10])
        self.assertTrue(all(row[8:12] == [3, 0, 1, 1] and row[15] == 1 for row in groups))

    def test_add_remove_and_adjust_conserve_troops_and_leave_inputs_unchanged(self):
        setup = build(fixture());before = deepcopy(setup)
        result = edit_ground_groups(setup, RULES, "remove", 1)
        self.assertEqual(setup, before);self.assertEqual(result["friendly_reserve"], [30, 0, 0, 0])
        result = edit_ground_groups(result, RULES, "increase", 1)
        self.assertEqual(quantities(result["friendly_groups"]), [2]);self.assertTrue(conserved(result))
        result = edit_ground_groups(result, RULES, "add", 1)
        self.assertEqual(quantities(result["friendly_groups"]), [2, 29]);self.assertTrue(conserved(result))
        result = edit_ground_groups(result, RULES, "decrease", 2)
        self.assertEqual(result["friendly_reserve"], [1, 0, 0, 0]);self.assertTrue(conserved(result))

    def test_zero_group_can_be_refilled_and_quantity_controls_stop_at_bounds(self):
        setup = build(fixture());setup = edit_ground_groups(setup, RULES, "decrease", 2)
        self.assertEqual(quantities(setup["friendly_groups"]), [30, 0])
        self.assertEqual(edit_ground_groups(setup, RULES, "decrease", 2), setup)
        self.assertEqual(edit_ground_groups(setup, RULES, "increase", 1), setup)
        setup = edit_ground_groups(setup, RULES, "increase", 2)
        self.assertEqual(quantities(setup["friendly_groups"]), [30, 1]);self.assertTrue(conserved(setup))

    def test_empty_and_twenty_first_new_groups_are_rejected(self):
        setup = build(fixture())
        with self.assertRaises(GameError):edit_ground_groups(setup, RULES, "add", 2)
        state = fixture();state["fleets"]["moving"][0][69:71] = struct.pack("<h", 601);setup = build(state)
        self.assertEqual(len(setup["friendly_groups"]), 20);self.assertEqual(setup["friendly_reserve"][0], 1)
        with self.assertRaises(GameError):edit_ground_groups(setup, RULES, "add", 1)

    def test_invalid_stock_world_and_command_are_rejected_without_mutation(self):
        state = fixture();state["fleets"]["moving"][0][69:71] = [255, 255];before = deepcopy(state)
        with self.assertRaises(GameError):build(state)
        self.assertEqual(state, before)
        with self.assertRaises(GameError):build_ground_setup(state["fleets"], state["civilizations"], {}, (1, 5, 0), RULES)
        setup = build(fixture())
        for action, selection in (("remove", 0), ("increase", 3), ("add", 5), ("unknown", 1)):
            with self.assertRaises(GameError):edit_ground_groups(setup, RULES, action, selection)

    def test_space_casualties_and_outcomes_preserve_troops_for_ground_setup(self):
        state = fixture();state["rng"] = 0;alien(state["civilizations"]);c = state["civilizations"][1];c[17:19] = [2, 1]
        row = fleet_at(c, 1);row[0] = 2;store_fleet(c, 1, row)
        raw = state["worlds"]["1:5:0"]["raw"];raw[0] = 3;raw[43] = 12
        rules = space_fixture()[-1]
        battle = build_space_battle(state["fleets"], state["civilizations"], state["worlds"], (1, 5, 0), 20, 0, rules)
        for _ in range(5000):
            battle = space_tick(battle, rules)
            if battle["done"]:break
        self.assertTrue(battle["done"]);self.assertGreater(battle["friendly_count"], 0)
        state["fleets"], state["civilizations"], state["worlds"], _ = apply_casualties(
            state["fleets"], state["civilizations"], state["worlds"], (1, 5, 0), survivor_roster(battle))
        state["rng"] = battle["rng"]
        state, phase, _ = space_outcome(state, (1, 5, 0), player_won=True, player_attacking=True, ground_requested=True)
        self.assertEqual(phase, "ground_setup");setup = build(state)
        self.assertEqual(setup["friendly_totals"], [31, 0, 0, 0]);self.assertEqual(setup["hostile_totals"], [12, 0, 0, 0])


if __name__ == "__main__":unittest.main()
