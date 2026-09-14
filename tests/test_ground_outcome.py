"""Capital rewards, ending conditions and ground result corruption fixes."""
from copy import deepcopy
import struct
import unittest
from test_ground_conquest import fixture as conquest_fixture, fleet
from openreunion.core import GameError
from openreunion.dos.aliens import fleet_at, store_fleet
from openreunion.dos.campaign import random_bounded
from openreunion.dos.ground_outcome import FLAGS, ground_outcome


RULES = {"morgrul_base": [100]*8, "morgrul_early_base": [10]*8, "morgrul_spread": [0]*8}


def fixture():
    state, catalog = conquest_fixture()
    state.update(flags={f"{at:x}": 0 for at in FLAGS}, known_systems=[1]*8, training_phase=1,
                 products=[{"research_state": 0, "research_remaining": 99} for _ in range(35)],
                 idea_timers=[-1]*35, civilizations=[[0]*228 for _ in range(11)])
    raw = state["worlds"]["1:5:0"]["raw"];raw[0] = 3;raw[1] = 0
    state["worlds"]["1:5:1"]["raw"] = [0]*65
    return state, catalog


def finish(state, catalog, *, won=True, attacking=False, destination=(1, 5, 0), owner=3, ruins=False):
    return ground_outcome(state, destination, catalog, RULES, player_won=won,
                          player_attacking=attacking, conquering_owner=owner, search_ruins=ruins)


