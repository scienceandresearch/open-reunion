"""Ground casualty eligibility, reserves, proportional equipment and campaign flow."""
from copy import deepcopy
import struct
import unittest
from test_ground_setup import fixture, build, RULES
from test_ground_geometry import MOTION
from test_ground_frame import RULES as ATTACK_RULES
from test_ground_movement import RULES as MOVEMENT_RULES
from test_space_roster import player, alien
from openreunion.core import GameError
from openreunion.dos.aliens import fleet_at, store_fleet
from openreunion.dos.ground_battle import initialize_ground_battle
from openreunion.dos.ground_frame import ground_frame
from openreunion.dos.ground_casualties import apply_ground_casualties


def apply(state, battle):
    return apply_ground_casualties(state["fleets"], state["civilizations"], state["worlds"], (1, 5, 0), battle)


class GroundCasualtyTests(unittest.TestCase):
    def test_three_equipment_components_follow_surviving_units_and_fourth_is_preserved(self):
        state = fixture();battle = build(state)
        battle["friendly_groups"][0][1] = 14
        before = deepcopy((state, battle));f, c, w, losses = apply(state, battle)
        self.assertEqual(struct.unpack("<5h", bytes(f["moving"][0][69:79])), (15, 0, 1, 1, 999))
        self.assertEqual(losses["friendly"], [16, 0, 0, 0]);self.assertEqual((state, battle), before)

    def test_mixed_fleets_cannot_retain_more_weapons_per_surviving_tank(self):
        state=fixture();army=state['fleets']['moving'][0];army[69:109]=[0]*40
        army[79:89]=struct.pack('<5h',55,165,55,0,0)
        local=deepcopy(army);local[0]=5;local[22]=7;local[79:89]=struct.pack('<5h',35,105,35,0,0)
        state['fleets']['local']=[local];battle=build(state)
        battle['friendly_groups'][-1][1]=20
        f,_,_,losses=apply(state,battle)
        self.assertEqual(struct.unpack_from('<4h',bytes(f['moving'][0]),79),(48,144,48,0))
        self.assertEqual(struct.unpack_from('<4h',bytes(f['local'][0]),79),(31,93,31,0))
        self.assertEqual(losses['friendly'],[0,10,0,0])

    def test_zero_surviving_units_cannot_leave_usable_equipment(self):
        state=fixture();army=state['fleets']['moving'][0];army[69:109]=[0]*40
        army[79:89]=struct.pack('<5h',1,3,1,0,0)
        local=deepcopy(army);local[0]=5;local[22]=7;local[79:89]=struct.pack('<5h',9,27,9,0,0)
        state['fleets']['local']=[local];battle=build(state);battle['friendly_groups'][0][1]=5
        f,_,_,_=apply(state,battle)
        self.assertEqual(f['moving'][0][79:87],[0]*8)
        self.assertEqual(struct.unpack_from('<4h',bytes(f['local'][0]),79),(4,12,4,0))

    def test_friendly_reserves_survive_when_all_deployed_groups_are_destroyed(self):
        state = fixture();battle = build(state)
        battle["friendly_reserve"][0] = 1;battle["friendly_groups"][1][1] = 0;battle["friendly_groups"][0][1] = 0
        f, _, _, losses = apply(state, battle)
        self.assertEqual(f["moving"][0][69], 1);self.assertEqual(losses["friendly"][0], 30)

    def test_undeployed_hostile_reserves_are_not_lost_at_group_capacity(self):
        state = fixture();state["civilizations"][1][27] = 2
        raw = state["worlds"]["1:5:0"]["raw"];raw[0] = 3;raw[43:47] = struct.pack("<I", 700)
        battle = build(state);_, _, worlds, losses = apply(state, battle)
        self.assertEqual(battle["hostile_reserve"], [100, 0, 0, 0])
        self.assertEqual(struct.unpack("<I", bytes(worlds["1:5:0"]["raw"][43:47]))[0], 700)
        self.assertEqual(losses["hostile"], [0]*4)

    def test_exact_world_type_status_and_both_player_banks(self):
        state = fixture();base = state["fleets"]["moving"][0]
        wrong_moon, traveling, pirate = deepcopy(base), deepcopy(base), deepcopy(base)
        wrong_moon[21] = 1;traveling[22] = 4;pirate[0] = 3
        state["fleets"]["moving"].extend([wrong_moon, traveling, pirate])
        local = deepcopy(base);local[0] = 5;local[22] = 7;state["fleets"]["local"] = [local]
        battle = build(state)
        for row in battle["friendly_groups"]:row[1:3] = [0, 0]
        f, _, _, _ = apply(state, battle)
        self.assertEqual(f["moving"][0][69:77], [0]*8);self.assertEqual(f["local"][0][69:77], [0]*8)
        self.assertEqual(f["moving"][1:], state["fleets"]["moving"][1:])

    def test_allied_and_hostile_counted_stationary_aliens_scale(self):
        state = fixture()
        for race, relation in ((3, 2), (4, 6)):
            alien(state["civilizations"], race=race, relation=relation)
            row = fleet_at(state["civilizations"][race-2], 1);row[21:23] = struct.pack("<H", 20)
            store_fleet(state["civilizations"][race-2], 1, row)
            store_fleet(state["civilizations"][race-2], 2, row)
        battle = build(state)
        for side in ("friendly", "hostile"):
            for row in battle[side+"_groups"]:
                if row[0] == 2:row[1] = 10
        _, civs, _, _ = apply(state, battle)
        for race in (3, 4):
            self.assertEqual(fleet_at(civs[race-2], 1)[21], 10)
            self.assertEqual(fleet_at(civs[race-2], 2)[21], 20)

    def test_battle_world_only_is_changed_and_player_planet_storage_is_untouched(self):
        state = fixture();state["civilizations"][1][27] = 2
        for key, count in (("1:5:0", 20), ("1:5:1", 30)):
            raw = state["worlds"][key]["raw"];raw[0] = 3;raw[43] = count
        battle = build(state);battle["hostile_groups"][0][1] = 10
        _, _, worlds, _ = apply(state, battle)
        self.assertEqual(worlds["1:5:0"]["raw"][43], 10)
        self.assertEqual(worlds["1:5:1"], state["worlds"]["1:5:1"])
        state["worlds"]["1:5:0"]["raw"][0] = 1
        _, _, worlds, _ = apply(state, build(state))
        self.assertEqual(worlds["1:5:0"], state["worlds"]["1:5:0"])

    def test_large_world_product_cannot_overflow_to_billions_of_survivors(self):
        state = fixture();state["civilizations"][1][27] = 2
        raw = state["worlds"]["1:5:0"]["raw"];raw[0] = 3;raw[43:47] = struct.pack("<I", 10000000)
        battle = build(state);battle["hostile_reserve"] = [0]*4
        for row in battle["hostile_groups"]:row[1] = 15
        _, _, worlds, losses = apply(state, battle)
        self.assertEqual(struct.unpack("<I", bytes(worlds["1:5:0"]["raw"][43:47]))[0], 300)
        self.assertEqual(losses["hostile"][0], 9999700)

    def test_survivor_overcount_and_negative_stock_reject_without_partial_changes(self):
        for malformed in ("overcount", "negative"):
            state = fixture();battle = build(state)
            if malformed == "overcount":battle["friendly_groups"][0][1] = 32
            else:state["fleets"]["moving"][0][71:73] = [255, 255]
            before = deepcopy((state, battle))
            with self.assertRaises(GameError):apply(state, battle)
            self.assertEqual((state, battle), before)

    def test_campaign_forces_through_setup_battle_and_survivor_writeback(self):
        state = fixture();row = player();row[69:109] = [0]*40
        row[99:109] = struct.pack("<5h", 10, 0, 0, 112, 999);state["fleets"]["moving"] = [row]
        state["civilizations"][1][27] = 2;raw = state["worlds"]["1:5:0"]["raw"];raw[0] = 3;raw[43] = 30
        battle = initialize_ground_battle(build(state), MOTION, player_attacking=True);battle["rng"] = 1994
        for _ in range(2000):
            battle, _ = ground_frame(battle, MOTION, ATTACK_RULES, MOVEMENT_RULES)
            if battle["done"]:break
        self.assertTrue(battle["done"]);self.assertTrue(battle["player_won"])
        f, _, worlds, losses = apply(state, battle)
        self.assertEqual(struct.unpack("<5h", bytes(f["moving"][0][99:109])), (10, 0, 0, 112, 999))
        self.assertEqual(worlds["1:5:0"]["raw"][43:59], [0]*16)
        self.assertEqual(losses["hostile"], [30, 0, 0, 0])


if __name__ == "__main__":unittest.main()
