"""Story chronology, prerequisites, atomic changes and campaign consequences."""
from copy import deepcopy
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.dos.aliens import fleet_at, store_fleet
from openreunion.dos.campaign import campaign_counters_tick
from openreunion.dos.story import FLAGS, TIMERS, count_observatories, story_hour


RULES = {key: [0]*8 for key in ("morgrul_base", "morgrul_early_base", "morgrul_spread")}


def state_fixture():
    state = {
        "rng": 1994, "flags": {f"{at:x}": 0 for at in FLAGS}, "timers": {f"{at:x}": 0 for at in TIMERS},
        "encounter": [3, 6, 2], "idea_timers": [-1]*35,
        "products": [{"research_state": 0, "research_remaining": 100} for _ in range(35)],
        "training_remaining": 0, "training_role": 0, "training_phase": 1,
        "developer_rank": 1, "developer_level": 10, "system_observatories": [0]*8,
        "known_systems": [1, 0, 255, 255, 255, 255, 255, 255], "civilizations": [[0]*228 for _ in range(11)],
        "worlds": {key: {"raw": [0]*65} for key in ("1:5:0", "1:7:0", "1:7:1", "2:5:0", "4:1:0")},
        "buildings": [], "fleets": {"moving": [], "local": []},
    }
    for civilization in state["civilizations"]:
        civilization[16] = 50; civilization[27] = 4
        for slot in range(1, 8):
            row = [0]*27;row[8:11] = [2, 3, 0];store_fleet(civilization, slot, row)
    return state


