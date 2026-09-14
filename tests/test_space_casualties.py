"""Casualty conservation, participant identity and original pointer regressions."""
from copy import deepcopy
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.core import GameError
from openreunion.dos.aliens import fleet_at, store_fleet
from openreunion.dos.space_casualties import apply_casualties


def fixture():
    f = {"moving": [], "local": []};c = [[0]*228 for _ in range(11)]
    w = {key: {"raw": [0]*65} for key in ("1:5:0", "1:5:1", "2:5:0")}
    return f, c, w


def player():
    row = [0]*161;row[0] = 1;row[19:23] = [1, 5, 0, 1]
    row[29:39] = struct.pack("<5h", 10, 21, 10, 0, 9)
    return row


class SpaceCasualtiesTests(unittest.TestCase):
    def test_retained_force_and_equipment_are_scaled_without_creating_stock(self):
        f, c, w = fixture();f["moving"] = [player()]
        live = [{"source": "player", "bank": "moving", "slot": 1, "hull": 1}]*2
        changed, _, _, losses = apply_casualties(f, c, w, (1, 5, 0), live)
        self.assertEqual(struct.unpack("<5h", bytes(changed["moving"][0][29:39])), (3, 6, 3, 0, 2))
        self.assertEqual(losses, {"friendly": [7, 0, 0, 0], "hostile": [0]*4})
        self.assertEqual(f["moving"][0], player())

    def test_all_surviving_entries_preserve_hulls_and_equipment(self):
        f, c, w = fixture();f["moving"] = [player()]
        live = [{"source": "player", "bank": "moving", "slot": 1, "hull": 1}]*10
        changed, _, _, losses = apply_casualties(f, c, w, (1, 5, 0), live)
        self.assertEqual(changed, f);self.assertEqual(losses["friendly"], [0]*4)

    def test_local_and_allied_alien_identifiers_do_not_collide(self):
        f, c, w = fixture();f["local"] = [[0]*161 for _ in range(10)]+[player()]
        f["local"][10][0] = 5;f["local"][10][22] = 7
        c[9][27] = 6;c[9][38] = 1;row = [0]*27;row[2] = 1;row[8:11] = [1, 5, 0];row[11] = 10
        store_fleet(c[9], 1, row)
        live = [{"source": "player", "bank": "local", "slot": 11, "hull": 1}]*5
        changed, aliens, _, losses = apply_casualties(f, c, w, (1, 5, 0), live)
        self.assertEqual(changed["local"][10][29], 6);self.assertEqual(fleet_at(aliens[9], 1)[11], 2)
        self.assertEqual(losses["friendly"][0], 12)

    def test_worlds_use_battle_primary_and_each_owners_side(self):
        f, c, w = fixture();c[1][27] = 6;c[5][27] = 2
        for identity, owner in (("1:5:0", 3), ("1:5:1", 7), ("2:5:0", 7)):
            w[identity]["raw"][0] = owner;w[identity]["raw"][27] = 10
        _, _, changed, losses = apply_casualties(f, c, w, (1, 5, 1), [])
        self.assertEqual([changed[key]["raw"][27] for key in w], [2, 2, 10])
        self.assertEqual(losses, {"friendly": [8, 0, 0, 0], "hostile": [8, 0, 0, 0]})

    def test_nonparticipants_and_ground_unit_fields_remain_intact(self):
        f, c, w = fixture();f["moving"] = [player(), player(), player()]
        f["moving"][0][22] = 6;f["moving"][1][0] = 4;f["moving"][2][19] = 2
        c[1][27] = 2;c[1][38] = 1;row = [0]*27;row[2] = 1;row[8:11] = [1, 5, 0];row[11:27] = list(range(16))
        store_fleet(c[1], 1, row);store_fleet(c[1], 7, row)
        changed, aliens, _, _ = apply_casualties(f, c, w, (1, 5, 0), [])
        self.assertEqual(changed, f);self.assertEqual(fleet_at(aliens[1], 1)[19:27], row[19:27])
        self.assertEqual(fleet_at(aliens[1], 7), row)

    def test_survivor_overcount_and_nonparticipant_reject_atomically(self):
        f, c, w = fixture();f["moving"] = [player()];before = deepcopy((f, c, w))
        live = [{"source": "player", "bank": "moving", "slot": 1, "hull": 1}]*11
        with self.assertRaises(GameError):apply_casualties(f, c, w, (1, 5, 0), live)
        self.assertEqual((f, c, w), before)
        with self.assertRaises(GameError):apply_casualties(f, c, w, (2, 5, 0), live[:1])
        for bad in (None, {"source": "other", "hull": 1}, {"source": "world", "world": "9:9:9", "hull": 1}):
            with self.assertRaises(GameError):apply_casualties(f, c, w, (1, 5, 0), [bad])

    def test_zero_hulls_clear_equipment_and_negative_stock_is_rejected(self):
        f, c, w = fixture();f["moving"] = [player()];f["moving"][0][29:31] = [0, 0]
        changed, _, _, _ = apply_casualties(f, c, w, (1, 5, 0), [])
        self.assertEqual(changed["moving"][0][29:39], [0]*10)
        f["moving"][0][29:31] = [255, 255]
        with self.assertRaises(GameError):apply_casualties(f, c, w, (1, 5, 0), [])

    def test_world_survivors_keep_distinct_moon_origins(self):
        f, c, w = fixture();c[1][27] = 2
        for key in ("1:5:0", "1:5:1"):
            w[key]["raw"][0] = 3;w[key]["raw"][27] = 10
        live = [{"source": "world", "world": "1:5:1", "hull": 1}]*5
        _, _, changed, losses = apply_casualties(f, c, w, (1, 5, 0), live)
        self.assertEqual(changed["1:5:0"]["raw"][27], 2);self.assertEqual(changed["1:5:1"]["raw"][27], 6)
        self.assertEqual(losses["hostile"][0], 12)


if __name__ == "__main__":unittest.main()
