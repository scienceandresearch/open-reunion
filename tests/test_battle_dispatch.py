"""Player attacks preserve strategic eligibility and atomic battle startup."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from test_space_session import prepared, finish_space
from test_strategy_session import finish as finish_ground
from openreunion.core import GameError
from openreunion.dos.aliens import store_fleet
from openreunion.dos.battle_dispatch import player_attack_request
from openreunion.dos.session import RecoveredSession


def ready():
    session=prepared();session.state["space_encounter"]=None
    session.state["worlds"]["1:5:1"]["raw"][12]=40
    session.state["levels"]["fighter"]=20;session.state["ranks"]["fighter"]=2
    session.state["campaign"]["civilizations"][1][27]=4
    return session


class BattleDispatchTests(unittest.TestCase):
    def test_request_is_read_only_and_uses_army_world(self):
        session=ready();before=deepcopy(session.state)
        self.assertEqual(player_attack_request(session.state,0),
            {"destination":[1,5,1],"hostile_race":3,"ground_requested":True})
        self.assertEqual(before,session.state)

    def test_assault_changes_diplomacy_before_roster_and_resumes_to_conquest(self):
        session=ready();date=deepcopy(session.state["date"])
        session.apply("attack",fleet_index=0)
        self.assertEqual(session.state["campaign"]["civilizations"][1][27],2)
        self.assertEqual(session.state["space_encounter"]["battle"]["hostile_count"],3)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"assault.json";session.save(path)
            resumed=RecoveredSession.load(session.catalog,path)
            for current in (session,resumed):
                finish_space(current);current.apply("space_acknowledge")
                self.assertEqual(current.state["ground_encounter"]["destination"],[1,5,1])
                current.apply("ground_start");finish_ground(current);current.apply("ground_acknowledge")
            self.assertEqual(session.state,resumed.state)
        self.assertEqual(session.state["worlds"]["1:5:1"]["raw"][0],1)
        self.assertEqual(session.state["date"],date)
        self.assertFalse(session.state["assisted"])

    def test_rejected_assaults_preserve_diplomacy_seed_and_state(self):
        edits=[lambda s:s["fleets"]["moving"][0].__setitem__(0,3),
               lambda s:s["levels"].__setitem__("fighter",0),
               lambda s:s["ranks"].__setitem__("fighter",1)]
        for value in (0,3,4,5,6,7):
            edits.append(lambda s,v=value:s["fleets"]["moving"][0].__setitem__(22,v))
        for value in (0,39,128,255):
            edits.append(lambda s,v=value:s["worlds"]["1:5:1"]["raw"].__setitem__(12,v))
        for value in (0,1,13,255):
            edits.append(lambda s,v=value:s["worlds"]["1:5:1"]["raw"].__setitem__(0,v))
        edits.append(lambda s:s["campaign"]["civilizations"][1].__setitem__(27,6))
        for edit in edits:
            session=ready();edit(session.state);before=deepcopy(session.state)
            with self.assertRaises(GameError):session.apply("attack",fleet_index=0)
            self.assertEqual(before,session.state)

    def test_startup_failure_rolls_back_declaration_of_war(self):
        session=ready();session.catalog["battle_rules"]["space"]["bytes"][0:]=[0]*len(session.catalog["battle_rules"]["space"]["bytes"])
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("attack",fleet_index=0)
        self.assertEqual(before,session.state)

    def test_fleet_attack_is_primary_wide_without_ground_or_rank_two_gate(self):
        session=ready();session.state["ranks"]["fighter"]=1
        civilization=session.state["campaign"]["civilizations"][2];civilization[38]=1
        alien=[0]*27;alien[0]=2;alien[2]=1;alien[8:11]=[1,5,2];alien[11]=3
        store_fleet(civilization,1,alien)
        session.apply("attack",fleet_index=0,target_race=4,target_slot=1)
        encounter=session.state["space_encounter"]
        self.assertEqual(encounter["destination"],[1,5,0]);self.assertFalse(encounter["ground_requested"])
        self.assertEqual(civilization[27],4) # original state snapshot was not mutated
        self.assertEqual(session.state["campaign"]["civilizations"][2][27],2)
        self.assertEqual(session.state["campaign"]["civilizations"][1][27],4)
        self.assertEqual(encounter["battle"]["hostile_count"],3)
        finish_space(session);session.apply("space_acknowledge")
        self.assertIsNone(session.state["ground_encounter"])
        self.assertEqual(session.state["worlds"]["1:5:1"]["raw"][0],3)

    def test_target_must_be_counted_stationary_nonallied_combat_fleet(self):
        for field,value in ((0,1),(2,2),(8,2),(9,4)):
            session=ready();civ=session.state["campaign"]["civilizations"][2];civ[38]=1
            alien=[0]*27;alien[0]=2;alien[2]=1;alien[8:11]=[1,5,0];alien[field]=value
            store_fleet(civ,1,alien);before=deepcopy(session.state)
            with self.assertRaises(GameError):session.apply("attack",fleet_index=0,target_race=4,target_slot=1)
            self.assertEqual(before,session.state)
        session=ready();before=deepcopy(session.state)
        for arguments in ({"target_race":4,"target_slot":7},{"target_race":4},{"target_slot":1},{"target_race":True,"target_slot":1}):
            with self.assertRaises(GameError):session.apply("attack",fleet_index=0,**arguments)
            self.assertEqual(before,session.state)
        civ=session.state["campaign"]["civilizations"][2];civ[38]=1;civ[27]=6
        alien=[0]*27;alien[0]=2;alien[2]=1;alien[8:11]=[1,5,0];store_fleet(civ,1,alien)
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("attack",fleet_index=0,target_race=4,target_slot=1)
        self.assertEqual(before,session.state)

    def test_second_attack_and_campaign_ticks_cannot_replace_active_battle(self):
        session=ready();session.apply("attack",fleet_index=0);before=deepcopy(session.state)
        for action,arguments in (("attack",{"fleet_index":0}),("advance",{"hours":1})):
            with self.assertRaises(GameError):session.apply(action,**arguments)
            self.assertEqual(before,session.state)
