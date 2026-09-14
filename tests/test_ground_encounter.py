"""Connected ground phases, single application of results and replay continuity."""
from copy import deepcopy
import json
import struct
import unittest
from test_ground_outcome import fixture as campaign_fixture, RULES as ALIEN_RULES
from test_ground_setup import RULES as SETUP_RULES
from test_ground_geometry import MOTION
from test_ground_frame import RULES as ATTACK_RULES
from test_ground_movement import RULES as MOVEMENT_RULES
from test_ground_controls import RULES as CONTROL_RULES
from test_space_roster import player
from openreunion.core import GameError
from openreunion.dos.ground_encounter import (open_ground_encounter, edit_ground_encounter, start_ground_encounter,
    command_ground_encounter, tick_ground_encounter, acknowledge_ground_result)


def fixture(*, attacking=True, destination=(1, 5, 0)):
    state, catalog = campaign_fixture();row = player();row[19:22] = list(destination);row[69:109] = [0]*40
    row[99:109] = struct.pack("<5h", 10, 0, 0, 112, 999);state["fleets"]["moving"] = [row]
    raw = [0]*65;raw[:2] = [3 if attacking else 1, 1];raw[21] = 1;raw[43] = 30
    state["worlds"][":".join(map(str, destination))] = {"raw": raw};state["civilizations"][1][27] = 2
    state = open_ground_encounter(state, destination, SETUP_RULES, player_attacking=attacking, conquering_owner=3)
    return state, catalog


def tick(state):return tick_ground_encounter(state, MOTION, ATTACK_RULES, MOVEMENT_RULES)
def command(state, action, **args):return command_ground_encounter(state, MOTION, CONTROL_RULES, action, **args)


