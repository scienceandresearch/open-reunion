"""Original-free conquest, colony cleanup and fleet corruption regressions."""
from copy import deepcopy
import struct
import unittest
from test_colony import definition, building
from openreunion.core import GameError
from openreunion.dos.campaign import random_bounded
from openreunion.dos.ground_conquest import reset_battle_world, lose_colony, conquer_for_player, conquer_for_alien


def fleet(destination=(1, 5, 0), kind=5, capacity=4321):
    row = [0]*161;row[0] = kind;row[19:23] = [*destination, 7]
    row[159:161] = struct.pack("<H", capacity)
    return row


def fixture():
    raw = [55]*65;raw[21] = 1
    state = {"worlds": {"1:5:0": {"raw": raw}, "1:5:1": {"raw": [77]*65}},
             "buildings": [], "fleets": {"moving": [], "local": []}, "rng": 1994, "flags": {"5d6c": 0}}
    command = definition(1, workers=0, power=0)
    fields = bytearray.fromhex(command["unclassified_fields_hex"]);fields[5] = 1
    command["unclassified_fields_hex"] = fields.hex()
    catalog = {"worlds": [{"id": "1:5:0", "name": "New Earth"}],
               "buildings": [command, definition(11, workers=0, power=0)]}
    return state, catalog


