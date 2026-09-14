"""Player-facing space battle identity and notice regression tests."""
from copy import deepcopy
import unittest

from test_space_session import prepared
from openreunion.dos.battle_identity import civilization_name, space_notice, space_opponents, world_name


def names(session):
    session.catalog["alien_names"] = [f"Race {race}" for race in range(2, 13)]


class BattleIdentityTests(unittest.TestCase):
    def test_defense_uses_current_initiator_before_queued_attack(self):
        session = prepared(attacking=False)
        names(session)
        encounter = session.state["space_encounter"]
        session.state["battle_requests"] = [{"race": 7, "slot": 1, "world": [1, 7, 0],
                                              "ground": True, "special": False}]
        self.assertEqual(space_opponents(session.state, session.catalog, encounter), "Race 3")
        self.assertIn("UNDER ATTACK: Race 3", space_notice(session.state, session.catalog, encounter))
        self.assertNotIn("Race 7", space_notice(session.state, session.catalog, encounter))

    def test_mixed_hostiles_are_named_once_and_friendly_allies_are_ignored(self):
        session = prepared(attacking=False)
        names(session)
        encounter = session.state["space_encounter"]
        hostile = encounter["battle"]["hostile"]
        hostile[0]["origin"] = {"source": "alien", "race": 7, "slot": 2}
        hostile[1]["origin"] = {"source": "alien", "race": 7, "slot": 2}
        hostile[2]["origin"] = {"source": "world", "world": "1:5:1"}
        # Race 3 is the saved initiator; race 7 and the world owner are also
        # present in the broad hostile roster, but friendly origins are not.
        session.state["worlds"]["1:5:1"]["raw"][0] = 8
        encounter["battle"]["friendly"][0]["origin"] = {"source": "alien", "race": 11, "slot": 1}
        self.assertEqual(space_opponents(session.state, session.catalog, encounter), "Race 3, Race 7, Race 8")

    def test_incoming_identity_survives_empty_or_destroyed_hostile_roster(self):
        session = prepared(attacking=False)
        names(session)
        encounter = session.state["space_encounter"]
        encounter["battle"]["hostile"] = []
        self.assertEqual(space_opponents(session.state, session.catalog, encounter), "Race 3")
        encounter["battle"]["hostile"] = [{"raw": [0, 1, 0, 0, 0, 0, 0, 0, 2, 1, 1, 0],
                                              "origin": {"source": "alien", "race": 7, "slot": 1}}]
        self.assertEqual(space_opponents(session.state, session.catalog, encounter), "Race 3, Race 7")

    def test_outgoing_empty_roster_falls_back_to_target_world_and_notice_result(self):
        session = prepared(attacking=True, empty=True)
        names(session)
        encounter = session.state["space_encounter"]
        encounter["battle"]["hostile"] = []
        target = session.state["worlds"]["1:5:1"]
        target["raw"][0] = 8
        before = deepcopy(session.state)
        self.assertEqual(space_opponents(session.state, session.catalog, encounter), "Race 8")
        self.assertIn("ATTACKING: ", space_notice(session.state, session.catalog, encounter))
        encounter["phase"] = "result"
        self.assertIn("ATTACKING: ", space_notice(session.state, session.catalog, encounter))
        self.assertEqual(before["battle_requests"], session.state["battle_requests"])

    def test_notice_and_helpers_do_not_mutate_state(self):
        session = prepared(attacking=False)
        names(session)
        before = deepcopy(session.state)
        expected_world = next(w["name"] for w in session.catalog["worlds"] if w["id"] == "1:5:0")
        self.assertEqual(world_name(session.catalog, [1, 5, 0]), expected_world)
        self.assertEqual(civilization_name(session.catalog, 3), "Race 3")
        space_notice(session.state, session.catalog, session.state["space_encounter"])
        self.assertEqual(session.state, before)


if __name__ == "__main__":
    unittest.main()