class GroundEncounterTests(unittest.TestCase):
    def test_setup_edits_conserve_reserves_and_start_resets_battle_controls(self):
        state, _ = fixture();before = deepcopy(state)
        edited = edit_ground_encounter(state, SETUP_RULES, "remove", 1)
        self.assertEqual(edited["ground_encounter"]["battle"]["friendly_reserve"], [0, 0, 0, 5])
        started = start_ground_encounter(edited, MOTION);battle = started["ground_encounter"]["battle"]
        self.assertEqual(started["ground_encounter"]["phase"], "fighting")
        self.assertEqual((battle["selected_group"], battle["control_mode"], battle["retreated"]), (0, 1, False))
        self.assertEqual(battle["rng"], state["rng"]);self.assertEqual(state, before)

    def test_natural_result_applies_losses_before_acknowledgment_and_rewards_once(self):
        state, catalog = fixture();state = start_ground_encounter(state, MOTION)
        for _ in range(2000):
            state, _ = tick(state)
            if state["ground_encounter"]["phase"] == "result":break
        encounter = state["ground_encounter"]
        self.assertEqual(encounter["phase"], "result");self.assertTrue(encounter["battle"]["player_won"])
        self.assertEqual(encounter["losses"]["hostile"], [30, 0, 0, 0])
        self.assertEqual(state["worlds"]["1:5:0"]["raw"][0], 3)
        self.assertEqual(state["products"][18]["research_state"], 0)
        result, phase, events = acknowledge_ground_result(state, catalog, ALIEN_RULES)
        self.assertEqual(phase, "starmap");self.assertEqual(result["ground_encounter"]["phase"], "closed")
        self.assertEqual(result["worlds"]["1:5:0"]["raw"][0], 1)
        self.assertEqual(result["products"][18]["research_state"], 3)
        self.assertEqual(result["fleets"]["moving"][0][99:109], list(struct.pack("<5h", 10, 0, 0, 112, 999)))
        self.assertIn(("civilization_destroyed", 3), events)
        with self.assertRaises(GameError):acknowledge_ground_result(result, catalog, ALIEN_RULES)
        with self.assertRaises(GameError):tick(state)

    def test_retreat_overrides_pending_win_and_cannot_apply_casualties_twice(self):
        state, catalog = fixture(destination=(1, 5, 1));state = start_ground_encounter(state, MOTION)
        battle = state["ground_encounter"]["battle"];battle["friendly_groups"][0][1] = 0;battle["player_won"] = True
        result, events = command(state, "retreat")
        self.assertEqual(result["ground_encounter"]["phase"], "result")
        self.assertFalse(result["ground_encounter"]["battle"]["player_won"])
        self.assertEqual(result["fleets"]["moving"][0][99:109], list(struct.pack("<5h", 5, 0, 0, 56, 999)))
        self.assertIn({"kind": "ground_result_requested"}, events)
        before = deepcopy(result)
        with self.assertRaises(GameError):command(result, "retreat")
        self.assertEqual(result, before)
        result, phase, events = acknowledge_ground_result(result, catalog, ALIEN_RULES)
        self.assertEqual(phase, "starmap");self.assertEqual(result["worlds"]["1:5:1"]["raw"][0], 3)
        self.assertEqual(events, [("message", 14)])

    def test_defensive_retreat_waits_for_acknowledgment_before_colony_settlement(self):
        state, catalog = fixture(attacking=False);state = start_ground_encounter(state, MOTION)
        result, _ = command(state, "retreat")
        self.assertEqual(result["worlds"]["1:5:0"]["raw"][0], 1)
        result, phase, _ = acknowledge_ground_result(result, catalog, ALIEN_RULES)
        self.assertEqual(phase, "defeat");self.assertEqual(result["worlds"]["1:5:0"]["raw"][0], 3)

    def test_pause_skips_frame_and_rng_and_context_cancel_resumes(self):
        state, _ = fixture();state = start_ground_encounter(state, MOTION)
        state["ground_encounter"]["battle"]["control_mode"] = 2
        paused, events = tick(state);self.assertEqual(paused, state);self.assertEqual(events, [])
        resumed, _ = command(paused, "context_cancel");resumed, _ = tick(resumed)
        self.assertNotEqual(resumed["rng"], state["rng"])

    def test_json_roundtrip_midbattle_and_at_result_preserves_future_frames_and_rewards(self):
        state, catalog = fixture();state = start_ground_encounter(state, MOTION)
        for _ in range(50):state, _ = tick(state)
        restored = json.loads(json.dumps(state))
        for _ in range(2000):
            state, events = tick(state);restored, expected = tick(restored)
            self.assertEqual((restored, expected), (state, events))
            if state["ground_encounter"]["phase"] == "result":break
        self.assertEqual(state["ground_encounter"]["phase"], "result")
        restored = json.loads(json.dumps(state))
        self.assertEqual(acknowledge_ground_result(restored, catalog, ALIEN_RULES), acknowledge_ground_result(state, catalog, ALIEN_RULES))

    def test_wrong_phase_and_failed_acknowledgment_leave_records_unchanged(self):
        state, catalog = fixture();before = deepcopy(state)
        with self.assertRaises(GameError):tick(state)
        with self.assertRaises(GameError):acknowledge_ground_result(state, catalog, ALIEN_RULES)
        with self.assertRaises(GameError):open_ground_encounter(state, (1, 5, 0), SETUP_RULES, player_attacking=True)
        self.assertEqual(state, before)
        state = start_ground_encounter(state, MOTION)
        for _ in range(2000):
            state, _ = tick(state)
            if state["ground_encounter"]["phase"] == "result":break
        before = deepcopy(state);catalog["worlds"] = []
        with self.assertRaises(GameError):acknowledge_ground_result(state, catalog, ALIEN_RULES)
        self.assertEqual(state, before)

    def test_base_order_permission_comes_from_operating_completed_building_at_exact_world(self):
        for active, complete, moon in ((0, True, 0), (1, False, 0), (1, True, 1), (1, True, 0)):
            state, _ = fixture();state = start_ground_encounter(state, MOTION)
            state["ground_encounter"]["battle"]["selected_group"] = 21
            state["buildings"] = [[18, 1, 5, moon, 1, 1, 0 if complete else 10, 100, active, 0, 0, 0, 0, 100]]
            result, _ = command(state, "attack")
            self.assertEqual(result["ground_encounter"]["battle"]["control_mode"], 4 if active and complete and moon == 0 else 1)


if __name__ == "__main__":unittest.main()
