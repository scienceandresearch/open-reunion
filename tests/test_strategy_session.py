"""Canonical campaign state and persisted ground encounters, without DOS assets."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from test_surface import surface_session
from test_space_roster import player
from test_ground_setup import RULES as SETUP
from test_ground_geometry import MOTION
from test_ground_frame import RULES as ATTACK
from test_ground_movement import RULES as MOVEMENT
from test_ground_controls import RULES as CONTROL
from openreunion.core import GameError
from openreunion.dos.aliens import fleet_at, store_fleet
from openreunion.dos.ground_validation import validate_battle_rules
from openreunion.dos.navigation import contact
from openreunion.dos.session import RecoveredSession
from openreunion.dos.space_combat import RULE_START, RULE_END
from openreunion.dos.strategy import (FLAGS, TIMERS, relations, navigation_view,
    commit_navigation, campaign_work, commit_campaign_work)


def battle_session(*, attacking=True, destination=(1, 5, 1)):
    session = surface_session()
    names = ("morgrul_base", "morgrul_early_base", "morgrul_spread", "lisonian_base",
             "lisonian_spread", "undorling_base", "undorling_spread", "earth_base", "earth_spread")
    session.catalog["battle_rules"] = deepcopy({"ground_setup": SETUP, "ground_motion": MOTION,
        "ground_attacks": ATTACK, "ground_movement": MOVEMENT, "ground_controls": CONTROL,
        "aliens": {key: [0]*8 for key in names}, "space": {"bytes": [0]*(RULE_END-RULE_START)}})
    row = player();row[19:22] = list(destination);row[69:109] = [0]*40
    row[99:109] = struct.pack("<5h", 10, 0, 0, 112, 999)
    session.state["fleets"]["moving"] = [row]
    raw = session.state["worlds"][":".join(map(str, destination))]["raw"]
    raw[0:2] = [3 if attacking else 1, 1];raw[3] = raw[6] = raw[21] = 1
    raw[43:47] = struct.pack("<I", 30)
    session.state["campaign"]["civilizations"][1][27] = 2
    session.state["campaign"]["civilizations"][2][27] = 4
    session.state["products"][18]["research_state"] = 0
    session.begin_ground_battle(destination, player_attacking=attacking, conquering_owner=3)
    return session


def finish(session):
    for _ in range(30):
        if session.state["ground_encounter"]["phase"] == "result":return
        session.apply("ground_tick", frames=120)
    raise AssertionError("Prepared ground battle failed to complete in 3600 frames")


class StrategySessionTests(unittest.TestCase):
    def test_navigation_contact_updates_canonical_records_and_preserves_dormant_slots(self):
        session = surface_session();campaign = session.state["campaign"]
        civ = campaign["civilizations"][2];civ[38] = 1
        store_fleet(civ, 1, [0]*27);store_fleet(civ, 7, list(range(27)))
        before = deepcopy(campaign);view = navigation_view(campaign)
        events = contact(view, session.state["products"], 4)
        view["navigation"]["alien_fleets"][2][0][2] = 1
        self.assertEqual(campaign, before)
        commit_navigation(campaign, view)
        self.assertEqual(events, [("message", 15), ("dialog", 5)])
        self.assertEqual(relations(campaign)[2], 6)
        self.assertTrue(1500 <= campaign["timers"]["5d76"] < 2000)
        self.assertEqual(fleet_at(civ, 1)[2], 1)
        self.assertEqual(fleet_at(civ, 7), list(range(27)))
        self.assertNotIn("alien_status", campaign)
        self.assertEqual(set(campaign["navigation"]), {"planet_visibility", "encounter", "ending"})
        view["idea_timers"][0] = 42
        self.assertEqual(campaign["idea_timers"][0], -1)
        RecoveredSession(session.catalog, session.state)

    def test_work_roundtrip_has_one_owner_for_shared_story_fields(self):
        session = surface_session();before = deepcopy(session.state)
        work = campaign_work(session.state);commit_campaign_work(session.state, work)
        self.assertEqual(session.state, before)
        work["flags"].update({"5d4c": 1, "5d62": 1, "23c": 2, "5d67": 1})
        work["timers"].update({"5d4a": 7, "5d52": 9})
        work["civilizations"][0][27] = 255
        commit_campaign_work(session.state, work);campaign = session.state["campaign"]
        self.assertEqual(set(campaign["flags"]), FLAGS);self.assertEqual(set(campaign["timers"]), TIMERS)
        self.assertTrue(campaign["carrier_failure_reported"] and campaign["hyperspace_allowed"])
        self.assertEqual((campaign["carrier_failure_remaining"], campaign["research_block_remaining"]), (7, 9))
        self.assertEqual(campaign["navigation"]["ending"], 2)
        self.assertEqual(relations(campaign)[0], -1)
        work["civilizations"][0][27] = 0
        self.assertEqual(campaign["civilizations"][0][27], 255)
        RecoveredSession(session.catalog, session.state)

    def test_battle_disk_resume_preserves_frames_losses_rewards_and_future_clock(self):
        session = battle_session();date = list(session.state["date"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"battle.json"
            session.apply("ground_edit", operation="remove", selection=1)
            session.save(path);restored = RecoveredSession.load(session.catalog, path)
            self.assertEqual(restored.state, session.state)
            session.apply("ground_start");session.apply("ground_tick", frames=50)
            session.save(path);restored = RecoveredSession.load(session.catalog, path)
            for _ in range(30):
                events = session.apply("ground_tick", frames=120)
                self.assertEqual(restored.apply("ground_tick", frames=120), events)
                self.assertEqual(restored.state, session.state)
                if session.state["ground_encounter"]["phase"] == "result":break
            self.assertEqual(session.state["ground_encounter"]["phase"], "result")
            self.assertEqual(session.state["date"], date)
            self.assertTrue(session.state["ground_encounter"]["battle"]["player_won"])
            self.assertEqual(session.state["ground_encounter"]["losses"]["hostile"], [30, 0, 0, 0])
            self.assertEqual(session.state["worlds"]["1:5:1"]["raw"][0], 3)
            session.save(path);restored = RecoveredSession.load(session.catalog, path)
            self.assertEqual(restored.apply("ground_acknowledge"), session.apply("ground_acknowledge"))
            self.assertEqual(restored.state, session.state)
            self.assertEqual(session.state["worlds"]["1:5:1"]["raw"][0], 1)
            self.assertEqual(session.state["products"][18]["research_state"], 3)
            self.assertEqual(relations(session.state["campaign"])[2], 6)
            self.assertEqual(session.state["presentation_requests"][:3], [
                {"kind": "civilization_destroyed", "id": 3}, {"kind": "message", "id": 35}, {"kind": "scene", "id": 3}])
            before = deepcopy(session.state)
            with self.assertRaises(GameError):session.apply("ground_acknowledge")
            self.assertEqual(session.state, before)
            session.save(path);restored = RecoveredSession.load(session.catalog, path)
            session.apply("advance", hours=1);restored.apply("advance", hours=1)
            self.assertEqual(restored.state, session.state)

    def test_active_battle_rejects_campaign_actions_but_allows_logged_resource_assistance(self):
        session = battle_session();before = deepcopy(session.state)
        for action, args in (("advance", {"hours": 1}), ("hire", {"role": "fighter", "rank": 1}),
                             ("ground_tick", {}), ("ground_acknowledge", {})):
            with self.subTest(action=action), self.assertRaises(GameError):session.apply(action, **args)
            self.assertEqual(session.state, before)
        with self.assertRaises(GameError):session.apply("admin", command="give credits 100")
        session.admin_enabled = True;session.apply("admin", command="give credits 100")
        self.assertEqual(session.state["ground_encounter"], before["ground_encounter"])
        self.assertEqual(session.state["resources"]["credits"], before["resources"]["credits"]+100)
        self.assertTrue(session.state["assisted"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"assisted.json";session.save(path)
            self.assertFalse(RecoveredSession.load(session.catalog, path).admin_enabled)

    def test_defensive_retreat_persists_terminal_state_after_acknowledgment(self):
        session = battle_session(attacking=False, destination=(1, 5, 0))
        session.apply("ground_start");session.apply("ground_command", command="retreat")
        self.assertFalse(session.defeated())
        session.apply("ground_acknowledge")
        self.assertEqual(session.state["campaign_phase"], "defeat")
        self.assertTrue(session.defeated())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"defeat.json";session.save(path)
            restored = RecoveredSession.load(session.catalog, path)
            with self.assertRaises(GameError):restored.apply("advance", hours=1)
            self.assertEqual(restored.state, session.state)

    def test_invalid_frame_counts_reject_without_mutation(self):
        session = battle_session();session.apply("ground_start");before = deepcopy(session.state)
        for frames in (0, -1, 121, True, 1.5):
            with self.subTest(frames=frames), self.assertRaises(GameError):session.apply("ground_tick", frames=frames)
            self.assertEqual(session.state, before)

    def test_malformed_battle_saves_are_rejected_and_do_not_overwrite_valid_save(self):
        session = battle_session();session.apply("ground_start")
        # Each case changes a different structural or cross-record invariant.
        edits = [
            (("ground_encounter", "phase"), "result"),
            (("ground_encounter", "destination"), [8, 255, 255]),
            (("ground_encounter", "conquering_owner"), 13),
            (("ground_encounter", "battle", "done"), True),
            (("ground_encounter", "battle", "rng"), 99),
            (("ground_encounter", "battle", "instant_kill"), True),
            (("ground_encounter", "battle", "board", 0, 0), 120),
            (("ground_encounter", "battle", "board"), []),
            (("ground_encounter", "battle", "friendly_groups", 0, 0), 5),
            (("ground_encounter", "battle", "friendly_groups", 0, 8), 5),
            (("ground_encounter", "battle", "friendly_groups", 0, 18), 21),
            (("ground_encounter", "battle", "friendly_groups", 0, 13), 10),
            (("ground_encounter", "battle", "friendly_primary", 0), 1),
            (("ground_encounter", "battle", "friendly_reserve", 0), 1),
            (("ground_encounter", "battle", "friendly_projectiles"), [list(struct.pack("<7hI", 0, 0, 0, 0, 1, 0, 0, 1))]),
            (("ground_encounter", "battle", "selected_group"), 20),
            (("campaign", "civilizations", 0, 38), 8),
            (("presentation_requests",), [{"kind": "scene", "id": 11}]),
            (("schema",), "recovered-strategy-v7"),
            (("campaign_phase",), "victory"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            valid = Path(directory)/"valid.json";invalid = Path(directory)/"invalid.json"
            session.save(valid);original = valid.read_bytes();before = deepcopy(session.state)
            for keys, value in edits:
                candidate = deepcopy(before);target = candidate
                for key in keys[:-1]:target = target[key]
                target[keys[-1]] = value
                invalid.write_text(json.dumps(candidate), encoding="utf-8")
                with self.subTest(keys=keys):
                    with self.assertRaises(GameError):RecoveredSession.load(session.catalog, invalid)
                    session.state = candidate
                    with self.assertRaises(GameError):session.save(valid)
                    self.assertEqual(valid.read_bytes(), original)
                session.state = deepcopy(before)

    def test_result_cannot_claim_victory_before_combat_or_invent_loss_totals(self):
        session = battle_session();session.apply("ground_start")
        candidate = deepcopy(session.state);encounter = candidate["ground_encounter"]
        encounter.update(phase="result", losses={"friendly": [0]*4, "hostile": [0]*4})
        encounter["battle"].update(done=True, player_won=True)
        with self.assertRaises(GameError):RecoveredSession(session.catalog, candidate)
        finish(session)
        candidate = deepcopy(session.state);candidate["ground_encounter"]["losses"]["hostile"][0] -= 1
        with self.assertRaises(GameError):RecoveredSession(session.catalog, candidate)

    def test_battle_tables_are_bounded_and_required_before_opening_encounter(self):
        session = battle_session();rules = session.catalog["battle_rules"]
        validate_battle_rules(rules)
        for group, field, value in (("ground_motion", "x", [0, 1, 0, -1, 0]),
                                    ("ground_attacks", "cooldowns", [0, 1, 1, 1]),
                                    ("aliens", "earth_base", [0]*7), ("space", "bytes", [])):
            damaged = deepcopy(rules);damaged[group][field] = value
            with self.subTest(group=group), self.assertRaises(GameError):validate_battle_rules(damaged)
        del session.catalog["battle_rules"]
        with self.assertRaises(GameError):RecoveredSession(session.catalog, session.state)
        plain = surface_session();before = deepcopy(plain.state)
        with self.assertRaises(GameError):plain.begin_ground_battle((1, 5, 1), player_attacking=True)
        self.assertEqual(plain.state, before)


if __name__ == "__main__":unittest.main()
