"""Alien arrival/action chronology and original battle-request regressions."""
from copy import deepcopy
import struct
import unittest

from test_story import state_fixture
from openreunion.core import GameError
from openreunion.dos.aliens import fleet_at, store_fleet
from openreunion.dos.alien_movement import alien_hour


def group(state, race=3, slot=1, *, status=1, travel=1, delay=1, mission=2, world=(1, 5, 0), counted=True):
    civilization = state["civilizations"][race-2]
    if counted:civilization[38] = max(civilization[38], slot)
    row = [0]*27;row[2] = status;row[3:7] = struct.pack("<2h", travel, delay)
    row[7] = mission;row[8:11] = world;store_fleet(civilization, slot, row)


def player(state, *, bank="moving", kind=1, status=1, world=(1, 5, 0)):
    row = [0]*161;row[0] = kind;row[19:23] = [*world, status];state["fleets"][bank].append(row)


class AlienMovementTests(unittest.TestCase):
    def test_arrival_and_action_can_happen_in_the_same_hour(self):
        state = state_fixture();state["worlds"]["1:5:0"]["raw"][0] = 1
        group(state, status=2, travel=2)
        first, events = alien_hour(state)
        self.assertEqual(events, []);self.assertEqual(fleet_at(first["civilizations"][1], 1)[5], 1)
        second, events = alien_hour(first)
        self.assertEqual(events, [("battle", {"race": 3, "slot": 1, "world": [1, 5, 0], "ground": True, "special": False})])
        self.assertEqual(fleet_at(second["civilizations"][1], 1)[2:8], [1, 0, 0, 0, 0, 0])
        self.assertEqual(alien_hour(second)[1], [])

    def test_inactive_and_uncounted_slots_are_preserved(self):
        state = state_fixture();group(state, status=0)
        group(state, slot=7, status=2, counted=False)
        before = deepcopy(state);result, events = alien_hour(state)
        self.assertEqual(result, before);self.assertEqual(state, before);self.assertEqual(events, [])

    def test_contact_is_once_but_later_matching_group_can_raise_hostile_warning(self):
        state = state_fixture();state["civilizations"][1][27] = 0
        group(state, status=2, mission=0);player(state, bank="local");player(state, kind=2)
        result, events = alien_hour(state)
        self.assertEqual(events, [("contact", {"race": 3, "world": [1, 5, 0], "source": "local"}),
                                  ("message", 5), ("hostile_arrival", {"race": 3, "world": [1, 5, 0]})])
        self.assertEqual(result["civilizations"][1][27], 2)
        self.assertEqual(state["civilizations"][1][27], 0)

    def test_carriers_and_in_transit_groups_do_not_make_arrival_contact(self):
        for kind, status in ((4, 1), (4, 2), (1, 4), (2, 5), (3, 6)):
            state = state_fixture();state["civilizations"][1][27] = 0
            group(state, status=2, mission=0);player(state, kind=kind, status=status)
            result, events = alien_hour(state)
            self.assertEqual(events, []);self.assertEqual(result["civilizations"][1][27], 0)
        player(state, kind=2, status=2)
        result, events = alien_hour(state)
        self.assertEqual(events[0][1]["source"], "fleet");self.assertEqual(result["civilizations"][1][27], 2)

    def test_each_race_finishes_actions_before_the_next_race_travels(self):
        state = state_fixture();state["worlds"]["1:5:0"]["raw"][0] = 1
        group(state, race=2);group(state, race=3, status=2, mission=0)
        state["civilizations"][1][27] = 0;player(state, bank="local")
        _, events = alien_hour(state)
        self.assertEqual([kind for kind, _ in events], ["battle", "contact", "message"])
        self.assertEqual(events[0][1]["race"], 2);self.assertEqual(events[1][1]["race"], 3)

    def test_ground_and_special_modes_match_mission_and_owner(self):
        for mission in (1, 2, 3, 4):
            for owner in (0, 1, 3):
                state = state_fixture();state["worlds"]["1:5:0"]["raw"][0] = owner
                group(state, mission=mission)
                result, events = alien_hour(state)
                if mission in (2, 4) and owner == 1:
                    self.assertEqual(events[0][1]["ground"], True)
                    self.assertEqual(events[0][1]["special"], mission == 4)
                else:self.assertEqual(events, [])
                self.assertEqual(fleet_at(result["civilizations"][1], 1)[7], 0)

    def test_space_defense_covers_moons_but_not_inbound_or_unarmed_group_types(self):
        for kind, status, expected in ((1, 1, True), (3, 2, True), (2, 1, False),
                                       (4, 1, False), (1, 6, False), (3, 4, False)):
            state = state_fixture();group(state, mission=3)
            player(state, kind=kind, status=status, world=(1, 5, 1))
            _, events = alien_hour(state)
            self.assertEqual(bool(events), expected)
            if expected:
                self.assertFalse(events[0][1]["ground"]);self.assertTrue(events[0][1]["special"])
        state = state_fixture();group(state, mission=1);player(state, world=(1, 7, 0))
        self.assertEqual(alien_hour(state)[1], [])

    def test_later_actions_cannot_overwrite_pending_battle_identity(self):
        state = state_fixture()
        for identity in ("1:5:0", "1:7:0"):state["worlds"][identity]["raw"][0] = 1
        group(state, race=3);group(state, race=7, world=(1, 7, 0))
        group(state, race=12, mission=1, world=(2, 5, 0))
        before = deepcopy(state);result, events = alien_hour(state)
        self.assertEqual([(e[1]["race"], e[1]["world"]) for e in events], [(3, [1, 5, 0]), (7, [1, 7, 0])])
        self.assertEqual(state, before)
        events[0][1]["world"][0] = 8
        self.assertEqual(fleet_at(result["civilizations"][1], 1)[8:11], [1, 5, 0])

    def test_expired_timers_do_not_wrap_or_stall_for_thousands_of_hours(self):
        for timer in (0, -1, -32768):
            state = state_fixture();state["worlds"]["1:5:0"]["raw"][0] = 1
            group(state, status=2, travel=timer, delay=timer)
            result, events = alien_hour(state)
            self.assertEqual(len(events), 1);self.assertEqual(events[0][0], "battle")
            self.assertEqual(fleet_at(result["civilizations"][1], 1)[2:8], [1, 0, 0, 0, 0, 0])

    def test_invalid_action_rejects_the_whole_pass_without_partial_changes(self):
        for invalid in ("mission", "world"):
            state = state_fixture();group(state, status=2, mission=0)
            group(state, slot=2, mission=5 if invalid == "mission" else 2,
                  world=(1, 5, 0) if invalid == "mission" else (8, 8, 8))
            before = deepcopy(state)
            with self.assertRaises(GameError):alien_hour(state)
            self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
