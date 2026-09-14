"""Campaign-derived roster construction, capacity and identity regressions."""
from copy import deepcopy
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.core import GameError
from openreunion.dos.aliens import store_fleet, fleet_at
from openreunion.dos.space_roster import build_space_battle
from openreunion.dos.space_combat import RULE_START, space_tick, survivor_roster
from openreunion.dos.space_casualties import apply_casualties
from test_space_combat import rules_fixture


def fixture():
    f = {"moving": [], "local": []};c = [[0]*228 for _ in range(11)]
    w = {key: {"raw": [0]*65} for key in ("1:5:1", "2:5:0", "1:5:0")}
    rules = rules_fixture();values = rules["bytes"]
    for i, weight in enumerate((2, 7, 40, 200)):
        at = 0x5C8+4*i-RULE_START;values[at:at+4] = struct.pack("<i", weight)
    for hull in range(1, 5):
        for at, value in ((0x5D4+4*hull, 30), (0x5E4+4*hull, 30)):
            at -= RULE_START;values[at:at+4] = struct.pack("<i", value)
        for at, value in ((0x7B7+hull, 40), (0x7BB+hull, 1), (0x7BF+hull, 60), (0x7C3+hull, 1)):
            values[at-RULE_START] = value
    for at in range(0x753, 0x75B):values[at-RULE_START] = 1
    return f, c, w, (1, 5, 0), 20, 1994, rules


def player(quantity=2):
    row = [0]*161;row[0] = 1;row[19:23] = [1, 5, 0, 1]
    row[29:39] = struct.pack("<5h", quantity, 2, 2, 2, 2)
    return row


def alien(civs, race=3, quantity=2, relation=2):
    civs[race-2][27] = relation;civs[race-2][38] = 1
    row = [0]*27;row[2] = 1;row[8:11] = [1, 5, 0];row[11:13] = struct.pack("<H", quantity)
    store_fleet(civs[race-2], 1, row)


class SpaceRosterTests(unittest.TestCase):
    def test_weighted_equipment_and_fighter_skill(self):
        args = list(fixture());args[0]["moving"] = [player()]
        for skill, expected in ((0, 166), (20, 249), (90, 328)):
            args[4] = skill;battle = build_space_battle(*args)
            self.assertEqual(struct.unpack("<H", bytes(battle["friendly"][0]["raw"][2:4]))[0], expected)
            self.assertEqual(battle["friendly_count"], 2)

    def test_original_order_and_typed_origins(self):
        args = fixture();f, c, w = args[:3];f["moving"] = [player(1)];f["local"] = [player(1)]
        alien(c, relation=6, quantity=1)
        for key in ("1:5:0", "1:5:1"):w[key]["raw"][0] = 3;w[key]["raw"][27] = 1
        result = build_space_battle(*args)
        self.assertEqual([u["origin"] for u in result["friendly"]], [
            {"source": "player", "bank": "moving", "slot": 1},
            {"source": "player", "bank": "local", "slot": 1},
            {"source": "alien", "race": 3, "slot": 1},
            {"source": "world", "world": "1:5:0"}, {"source": "world", "world": "1:5:1"}])
        self.assertEqual([u["raw"][6] for u in result["friendly"]], [40, 40, 120, 120, 120])

    def test_player_capacity_is_checked_within_hull_group(self):
        args = fixture();args[0]["moving"] = [player(502)]
        self.assertEqual(build_space_battle(*args)["friendly_count"], 500)
        other = fixture();other[0]["moving"] = [player(500)]
        self.assertEqual(build_space_battle(*args)["rng"], build_space_battle(*other)["rng"])

    def test_full_unsigned_world_and_alien_quantities_obey_side_cap(self):
        args = fixture();alien(args[1], quantity=32768)
        self.assertEqual(build_space_battle(*args)["hostile_count"], 500)
        args[1][1][38] = 0;raw = args[2]["1:5:0"]["raw"];raw[0] = 3;raw[27:31] = struct.pack("<I", 2**32-1)
        self.assertEqual(build_space_battle(*args)["hostile_count"], 500)

    def test_side_caps_are_independent(self):
        args = fixture();args[0]["moving"] = [player(500)];alien(args[1], quantity=500)
        result = build_space_battle(*args)
        self.assertEqual((result["friendly_count"], result["hostile_count"]), (500, 500))

    def test_nonparticipants_and_unrelated_worlds_are_excluded(self):
        args = fixture();f, c, w = args[:3]
        f["moving"] = [player() for _ in range(3)]
        f["moving"][0][22] = 6;f["moving"][1][0] = 4;f["moving"][2][20] = 1
        alien(c);row = fleet_at(c[1], 1);row[2] = 2;store_fleet(c[1], 1, row)
        w["2:5:0"]["raw"][0] = 3;w["2:5:0"]["raw"][27] = 10
        result = build_space_battle(*args)
        self.assertEqual((result["friendly_count"], result["hostile_count"]), (0, 0))

    def test_large_equipment_damage_saturates_instead_of_wrapping(self):
        args = list(fixture());args[4] = 90;args[0]["moving"] = [player(1)]
        args[0]["moving"][0][31:39] = struct.pack("<4h", *([32767]*4))
        result = build_space_battle(*args)
        self.assertEqual(result["friendly"][0]["raw"][2:4], [255, 255])

    def test_rejections_and_success_leave_campaign_inputs_unchanged(self):
        args = fixture();args[0]["moving"] = [player()];before = deepcopy(args)
        build_space_battle(*args);self.assertEqual(args, before)
        args[0]["moving"][0][29:31] = [255, 255];before = deepcopy(args)
        with self.assertRaises(GameError):build_space_battle(*args)
        self.assertEqual(args, before)
        args = list(fixture());args[3] = (9, 9, 9)
        with self.assertRaises(GameError):build_space_battle(*args)

    def test_roster_simulation_and_casualties_form_a_complete_headless_fight(self):
        args = fixture();f, c, w = args[:3];f["moving"] = [player()];alien(c)
        state = build_space_battle(*args)
        for _ in range(5000):
            state = space_tick(state, args[-1])
            if state["done"]:break
        self.assertTrue(state["done"])
        changed, civs, _, losses = apply_casualties(f, c, w, args[3], survivor_roster(state))
        self.assertEqual(changed["moving"][0][29], state["friendly_count"])
        self.assertEqual(fleet_at(civs[1], 1)[11], state["hostile_count"])
        self.assertEqual(sum(losses["friendly"])+sum(losses["hostile"]), 4-state["friendly_count"]-state["hostile_count"])


if __name__ == "__main__":unittest.main()