class GroundConquestTests(unittest.TestCase):
    def test_reset_preserves_geography_and_other_world_without_removing_records(self):
        state, _ = fixture();state["buildings"] = [building(1)];state["fleets"]["local"] = [fleet()]
        before = deepcopy(state);result = reset_battle_world(state, (1, 5, 0))
        raw = result["worlds"]["1:5:0"]["raw"]
        self.assertEqual(raw[0], 0);self.assertEqual(raw[13:20], [0]*7)
        self.assertEqual(raw[21:27], before["worlds"]["1:5:0"]["raw"][21:27])
        self.assertEqual(result["worlds"]["1:5:1"], state["worlds"]["1:5:1"])
        for key in ("buildings", "fleets", "rng"):self.assertEqual(result[key], state[key])
        self.assertEqual(state, before)

    def test_loss_compacts_only_exact_world_even_with_empty_moving_bank(self):
        state, _ = fixture();moon = building(1);moon[3] = 1
        state["buildings"] = [building(1), moon, building(1)]
        state["fleets"]["local"] = [fleet(), fleet((1, 5, 1)), fleet((1, 7, 0)), fleet()]
        result = lose_colony(state, (1, 5, 0))
        self.assertEqual(result["buildings"], [moon])
        self.assertEqual([row[19:22] for row in result["fleets"]["local"]], [[1, 5, 1], [1, 7, 0]])
        state["fleets"]["moving"] = [fleet(kind=1)]
        self.assertEqual(lose_colony(state, (1, 5, 0))["fleets"]["moving"], state["fleets"]["moving"])

    def test_conquest_consumes_population_then_building_rolls_and_defers_placement(self):
        state, catalog = fixture();before = deepcopy(state)
        seed, population = random_bounded(1994, 3000)
        seed, work = random_bounded(seed, 60);seed, condition = random_bounded(seed, 80)
        result = conquer_for_player(state, (1, 5, 0), catalog);raw = result["worlds"]["1:5:0"]["raw"]
        self.assertEqual((raw[0], raw[6], raw[9]), (1, 1, 0))
        self.assertEqual(struct.unpack("<I", bytes(raw[13:17]))[0], 2000+population)
        self.assertEqual(raw[17:20], [20, 3, 30]);self.assertEqual(result["rng"], seed)
        self.assertEqual(result["buildings"], [[1, 1, 5, 0, 255, 255, 100+work, 40+condition, 0, 0, 0, 0, 0, 0]])
        row = result["fleets"]["local"][-1]
        self.assertEqual(bytes(row[2:2+row[1]]), b"New Earth forces")
        self.assertEqual(row[19:23], [1, 5, 0, 7]);self.assertEqual(row[23:], [0]*138)
        self.assertEqual(state, before)

    def test_existing_buildings_reallocate_only_last_matching_local_capacity(self):
        state, catalog = fixture();state["buildings"] = [building(11)]
        state["fleets"]["local"] = [fleet(), fleet((1, 5, 1)), fleet()]
        result = conquer_for_player(state, (1, 5, 0), catalog)
        capacities = [struct.unpack("<H", bytes(row[159:161]))[0] for row in result["fleets"]["local"]]
        self.assertEqual(capacities, [4321, 4321, 20, 0])
        self.assertEqual(len(result["buildings"]), 2);self.assertEqual(result["buildings"][0][8], 1)

    def test_missing_local_lookup_cannot_overwrite_last_of_32_moving_fleets(self):
        state, catalog = fixture();state["fleets"]["moving"] = [fleet(kind=1) for _ in range(32)]
        result = conquer_for_player(state, (1, 5, 0), catalog)
        self.assertEqual(result["fleets"]["moving"], state["fleets"]["moving"])
        self.assertEqual(result["fleets"]["local"][0][159:161], [0, 0])

    def test_incompatible_terrain_and_full_building_bank_skip_construction_rng(self):
        for full in (False, True):
            state, catalog = fixture()
            if full:state["buildings"] = [building(1) for _ in range(1000)]
            else:state["worlds"]["1:5:0"]["raw"][21] = 2
            result = conquer_for_player(state, (1, 5, 0), catalog)
            self.assertEqual(result["buildings"], state["buildings"])
            self.assertEqual(result["rng"], random_bounded(1994, 3000)[0])
            self.assertEqual(len(result["fleets"]["local"]), 1)

    def test_local_name_obeys_original_pascal_17_byte_limit(self):
        state, catalog = fixture();catalog["worlds"][0]["name"] = "ABCDEFGHIJKL"
        row = conquer_for_player(state, (1, 5, 0), catalog)["fleets"]["local"][0]
        self.assertEqual(row[1], 17);self.assertEqual(bytes(row[2:19]), b"ABCDEFGHIJKL forc")
        self.assertEqual(row[19:23], [1, 5, 0, 7])

    def test_alien_settlement_cleans_colony_and_uses_correct_morgrul_phase_flag(self):
        rules = {"morgrul_base": [100]*8, "morgrul_early_base": [10]*8, "morgrul_spread": [0]*8}
        for late in (0, 1):
            state, _ = fixture();state["flags"] = {"5d6c": late, "5d8c": 1-late}
            state["buildings"] = [building(1)];state["fleets"]["local"] = [fleet()]
            before = deepcopy(state);result = conquer_for_alien(state, (1, 5, 0), 3, rules)
            raw = result["worlds"]["1:5:0"]["raw"]
            self.assertEqual(raw[0], 3);self.assertEqual(result["buildings"], [])
            self.assertEqual(result["fleets"]["local"], [])
            self.assertEqual(struct.unpack("<8I", bytes(raw[27:59])), (100 if late else 10,)*8)
            seed, _ = random_bounded(1994, 3000)
            for _ in range(8 if late else 16):seed, _ = random_bounded(seed, 0)
            self.assertEqual(result["rng"], seed);self.assertEqual(state, before)

    def test_invalid_world_catalog_and_owner_leave_inputs_unchanged(self):
        state, catalog = fixture();before = deepcopy(state)
        with self.assertRaises(GameError):lose_colony(state, (9, 9, 9))
        catalog["worlds"] = []
        with self.assertRaises(GameError):conquer_for_player(state, (1, 5, 0), catalog)
        for owner in (True, 1, 13, 3.0):
            with self.assertRaises(GameError):conquer_for_alien(state, (1, 5, 0), owner, {})
        self.assertEqual(state, before)

    def test_ground_victory_writes_survivors_then_conquers_the_same_world(self):
        from test_ground_setup import fixture as forces_fixture, build
        from test_ground_geometry import MOTION
        from test_ground_frame import RULES as ATTACK_RULES
        from test_ground_movement import RULES as MOVEMENT_RULES
        from test_space_roster import player
        from openreunion.dos.ground_battle import initialize_ground_battle
        from openreunion.dos.ground_frame import ground_frame
        from openreunion.dos.ground_casualties import apply_ground_casualties
        state = forces_fixture();_, catalog = fixture()
        row = player();row[69:109] = [0]*40;row[99:109] = struct.pack("<5h", 10, 0, 0, 112, 999)
        state["fleets"]["moving"] = [row];state["civilizations"][1][27] = 2
        raw = state["worlds"]["1:5:0"]["raw"];raw[0] = 3;raw[43] = 30;raw[21] = 1
        state["buildings"] = []
        battle = initialize_ground_battle(build(state), MOTION, player_attacking=True);battle["rng"] = 1994
        for _ in range(2000):
            battle, _ = ground_frame(battle, MOTION, ATTACK_RULES, MOVEMENT_RULES)
            if battle["done"]:break
        self.assertTrue(battle["done"]);self.assertTrue(battle["player_won"])
        state["fleets"], state["civilizations"], state["worlds"], losses = apply_ground_casualties(
            state["fleets"], state["civilizations"], state["worlds"], (1, 5, 0), battle)
        state["rng"] = battle["rng"];other = deepcopy(state["worlds"]["1:5:1"])
        result = conquer_for_player(state, (1, 5, 0), catalog)
        self.assertEqual(result["worlds"]["1:5:0"]["raw"][0], 1)
        self.assertEqual(result["worlds"]["1:5:1"], other)
        self.assertEqual(result["fleets"]["moving"][0][99:109], list(struct.pack("<5h", 10, 0, 0, 112, 999)))
        self.assertEqual(losses["hostile"], [30, 0, 0, 0])
        self.assertEqual(result["fleets"]["local"][-1][19:23], [1, 5, 0, 7])
        self.assertEqual(result["buildings"][-1][:6], [1, 1, 5, 0, 255, 255])


if __name__ == "__main__":unittest.main()
