"""Frame order, attacks, identity-preserving removal and casualty handoff."""
from copy import deepcopy
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.dos.campaign import random_bounded
from openreunion.dos.space_combat import RULE_START, RULE_END, space_tick, survivor_roster
from openreunion.dos.space_casualties import apply_casualties
from openreunion.dos.aliens import store_fleet, fleet_at


def rules_fixture():
    values = [0]*(RULE_END-RULE_START)
    for at in (0x7D0, 0x7D2, 0x7D4, 0x7D6):values[at-RULE_START:at-RULE_START+2] = [255, 255]
    for hull in range(1, 5):
        values[0x7CB+hull-RULE_START] = 2
        values[0x7A6+2*hull-RULE_START] = 1
    return {"bytes": values}


def unit(identity, *, hull=3, damage=30, hp=30, origin=None):
    raw = [identity, hull, 0, 0, 0, 0, 80, 70, 2, 1, 1, 1]
    raw[2:6] = struct.pack("<Hh", damage, hp)
    return {"raw": raw, "origin": origin or {"source": "player", "bank": "moving", "slot": identity}}


def battle_fixture():
    return {"rng": 1994, "frame": 0, "done": False, "explosions": False, "instant_kill": False,
            "friendly": [unit(1)], "hostile": [unit(2, damage=0)], "friendly_count": 1, "hostile_count": 1}


def hit_seed(count=1, target=None):
    for seed in range(1000):
        after, selected = random_bounded(seed, count);_, hit = random_bounded(after, 100)
        if hit <= 10 and (target is None or selected == target):return seed
    raise AssertionError("No deterministic hit fixture")


class SpaceCombatTests(unittest.TestCase):
    def test_only_every_fourth_frame_advances_and_inputs_are_unchanged(self):
        state = battle_fixture();before = deepcopy(state);rules = rules_fixture()
        first = space_tick(state, rules);self.assertEqual(state, before);self.assertEqual(first["frame"], 1)
        for frame in (2, 3, 4):
            following = space_tick(first, rules)
            self.assertEqual(following, dict(first, frame=frame));first = following
        self.assertEqual(space_tick(first, rules)["frame"], 1)

    def test_light_hulls_do_one_third_damage_against_heavy_hulls(self):
        state = battle_fixture();state["rng"] = hit_seed()
        state["friendly"] = [unit(1, hull=1, damage=9, hp=100)]
        state["hostile"] = [unit(2, hull=3, damage=0, hp=100)]
        result = space_tick(state, rules_fixture())
        self.assertEqual(struct.unpack("<h", bytes(result["hostile"][0]["raw"][4:6]))[0], 97)

    def test_critical_probability_includes_the_threshold_value(self):
        state = battle_fixture();state["rng"] = hit_seed();rules = rules_fixture()
        state["friendly"] = [unit(1, hull=1, damage=0)];state["hostile"] = [unit(2, hull=1, damage=0)]
        seed, _ = random_bounded(state["rng"], 1);seed, _ = random_bounded(seed, 100)
        _, value = random_bounded(seed, 100)
        rules["bytes"][0x7D0-RULE_START:0x7D2-RULE_START] = struct.pack("<h", value)
        result = space_tick(state, rules)
        self.assertEqual(result["hostile_count"], 0);self.assertEqual(result["hostile"][0]["raw"][4:6], [0, 0])

    def test_unsigned_large_damage_cannot_resurrect_a_target(self):
        state = battle_fixture();state["rng"] = hit_seed();state["friendly"][0]["raw"][2:4] = [255, 255]
        state["hostile"][0]["raw"][4:6] = [1, 0]
        result = space_tick(state, rules_fixture())
        self.assertEqual(result["hostile_count"], 0)
        self.assertEqual(struct.unpack("<h", bytes(result["hostile"][0]["raw"][4:6]))[0], -32768)

    def test_swap_removal_preserves_each_units_origin(self):
        state = battle_fixture();state["rng"] = hit_seed(2, 0)
        state["hostile"] = [unit(2, hp=1, damage=0), unit(3, hp=100, damage=0)];state["hostile_count"] = 2
        result = space_tick(state, rules_fixture())
        self.assertEqual(result["hostile_count"], 1)
        self.assertEqual([u["origin"]["slot"] for u in result["hostile"]], [3, 2])
        self.assertEqual(result["hostile"][1]["raw"][10], 2)

    def test_explosions_delay_completion_until_their_last_frame(self):
        state = battle_fixture();state["hostile_count"] = 0;state["hostile"][0]["raw"][4:6] = [0, 0]
        for tick in range(9):
            state = space_tick(state, rules_fixture())
            self.assertEqual(state["done"], tick == 8)
        self.assertFalse(state["explosions"])

    def test_survivor_export_uses_typed_origins_and_only_active_prefixes(self):
        state = battle_fixture();state["friendly"][0]["origin"] = {"source": "world", "world": "1:5:1"}
        state["hostile_count"] = 0
        exported = survivor_roster(state)
        self.assertEqual(exported, [{"source": "world", "world": "1:5:1", "hull": 3}])
        exported[0]["world"] = "2:5:0"
        self.assertEqual(state["friendly"][0]["origin"]["world"], "1:5:1")

    def test_prepared_fight_runs_to_completion_and_writes_real_fleet_casualties(self):
        state = battle_fixture();state["hostile"][0] = unit(2, damage=30, origin={"source": "alien", "race": 3, "slot": 1})
        f = {"moving": [[0]*161], "local": []};row = f["moving"][0];row[0] = 1;row[19:23] = [1, 5, 0, 1];row[49] = 1
        c = [[0]*228 for _ in range(11)];c[1][27] = 2;c[1][38] = 1
        row = [0]*27;row[2] = 1;row[8:11] = [1, 5, 0];row[15] = 1;store_fleet(c[1], 1, row)
        for _ in range(1000):
            state = space_tick(state, rules_fixture())
            if state["done"]:break
        self.assertTrue(state["done"]);self.assertEqual(state["friendly_count"]+state["hostile_count"], 1)
        changed, aliens, _, losses = apply_casualties(f, c, {}, (1, 5, 0), survivor_roster(state))
        self.assertEqual(changed["moving"][0][49], state["friendly_count"])
        self.assertEqual(fleet_at(aliens[1], 1)[15], state["hostile_count"])
        self.assertEqual(sum(losses["friendly"])+sum(losses["hostile"]), 1)


if __name__ == "__main__":unittest.main()
