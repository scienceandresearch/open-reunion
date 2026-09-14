"""Space persistence, atomic results and space-to-ground campaign continuation."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from test_strategy_session import battle_session, finish as finish_ground
from test_space_roster import fixture as roster_fixture, alien
from openreunion.core import GameError
from openreunion.dos.session import RecoveredSession, SCHEMA
from openreunion.dos.space_combat import RULE_START
from openreunion.dos.space_validation import validate_space_rules


def prepared(*, attacking=True, ground=True, empty=False):
    destination = (1, 5, 1) if attacking else (1, 5, 0)
    session = battle_session(attacking=attacking, destination=destination)
    session.state["ground_encounter"] = None
    rules = roster_fixture()[-1];table = rules["bytes"]
    # Synthetic paths occupy their own bank, away from hull statistics.
    for direction in range(1, 9):table[0x6E7+direction-RULE_START] = 2
    for region in range(1, 10):
        for index in range(8):table[0x72E+9*region+1+index-RULE_START] = 1
    session.catalog["battle_rules"]["space"] = rules
    player = session.state["fleets"]["moving"][0]
    player[29:39] = struct.pack("<5h", 0 if empty else 4, 100, 100, 100, 100)
    if not empty:
        if attacking:session.state["worlds"]["1:5:1"]["raw"][27:31] = struct.pack("<I", 3)
        else:alien(session.state["campaign"]["civilizations"], quantity=3)
    session.begin_space_battle(destination, player_attacking=attacking, ground_requested=ground, conquering_owner=3)
    return session


def finish_space(session):
    for _ in range(30):
        if session.state["space_encounter"]["phase"] == "result":return
        session.apply("space_tick", frames=120)
    raise AssertionError("Prepared space battle did not complete")


class SpaceSessionTests(unittest.TestCase):
    def test_save_live_result_closed_and_continue_ground_exactly(self):
        session = prepared();date = deepcopy(session.state["date"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"battle.json"
            session.apply("space_tick", frames=3);session.save(path)
            resumed = RecoveredSession.load(session.catalog, path)
            self.assertEqual(session.state, resumed.state)
            finish_space(session);finish_space(resumed)
            self.assertEqual(session.state, resumed.state)
            self.assertTrue(session.state["space_encounter"]["player_won"])
            self.assertEqual(session.state["date"], date)
            self.assertEqual(session.state["space_encounter"]["losses"]["hostile"], [3, 0, 0, 0])
            session.save(path);resumed = RecoveredSession.load(session.catalog, path)
            self.assertEqual(session.apply("space_acknowledge"), resumed.apply("space_acknowledge"))
            self.assertEqual(session.state, resumed.state)
            self.assertEqual(session.state["ground_encounter"]["phase"], "setup")
            self.assertEqual(session.state["space_encounter"]["next_phase"], "ground_setup")
            session.save(path);resumed = RecoveredSession.load(session.catalog, path)
            for current in (session, resumed):
                current.apply("ground_start");finish_ground(current);current.apply("ground_acknowledge")
            self.assertEqual(session.state, resumed.state)
            self.assertEqual(session.state["worlds"]["1:5:1"]["raw"][0], 1)
            self.assertEqual(session.state["products"][18]["research_state"], 3)
            for current in (session, resumed):current.apply("advance", hours=1)
            self.assertEqual(session.state, resumed.state)

    def test_retreat_keeps_live_casualties_but_loses_and_withdraws_once(self):
        session = prepared();seed = session.state["campaign"]["rng"]
        events = session.apply("space_retreat")
        self.assertEqual(events[-1], {"kind": "space_result_requested"})
        encounter = session.state["space_encounter"]
        self.assertFalse(encounter["player_won"]);self.assertTrue(encounter["retreated"])
        self.assertEqual(encounter["losses"], {"friendly": [0]*4, "hostile": [0]*4})
        self.assertEqual(session.state["campaign"]["rng"], seed)
        before = deepcopy(session.state)
        for action in ("space_tick", "space_retreat", "advance"):
            with self.assertRaises(GameError):session.apply(action, **({"hours": 1} if action == "advance" else {}))
            self.assertEqual(session.state, before)
        session.apply("space_acknowledge")
        self.assertIsNone(session.state["ground_encounter"])
        self.assertEqual(session.state["campaign"]["flags"]["5d67"], 0)
        self.assertFalse(session.state["fleets"]["moving"])
        before = deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("space_acknowledge")
        self.assertEqual(session.state, before)

    def test_defending_retreat_hands_off_to_ground_defense(self):
        session = prepared(attacking=False)
        session.apply("space_retreat");session.apply("space_acknowledge")
        encounter = session.state["ground_encounter"]
        self.assertEqual(encounter["phase"], "setup");self.assertFalse(encounter["player_attacking"])
        self.assertEqual(encounter["conquering_owner"], 3)
        session.apply("ground_start");session.apply("ground_command", command="retreat")
        session.apply("ground_acknowledge")
        self.assertTrue(session.defeated());self.assertEqual(session.state["campaign_phase"], "defeat")

    def test_space_only_win_rewards_are_ordered_and_once_only(self):
        session = prepared(ground=False)
        session.state["campaign"]["flags"].update({"5d6d": 1, "5d75": 1})
        finish_space(session)
        expected = [("message", 16), ("scene", 3), ("message", 19), ("scene", 3)]
        self.assertEqual(session.apply("space_acknowledge"), expected)
        self.assertEqual(session.state["presentation_requests"], [{"kind": k, "id": i} for k, i in expected])
        self.assertIsNone(session.state["ground_encounter"])
        snapshot = deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("space_acknowledge")
        self.assertEqual(snapshot, session.state)
        session.apply("advance", hours=1)

    def test_empty_battle_is_a_loss_not_an_unearned_win(self):
        session = prepared(empty=True)
        session.apply("space_tick")
        self.assertEqual(session.state["space_encounter"]["phase"], "result")
        self.assertFalse(session.state["space_encounter"]["player_won"])
        session.apply("space_acknowledge")
        self.assertIsNone(session.state["ground_encounter"])

    def test_active_battle_blocks_campaign_and_other_battles_but_allows_admin(self):
        session = prepared();before = deepcopy(session.state)
        for action, arguments in (("advance", {"hours": 1}), ("ground_start", {}),
                                  ("space_tick", {"frames": 0}), ("space_tick", {"frames": True}),
                                  ("space_tick", {"frames": 121}), ("space_acknowledge", {})):
            with self.assertRaises(GameError):session.apply(action, **arguments)
            self.assertEqual(session.state, before)
        for method in (session.begin_space_battle, session.begin_ground_battle):
            with self.assertRaises(GameError):method((1, 5, 1), player_attacking=True)
            self.assertEqual(session.state, before)
        session.admin_enabled = True;session.apply("admin", command="give credits 100")
        self.assertEqual(session.state["resources"]["credits"], before["resources"]["credits"]+100)

    def test_malformed_saves_fail_before_replacing_existing_file(self):
        session = prepared();session.apply("space_tick", frames=2)
        def raw(state):return state["space_encounter"]["battle"]["friendly"][0]["raw"]
        def battle(state):return state["space_encounter"]["battle"]
        mutations = [lambda s: s["space_encounter"].update(phase="setup"),
            lambda s: s["space_encounter"].update(destination=[99, 1, 0]),
            lambda s: s["space_encounter"].update(player_attacking=1),
            lambda s: s["space_encounter"].update(fighter_level=1),
            lambda s: s["space_encounter"].update(losses={"friendly": [0]*4, "hostile": [0]*4}),
            lambda s: battle(s).update(done=True), lambda s: battle(s).update(frame=5),
            lambda s: battle(s).update(rng=True), lambda s: battle(s).update(rng=99),
            lambda s: battle(s).update(friendly_count=501), lambda s: battle(s).update(instant_kill=True),
            lambda s: raw(s).__setitem__(1, 0), lambda s: raw(s).__setitem__(8, 8),
            lambda s: raw(s).__setitem__(9, 8), lambda s: raw(s).__setitem__(10, 255),
            lambda s: raw(s).__setitem__(slice(4, 6), [0, 0]),
            lambda s: raw(s).__setitem__(slice(4, 6), [255, 127]),
            lambda s: battle(s)["friendly"][0]["origin"].update(slot=2),
            lambda s: battle(s)["friendly"][0]["origin"].update(extra=1),
            lambda s: battle(s).update(friendly=battle(s)["friendly"]*126),
            lambda s: s.update(campaign_phase="victory")]
        before = deepcopy(session.state)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"battle.json";session.save(path);saved = path.read_bytes()
            for mutate in mutations:
                with self.subTest(mutation=mutate):
                    damaged = deepcopy(before);mutate(damaged);session.state = damaged
                    with self.assertRaises(GameError):session.save(path)
                    self.assertEqual(path.read_bytes(), saved)
            session.state = before

    def test_result_validation_rejects_forged_winner_and_unfinished_explosion(self):
        session = prepared();finish_space(session);before = deepcopy(session.state)
        for change in (lambda e: e.update(player_won=False), lambda e: e.update(next_phase="starmap"),
                       lambda e: e["battle"].update(explosions=True),
                       lambda e: e["battle"]["hostile"][0]["raw"].__setitem__(10, 1),
                       lambda e: e["losses"]["hostile"].__setitem__(0, -1)):
            damaged = deepcopy(before);change(damaged["space_encounter"])
            with self.assertRaises(GameError):RecoveredSession(session.catalog, damaged)

    def test_v8_migration_preserves_ground_state_and_rejects_unexpected_fields(self):
        session = battle_session();state = deepcopy(session.state)
        state["schema"] = "recovered-strategy-v8";del state["space_encounter"];del state['active_scene']
        del state["active_dialog"];del state["campaign"]["system_observatories"];del state["campaign"]["bar"]
        del state["battle_requests"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"old.json";path.write_text(json.dumps(state), encoding="utf-8")
            loaded = RecoveredSession.load(session.catalog, path)
            self.assertEqual(loaded.state, session.state);self.assertEqual(loaded.state["schema"], SCHEMA)
            state["unexpected"] = 1;path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(GameError):RecoveredSession.load(session.catalog, path)

    def test_withdrawal_overflow_keeps_the_result_available_without_partial_rewards(self):
        session = prepared(attacking=False)
        session.state["space_encounter"] = None
        local = [0]*161;local[0] = 5;local[19:23] = [1, 5, 0, 7]
        local[99:101] = struct.pack("<h", 32767)
        session.state["fleets"]["local"] = [local]
        session.begin_space_battle((1, 5, 0), player_attacking=False, ground_requested=True, conquering_owner=3)
        session.apply("space_retreat");before = deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("space_acknowledge")
        self.assertEqual(session.state, before)
        self.assertIsNone(session.state["ground_encounter"])
        self.assertEqual(session.state["space_encounter"]["phase"], "result")

    def test_bad_rule_tables_and_missing_defender_leave_campaign_unchanged(self):
        session = prepared();session.state["space_encounter"] = None;before = deepcopy(session.state)
        for value in (None, 1, True, 13):
            with self.assertRaises(GameError):session.begin_space_battle((1, 5, 1), player_attacking=False,
                ground_requested=True, conquering_owner=value)
            self.assertEqual(session.state, before)
        rules = session.catalog["battle_rules"]["space"]
        for at, value in ((0x6E8, 255), (0x738, 255), (0x7CD, 255)):
            damaged = deepcopy(rules);damaged["bytes"][at-RULE_START] = value
            with self.assertRaises(GameError):validate_space_rules(damaged)


if __name__ == "__main__":unittest.main()