class StoryTests(unittest.TestCase):
    def test_forced_reinforcement_becomes_counted_without_activating_future_slots(self):
        for race,slot,count in ((7,5,4),(7,6,5),(7,7,6),(12,3,2),(12,4,3),(12,5,4)):
            with self.subTest(race=race,slot=slot):
                state=state_fixture();state['encounter']=[race,slot,2];state['timers']['5d40']=1
                civ=state['civilizations'][race-2];civ[27]=2;civ[38]=count
                before=deepcopy(state);result,_=story_hour(state,RULES)
                self.assertEqual(state,before)
                self.assertEqual(result['civilizations'][race-2][38],slot)
                self.assertEqual(fleet_at(result['civilizations'][race-2],slot)[2],2)
                for future in range(slot+1,8):
                    self.assertEqual(fleet_at(result['civilizations'][race-2],future),fleet_at(civ,future))

    def test_reinforcement_count_preserves_allies_dormancy_and_larger_counts(self):
        for relation,timer,count,expected in ((6,1,4,4),(255,1,4,4),(2,2,4,4),(2,1,7,7)):
            state=state_fixture();state['encounter']=[7,5,2];state['timers']['5d40']=timer
            civ=state['civilizations'][5];civ[27]=relation;civ[38]=count
            result,_=story_hour(state,RULES)
            self.assertEqual(result['civilizations'][5][38],expected)
            if relation!=2 or timer!=1:
                self.assertEqual(fleet_at(result['civilizations'][5],5),fleet_at(civ,5))

    def test_visiting_scientist_waits_for_contact_hiring_and_active_training(self):
        for change in ("unknown", "destroyed", "unhired", "training"):
            state = state_fixture();state["timers"]["5d4e"] = 1
            if change == "unknown":state["civilizations"][0][27] = 0
            if change == "destroyed":state["civilizations"][0][27] = 255
            if change == "unhired":state["developer_rank"] = 0
            if change == "training":state.update(training_role=4, training_remaining=1)
            result, events = story_hour(state, RULES)
            self.assertEqual(result["timers"]["5d4e"], 1);self.assertEqual(events, [])
        state = state_fixture();state["timers"]["5d4e"] = 1;state["products"][7]["research_state"] = 5
        state["training_role"] = 4  # no remaining training: scientist may leave
        result, events = story_hour(state, RULES)
        self.assertEqual(events, [("dialog", 2)]);self.assertEqual(result["flags"]["5d50"], 0)

    def test_return_completes_only_locked_invention_without_developer_gate(self):
        for research_state in range(6):
            state = state_fixture();state["timers"]["5d52"] = 1
            state["developer_level"] = state["developer_rank"] = 0
            state["products"][8]["research_state"] = research_state
            result, events = story_hour(state, RULES)
            self.assertEqual(events, [("message", 8)])
            self.assertEqual(result["products"][8], {"research_state": research_state or 5,
                                                    "research_remaining": 100 if research_state else 0})
            partial = {"carrier_failure_reported": True, "carrier_failure_remaining": 0, "research_block_remaining": 1}
            products = deepcopy(state["products"])
            self.assertEqual(campaign_counters_tick(partial, products), [8])
            self.assertEqual(products, result["products"])
        from test_campaign import session_fixture
        from openreunion.dos.session import RecoveredSession
        session = session_fixture()
        session.state["campaign"]["research_block_remaining"] = 1
        session.state["products"][8].update(research_state=0, research_remaining=100)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"scientist.json";session.save(path)
            resumed = RecoveredSession.load(session.catalog, path)
            for client in (session, resumed):client.apply("advance", hours=1)
            self.assertEqual(session.state, resumed.state)
            self.assertEqual(session.state["products"][8]["research_state"], 5)
            self.assertEqual(session.state["products"][8]["research_remaining"], 0)

    def test_warning_overwrites_old_conquest_timer_before_it_can_expire(self):
        state = state_fixture();state["timers"].update({"5d58": 1, "5d5c": 1})
        state["products"][7]["research_state"] = 5
        result, events = story_hour(state, RULES)
        self.assertEqual(events, [("message", 10), ("dialog", 4)])
        self.assertTrue(199 <= result["timers"]["5d5c"] <= 248)
        self.assertEqual(result["flags"]["5d5e"], 0)
        self.assertEqual(fleet_at(result["civilizations"][1], 1)[8:11], [1, 7, 0])

    def test_conquest_changes_phase_and_advances_new_timers_in_same_hour(self):
        state = state_fixture();state["timers"]["5d5c"] = 1;state["products"][13]["research_state"] = 3
        state["worlds"]["1:7:0"]["raw"][0] = state["worlds"]["1:7:1"]["raw"][0] = 2
        state["civilizations"][0][38] = 1
        result, events = story_hour(state, RULES)
        self.assertEqual(events, [("message", 11), ("scene", 1)])
        self.assertEqual(result["civilizations"][0][27], 255);self.assertEqual(result["training_phase"], 2)
        self.assertEqual(result["worlds"]["1:7:0"]["raw"][0], 3)
        self.assertEqual(result["worlds"]["1:7:1"]["raw"][0], 0)
        self.assertTrue(599 <= result["timers"]["5d64"] <= 648)
        self.assertTrue(299 <= result["timers"]["5d60"] <= 348)
        self.assertTrue(1799 <= result["timers"]["5d6a"] <= 1998)
        self.assertEqual(fleet_at(result["civilizations"][0], 1), [0]*27)
        self.assertEqual(fleet_at(result["civilizations"][0], 7), fleet_at(state["civilizations"][0], 7))

    def test_hyperspace_requires_invention_experience_and_clear_training_role(self):
        for change in ("locked", "unskilled", "absent", "training_role"):
            state = state_fixture();state["timers"]["5d60"] = 1;state["products"][13]["research_state"] = 3
            if change == "locked":state["products"][13]["research_state"] = 0
            if change == "unskilled":state["developer_level"] = 0
            if change == "absent":state["timers"]["5d52"] = 2
            if change == "training_role":state["training_role"] = 4
            result, events = story_hour(state, RULES)
            self.assertEqual(result["timers"]["5d60"], 1);self.assertNotIn(("message", 30), events)
        state = state_fixture();state["timers"].update({"5d60": 1, "5d52": 1});state["products"][13]["research_state"] = 3
        result, events = story_hour(state, RULES)
        self.assertEqual(events, [("message", 8), ("message", 30)])
        self.assertEqual(result["flags"]["5d62"], 1)

    def test_all_encounter_followups_wait_and_use_stable_dormant_slots(self):
        for race, slot, next_race, next_slot in ((3, 6, 3, 7), (7, 6, 7, 7), (7, 5, 7, 6),
                                               (8, 1, 7, 5), (12, 4, 12, 5), (12, 3, 12, 4)):
            state = state_fixture();state["encounter"] = [race, slot, 99];state["timers"]["5d40"] = 1
            state["civilizations"][race-2][27] = 2
            result, events = story_hour(state, RULES)
            self.assertEqual(result["encounter"], [next_race, next_slot, 2])
            self.assertGreaterEqual(result["timers"]["5d40"], 1000)
            ordered = fleet_at(result["civilizations"][race-2], slot)
            self.assertEqual(ordered[8:11], [1, 5, 0]);self.assertEqual((ordered[0], ordered[7]), (2, 2))
            self.assertEqual(result["civilizations"][race-2][38], slot);self.assertEqual(events, [])
        state["civilizations"][race-2][27] = 4
        result, _ = story_hour(state, RULES)
        self.assertEqual(fleet_at(result["civilizations"][race-2], slot), fleet_at(state["civilizations"][race-2], slot))
        self.assertEqual(result["encounter"], [next_race, next_slot, 2])

    def test_observatory_count_needs_completion_but_not_power(self):
        buildings = []
        for kind, system, construction in ((6, 4, 0), (6, 4, 1), (6, 1, 0), (1, 4, 0), (6, 4, 0)):
            row = [0]*14;row[0:2] = [kind, system];row[6] = construction;buildings.append(row)
        self.assertEqual(count_observatories(buildings), [1, 0, 0, 2, 0, 0, 0, 0])
        state = state_fixture();state["timers"]["5d92"] = 1
        self.assertEqual(story_hour(state, RULES)[0]["timers"]["5d92"], 1)
        state["system_observatories"] = count_observatories(buildings)
        result, events = story_hour(state, RULES)
        self.assertEqual(events, [("message", 25)])
        self.assertTrue(999 <= result["timers"]["5d8e"] <= 1098)
        self.assertEqual(result["flags"]["5d95"], 1)

    def test_catastrophe_preserves_other_fleets_and_does_not_mutate_input(self):
        state = state_fixture();state["timers"]["5d8e"] = 1;state["timers"]["5d92"] = 200
        state["worlds"]["4:1:0"]["raw"][0] = 1
        for system, status in ((4, 1), (1, 1), (4, 2), (2, 2), (4, 6)):
            row = [0]*161;row[0] = 2;row[19:23] = [system, 1, 0, status];state["fleets"]["moving"].append(row)
        before = deepcopy(state);result, events = story_hour(state, RULES)
        self.assertEqual(state, before);self.assertEqual(events, [("message", 27), ("scene", 7)])
        self.assertEqual(result["worlds"]["4:1:0"]["raw"][0], 0)
        self.assertEqual(result["timers"]["5d92"], 0)
        self.assertEqual(len(result["fleets"]["moving"]), 3)
        self.assertEqual(result["fleets"]["moving"][-1][19:23], [1, 5, 0, 6])

    def test_multiple_requests_preserve_order_without_automatically_accepting(self):
        state = state_fixture();state["products"][7]["research_state"] = 5
        state["timers"].update({"5d4e": 1, "5d54": 1, "5d58": 1, "5d82": 1})
        result, events = story_hour(state, RULES)
        self.assertEqual(events, [("dialog", 2), ("message", 9), ("dialog", 3),
                                  ("message", 10), ("dialog", 4), ("dialog", 7)])
        self.assertEqual(result["flags"]["5d50"], 0);self.assertEqual(result["timers"]["5d52"], 0)

    def test_completed_flags_do_not_repeat_or_consume_random_numbers(self):
        state = state_fixture();state["flags"].update({key: 1 for key in state["flags"]})
        state["timers"].update({key: 1 for key in state["timers"]})
        for key in ("5d40", "5d52", "5d8a"):state["timers"][key] = 0
        result, events = story_hour(state, RULES)
        self.assertEqual(result, state);self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
