"""Withdrawal, disbanding, rewards and the space-to-ground handoff."""
from copy import deepcopy
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.core import GameError
from openreunion.dos.aliens import fleet_at, store_fleet
from openreunion.dos.navigation import depart
from openreunion.dos.space_outcome import FLAGS, space_outcome, withdraw_space_forces
from openreunion.dos.space_roster import build_space_battle
from openreunion.dos.space_combat import space_tick, survivor_roster
from openreunion.dos.space_casualties import apply_casualties
from test_space_roster import fixture as roster_fixture, player, alien


def fixture():
    args = roster_fixture()
    state = {"fleets": args[0], "civilizations": args[1], "worlds": args[2], "rng": 1994,
             "flags": {f"{at:x}": 0 for at in FLAGS}, "training_phase": 1,
             "products": [{"research_state": 0} for _ in range(35)], "idea_timers": [-1]*35}
    return state


def finish(state, *, won=True, attacking=True, ground=False, destination=(1, 5, 0)):
    return space_outcome(state, destination, player_won=won, player_attacking=attacking, ground_requested=ground)


class SpaceOutcomeTests(unittest.TestCase):
    def test_ground_setup_requires_the_attacker_to_win_and_a_ground_request(self):
        for won in (False, True):
            for attacking in (False, True):
                for ground in (False, True):
                    _, phase, _ = finish(fixture(), won=won, attacking=attacking, ground=ground)
                    self.assertEqual(phase, "ground_setup" if ground and won == attacking else "starmap")

    def test_first_space_victory_schedules_two_ideas_once(self):
        state, _, _ = finish(fixture())
        self.assertEqual(state["flags"]["5d67"], 1)
        self.assertTrue(20 <= state["idea_timers"][12] < 40)
        self.assertTrue(90 <= state["idea_timers"][16] < 140)
        again, _, _ = finish(state);self.assertEqual(again, state)

    def test_locked_and_unscheduled_guards_preserve_rng(self):
        state = fixture();state["products"][12]["research_state"] = 5;state["idea_timers"][16] = 0
        result, _, _ = finish(state)
        self.assertEqual(result["rng"], state["rng"])
        self.assertEqual(result["idea_timers"], state["idea_timers"])

    def test_ordered_story_rewards_and_phase_changes(self):
        state = fixture();state["flags"]["5d6d"] = 1;state["flags"]["5d75"] = 1
        result, _, events = finish(state)
        self.assertEqual(events, [("message", 16), ("scene", 3), ("message", 19), ("scene", 3)])
        self.assertEqual(result["training_phase"], 4)
        self.assertEqual([result["flags"][key] for key in ("5d6d", "5d75", "164", "5d3c")], [0, 0, 2, 1])
        self.assertEqual(result["idea_timers"][17], 3)
        self.assertTrue(30 <= result["idea_timers"][19] < 40)
        self.assertTrue(500 <= result["idea_timers"][24] < 600)

    def test_defeat_does_not_grant_rewards_and_system_eight_victory_sets_ending_field(self):
        state = fixture();state["flags"]["5d6d"] = 1;state["flags"]["5d75"] = 1
        result, _, events = finish(state, won=False, destination=(8, 1, 0))
        self.assertEqual(result, state);self.assertEqual(events, [])
        result, _, _ = finish(state, destination=(8, 1, 0));self.assertEqual(result["flags"]["23c"], 2)

    def test_remote_defeat_routes_all_stationary_moving_types_in_order(self):
        state = fixture();rows = [player() for _ in range(4)]
        for i, row in enumerate(rows):row[0] = i+1;row[19:23] = [2, 1, 0, 1]
        traveling = player();traveling[19:23] = [2, 1, 0, 6];rows.append(traveling)
        state["fleets"]["moving"] = rows
        result, _, _ = finish(state, won=False, destination=(2, 1, 0))
        seed = 1994;expected = []
        for row in rows[:4]:row, seed = depart(row, (1, 5, 0), seed);expected.append(row)
        self.assertEqual(result["fleets"]["moving"], expected+[traveling]);self.assertEqual(result["rng"], seed)

    def test_home_disband_merges_army_and_pirate_into_last_exact_local_record(self):
        state = fixture();army = player();pirate = player();pirate[0] = 3
        army[69:71] = [7, 0];pirate[69:71] = [9, 0]
        locals_ = [player(0), player(0)]
        for row in locals_:row[0] = 5;row[29:109] = [0]*80
        remote = player();remote[20] = 7
        state["fleets"] = {"moving": [army, remote, pirate], "local": locals_}
        result, _, _ = finish(state, won=False)
        self.assertEqual(result["fleets"]["moving"], [remote])
        self.assertEqual(result["fleets"]["local"][0], locals_[0])
        self.assertEqual(result["fleets"]["local"][1][29], 4)
        self.assertEqual(result["fleets"]["local"][1][69], 7)

    def test_only_losing_stationary_alien_combat_groups_withdraw(self):
        state = fixture();c = state["civilizations"]
        for race, relation, kind, status in ((3, 2, 2, 1), (4, 6, 2, 1), (5, 2, 1, 1), (6, 2, 2, 2)):
            alien(c, race=race, relation=relation);c[race-2][17:19] = [2, 1]
            row = fleet_at(c[race-2], 1);row[0] = kind;row[2] = status;store_fleet(c[race-2], 1, row)
        result, _, _ = finish(state)
        row = fleet_at(result["civilizations"][1], 1);self.assertEqual(row[8:11], [2, 1, 0]);self.assertEqual(row[2], 2)
        for index in (2, 3, 4):self.assertEqual(result["civilizations"][index], c[index])

    def test_alien_home_unload_includes_ground_stock_and_keeps_dormant_slot(self):
        state = fixture();alien(state["civilizations"]);c = state["civilizations"][1];c[17:19] = [1, 5]
        row = fleet_at(c, 1);row[0] = 2;row[19:21] = [7, 0];store_fleet(c, 1, row);store_fleet(c, 7, row)
        state["worlds"]["1:5:0"]["raw"][0] = 3
        result, _, _ = finish(state)
        raw = result["worlds"]["1:5:0"]["raw"];self.assertEqual(raw[27], 2);self.assertEqual(raw[43], 7)
        self.assertEqual(fleet_at(result["civilizations"][1], 1)[2], 0)
        self.assertEqual(fleet_at(result["civilizations"][1], 7), row)

    def test_stock_overflow_and_bad_flags_reject_atomically(self):
        state = fixture();state["fleets"]["moving"] = [player()];local = player(32767);local[0] = 5
        state["fleets"]["local"] = [local];before = deepcopy(state)
        with self.assertRaises(GameError):finish(state, won=False)
        self.assertEqual(state, before)
        with self.assertRaises(GameError):finish(state, won=1)

    def test_record_derived_fight_applies_casualties_before_outcomes(self):
        args = roster_fixture();state = fixture();state["rng"] = 0;state["fleets"]["moving"] = [player()]
        alien(state["civilizations"]);c = state["civilizations"][1];c[17:19] = [2, 1]
        row = fleet_at(c, 1);row[0] = 2;store_fleet(c, 1, row)
        before = deepcopy(state)
        battle = build_space_battle(state["fleets"], state["civilizations"], state["worlds"], args[3], args[4], state["rng"], args[-1])
        for _ in range(5000):
            battle = space_tick(battle, args[-1])
            if battle["done"]:break
        self.assertTrue(battle["done"])
        state["fleets"], state["civilizations"], state["worlds"], losses = apply_casualties(
            state["fleets"], state["civilizations"], state["worlds"], args[3], survivor_roster(battle))
        state["rng"] = battle["rng"];won = battle["friendly_count"] > 0
        result, phase, _ = finish(state, won=won, ground=True)
        self.assertTrue(won);self.assertEqual(phase, "ground_setup")
        self.assertEqual(result["fleets"]["moving"][0][29], battle["friendly_count"])
        self.assertEqual(fleet_at(result["civilizations"][1], 1)[11], battle["hostile_count"])
        self.assertEqual(fleet_at(result["civilizations"][1], 1)[2], 2)
        self.assertEqual(result["flags"]["5d67"], 1)
        self.assertEqual(before["fleets"]["moving"][0][29], 2)


if __name__ == "__main__":unittest.main()