class GroundOutcomeTests(unittest.TestCase):
    def test_first_ground_win_schedules_only_its_own_idea_and_only_once(self):
        state, catalog = fixture();before = deepcopy(state)
        result, phase, events = finish(state, catalog)
        self.assertEqual(phase, "starmap");self.assertEqual(events, [])
        self.assertEqual(result["flags"]["5d67"], 1)
        self.assertTrue(20 <= result["idea_timers"][12] < 40)
        self.assertEqual(result["idea_timers"][16:18], [-1, -1])
        self.assertEqual(result["worlds"], state["worlds"])
        self.assertEqual(finish(result, catalog)[0], result);self.assertEqual(state, before)

    def test_capital_destruction_precedes_player_recolonization_and_clears_counted_alien_slots(self):
        state, catalog = fixture();state["worlds"]["1:5:0"]["raw"][1] = 1
        state["worlds"]["1:5:1"]["raw"][0] = 3
        race = state["civilizations"][1];race[38] = 2
        for slot in (1, 2, 7):store_fleet(race, slot, [3]*27)
        result, _, events = finish(state, catalog, attacking=True)
        self.assertEqual(events[:3], [("civilization_destroyed", 3), ("message", 35), ("scene", 3)])
        self.assertEqual(result["worlds"]["1:5:0"]["raw"][0], 1)
        self.assertEqual(result["worlds"]["1:5:1"]["raw"][0], 0)
        self.assertEqual(result["civilizations"][1][38], 0)
        self.assertEqual(fleet_at(result["civilizations"][1], 1), [0]*27)
        self.assertEqual(fleet_at(result["civilizations"][1], 2), [0]*27)
        self.assertEqual(fleet_at(result["civilizations"][1], 7), [3]*27)
        self.assertEqual(result["buildings"][-1][:6], [1, 1, 5, 0, 255, 255])

    def test_morgrul_rewards_keep_unlock_before_timer_and_signed_diplomacy_guard(self):
        for relation in (0, 2, 6, 127, 128, 255):
            state, catalog = fixture();state["worlds"]["1:5:0"]["raw"][1] = 1
            state["civilizations"][2][27] = relation
            result, _, _ = finish(state, catalog)
            self.assertEqual(result["products"][18], {"research_state": 3, "research_remaining": 99})
            self.assertEqual(result["idea_timers"][18], -1)
            self.assertEqual(result["civilizations"][2][27], 6 if 0 < relation < 128 else relation)
            self.assertEqual(result["known_systems"], [1, 1, 1, 0, 0, 0, 1, 1])
            self.assertEqual(result["training_phase"], 5)
            self.assertEqual([result["flags"][key] for key in ("5d8c", "5d71", "5d70", "221")], [1, 0, 1, 2])

    def test_destroyed_civilization_requires_victory_enemy_owner_and_capital_byte_one(self):
        for owner, capital, won in ((3, 0, True), (3, 2, True), (1, 1, True), (3, 1, False)):
            state, catalog = fixture();state["worlds"]["1:5:0"]["raw"][:2] = [owner, capital]
            result, _, events = finish(state, catalog, won=won, attacking=not won, ruins=True)
            self.assertFalse(any(kind == "civilization_destroyed" for kind, _ in events))
            self.assertEqual(result["civilizations"], state["civilizations"])
            self.assertEqual(result["products"][11]["research_state"], 0)

    def test_alliance_gate_accepts_inactive_allied_and_currently_destroyed_races(self):
        state, catalog = fixture();state["worlds"]["1:5:0"]["raw"][:2] = [7, 1]
        for race, active, relation in ((7, 1, 2), (8, 0, 2), (9, 1, 6), (10, 0, 0)):
            state["civilizations"][race-2][15] = active;state["civilizations"][race-2][27] = relation
        result, _, events = finish(state, catalog)
        self.assertEqual(events, [("civilization_destroyed", 7), ("message", 32), ("scene", 5)])
        self.assertEqual(result["training_phase"], 6);self.assertEqual(result["known_systems"][6], 0)
        self.assertEqual(result["products"][32], {"research_state": 5, "research_remaining": 0})

    def test_one_active_unallied_race_blocks_alliance_reward_but_not_capital_destruction(self):
        for blocker in (8, 9, 10):
            state, catalog = fixture();state["worlds"]["1:5:0"]["raw"][:2] = [7, 1]
            state["civilizations"][blocker-2][15] = 1;state["civilizations"][blocker-2][27] = 2
            result, _, events = finish(state, catalog)
            self.assertEqual(events, [("civilization_destroyed", 7)])
            self.assertEqual(result["products"][32], state["products"][32])
            self.assertEqual(result["civilizations"][5][27], 255)

    def test_ruins_and_completion_rewards_do_not_overwrite_research_in_progress(self):
        for progress in (0, 1, 3, 5):
            state, catalog = fixture();state["worlds"]["1:5:0"]["raw"][:2] = [7, 1]
            for product in (11, 32):state["products"][product]["research_state"] = progress
            result, _, events = finish(state, catalog, ruins=True)
            self.assertEqual(result["products"][11]["research_state"], 3 if progress == 0 else progress)
            self.assertEqual(result["products"][11]["research_remaining"], 99)
            self.assertEqual(result["products"][32]["research_remaining"], 0 if progress == 0 else 99)
            self.assertEqual(("message", 13) in events, progress == 0)

    def test_earth_capital_victory_keeps_conquest_and_other_owned_world_cleanup(self):
        state, catalog = fixture();state["worlds"]["1:5:0"]["raw"][:2] = [12, 1]
        state["worlds"]["1:5:1"]["raw"][0] = 12
        result, phase, _ = finish(state, catalog, attacking=True)
        self.assertEqual(phase, "victory");self.assertEqual(result["worlds"]["1:5:0"]["raw"][0], 1)
        self.assertEqual(result["worlds"]["1:5:1"]["raw"][0], 0)

    def test_new_earth_defeat_is_exact_world_and_suppresses_first_loss_reward(self):
        state, catalog = fixture();state["fleets"]["local"] = [fleet()]
        result, phase, events = finish(state, catalog, won=False)
        self.assertEqual(phase, "defeat");self.assertEqual(events, [])
        self.assertEqual(result["flags"]["5d68"], 0);self.assertEqual(result["idea_timers"][16], -1)
        self.assertEqual(result["worlds"]["1:5:0"]["raw"][0], 3)
        self.assertEqual(result["fleets"]["local"], [])
        result, phase, events = finish(state, catalog, won=False, attacking=True, destination=(1, 5, 1))
        self.assertEqual(phase, "starmap");self.assertEqual(events, [("message", 14)])

    def test_first_nonterminal_defeat_reward_is_once_and_respects_research_timer_guards(self):
        for progress, timer in ((0, -1), (5, -1), (0, 0)):
            state, catalog = fixture();state["products"][16]["research_state"] = progress;state["idea_timers"][16] = timer
            result, _, events = finish(state, catalog, won=False, attacking=True, destination=(1, 5, 1))
            self.assertEqual(events, [("message", 14)]);self.assertEqual(result["flags"]["5d68"], 1)
            if progress == 0 and timer == -1:self.assertTrue(5 <= result["idea_timers"][16] < 10)
            else:self.assertEqual(result["rng"], state["rng"])
            again, _, events = finish(result, catalog, won=False, attacking=True, destination=(1, 5, 1))
            self.assertEqual(again, result);self.assertEqual(events, [])

    def test_defensive_loss_settles_exact_world_with_actual_enemy_and_preserves_other_moon(self):
        state, catalog = fixture()
        for identity, owner in (("1:1:1", 1), ("1:1:3", 4)):
            raw = [0]*65;raw[0] = owner;state["worlds"][identity] = {"raw": raw}
        result, _, _ = finish(state, catalog, won=False, destination=(1, 1, 1))
        self.assertEqual(result["worlds"]["1:1:1"]["raw"][0], 3)
        self.assertEqual(result["worlds"]["1:1:3"], state["worlds"]["1:1:3"])
        seed, _ = random_bounded(1994, 5)
        seed, population = random_bounded(seed, 3000)
        self.assertEqual(struct.unpack("<I", bytes(result["worlds"]["1:1:1"]["raw"][13:17]))[0], 2000+population)

    def test_ordered_campaign_rewards_finish_before_conquest_rng(self):
        state, catalog = fixture();state["worlds"]["1:5:0"]["raw"][1] = 1
        state["flags"]["5d6d"] = state["flags"]["5d75"] = 1
        result, _, events = finish(state, catalog, attacking=True)
        self.assertEqual(events, [("civilization_destroyed", 3), ("message", 35), ("scene", 3),
                                  ("message", 16), ("scene", 3), ("message", 16), ("scene", 3)])
        self.assertEqual(result["training_phase"], 4);self.assertEqual(result["idea_timers"][17], -1)
        seed = 1994
        for limit in (20, 10, 100):seed, _ = random_bounded(seed, limit)
        seed, population = random_bounded(seed, 3000)
        for limit in (60, 80):seed, _ = random_bounded(seed, limit)
        self.assertEqual(result["rng"], seed)
        self.assertEqual(struct.unpack("<I", bytes(result["worlds"]["1:5:0"]["raw"][13:17]))[0], 2000+population)

    def test_invalid_flags_owner_and_world_reject_without_partial_rewards(self):
        state, catalog = fixture();before = deepcopy(state)
        for args in ({"won": 1}, {"attacking": 0}, {"ruins": 1}, {"destination": (9, 9, 9)},
                     {"won": False, "owner": True}, {"won": False, "owner": 1}, {"won": False, "owner": 13}):
            with self.assertRaises(GameError):finish(state, catalog, **args)
        self.assertEqual(state, before)

    def test_campaign_forces_fight_then_receive_capital_rewards_and_colony(self):
        from test_ground_setup import fixture as forces_fixture, build
        from test_ground_geometry import MOTION
        from test_ground_frame import RULES as ATTACK_RULES
        from test_ground_movement import RULES as MOVEMENT_RULES
        from test_space_roster import player
        from openreunion.dos.ground_battle import initialize_ground_battle
        from openreunion.dos.ground_frame import ground_frame
        from openreunion.dos.ground_casualties import apply_ground_casualties
        state, catalog = fixture();forces = forces_fixture()
        for key in ("fleets", "civilizations", "worlds"):state[key] = forces[key]
        row = player();row[69:109] = [0]*40;row[99:109] = struct.pack("<5h", 10, 0, 0, 112, 999)
        state["fleets"]["moving"] = [row];state["civilizations"][1][27] = 2
        raw = state["worlds"]["1:5:0"]["raw"];raw[:2] = [3, 1];raw[21] = 1;raw[43] = 30
        battle = initialize_ground_battle(build(state), MOTION, player_attacking=True);battle["rng"] = 1994
        for _ in range(2000):
            battle, _ = ground_frame(battle, MOTION, ATTACK_RULES, MOVEMENT_RULES)
            if battle["done"]:break
        self.assertTrue(battle["done"]);self.assertTrue(battle["player_won"])
        state["fleets"], state["civilizations"], state["worlds"], losses = apply_ground_casualties(
            state["fleets"], state["civilizations"], state["worlds"], (1, 5, 0), battle)
        state["rng"] = battle["rng"]
        result, phase, events = finish(state, catalog, won=battle["player_won"], attacking=battle["player_attacking"])
        self.assertEqual(phase, "starmap");self.assertIn(("civilization_destroyed", 3), events)
        self.assertEqual(result["products"][18]["research_state"], 3)
        self.assertEqual(result["worlds"]["1:5:0"]["raw"][0], 1)
        self.assertEqual(result["fleets"]["moving"][0][99:109], list(struct.pack("<5h", 10, 0, 0, 112, 999)))
        self.assertEqual(losses["hostile"], [30, 0, 0, 0])


if __name__ == "__main__":unittest.main()
