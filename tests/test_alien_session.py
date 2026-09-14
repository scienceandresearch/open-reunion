"""Hourly alien contacts, saved attack queues and defensive consequences."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from test_space_session import prepared, finish_space
from openreunion.core import GameError
from openreunion.dos.aliens import fleet_at,store_fleet
from openreunion.dos.session import RecoveredSession,SCHEMA


def ready():
    session=prepared(attacking=False);session.state["space_encounter"]=None
    session.state["date"][3]=8
    for civ in session.state["campaign"]["civilizations"]:civ[38]=0
    for identity in ("1:5:0","1:5:1","1:2:0"):
        session.state["worlds"][identity]["raw"][0]=1
        session.state["worlds"][identity]["raw"][6]=1
    return session


def order(session,race=3,slot=1,world=(1,5,0),mission=2,travel=1,delay=1):
    civ=session.state["campaign"]["civilizations"][race-2]
    civ[27]=2;civ[17:19]=[1,7];civ[38]=max(civ[38],slot)
    row=[0]*27;row[0]=2;row[2]=2 if travel else 1
    row[3:7]=struct.pack("<2h",travel,delay);row[7]=mission;row[8:11]=list(world)
    row[11:13]=struct.pack("<H",3);row[19:21]=struct.pack("<H",20)
    store_fleet(civ,slot,row)


class AlienSessionTests(unittest.TestCase):
    def test_scheduled_dormant_reinforcement_arrives_after_save_reload(self):
        session=ready();order(session,race=7,slot=5)
        campaign=session.state['campaign'];civ=campaign['civilizations'][5];civ[38]=4
        row=fleet_at(civ,5);row[0]=row[2]=0;row[8:11]=[1,7,0];store_fleet(civ,5,row)
        campaign['navigation']['encounter']=[7,5,2];campaign['timers']['5d40']=1
        session.apply('advance',hours=1)
        self.assertEqual(session.state['campaign']['civilizations'][5][38],5)
        self.assertEqual(session.state['campaign']['navigation']['encounter'][:2],[7,6])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'reinforcement.json';session.save(path)
            resumed=RecoveredSession.load(session.catalog,path)
            for _ in range(120):
                if session.state['space_encounter'] is not None:break
                for current in (session,resumed):
                    current.apply('advance',hours=1)
                    while current.state['presentation_requests']:current.apply('dismiss_presentation')
                self.assertEqual(session.state,resumed.state)
            else:self.fail('Scheduled reinforcement never reached New Earth')
            self.assertEqual(session.state['space_encounter']['conquering_owner'],7)
            self.assertEqual(session.state['space_encounter']['destination'],[1,5,0])

    def test_same_hour_arrival_stops_fast_forward_and_preserves_other_requests(self):
        session=ready();order(session);order(session,race=7,world=(1,2,0),mission=4)
        session.apply("advance",hours=24)
        self.assertEqual(session.state["date"][3],9)
        encounter=session.state["space_encounter"]
        self.assertEqual(encounter["destination"],[1,5,0]);self.assertEqual(encounter["conquering_owner"],3)
        self.assertFalse(encounter["player_attacking"]);self.assertTrue(encounter["ground_requested"])
        self.assertEqual(session.state["battle_requests"],[{"race":7,"slot":1,"world":[1,2,0],"ground":True,"special":True}])
        self.assertEqual(fleet_at(session.state["campaign"]["civilizations"][5],1)[7],0)

    def test_queued_battles_survive_reload_and_start_in_order(self):
        session=ready();order(session);order(session,race=7,world=(1,2,0))
        session.apply("advance",hours=24)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"defense.json";session.save(path)
            resumed=RecoveredSession.load(session.catalog,path)
            for current in (session,resumed):
                finish_space(current);self.assertTrue(current.state["space_encounter"]["player_won"])
                current.apply("space_acknowledge")
                self.assertEqual(current.state["space_encounter"]["destination"],[1,2,0])
                self.assertEqual(current.state["space_encounter"]["conquering_owner"],7)
                self.assertEqual(current.state["battle_requests"],[])
            self.assertEqual(session.state,resumed.state)
            self.assertEqual(session.state["date"][3],9)

    def test_primary_wide_victory_drops_requests_from_already_withdrawn_fleets(self):
        session=ready();order(session);order(session,slot=2,world=(1,5,1))
        for slot in (1,2):
            civ=session.state["campaign"]["civilizations"][1];row=fleet_at(civ,slot)
            row[11:13]=struct.pack("<H",1);store_fleet(civ,slot,row)
        session.apply("advance",hours=1);self.assertEqual(len(session.state["battle_requests"]),1)
        finish_space(session);self.assertTrue(session.state["space_encounter"]["player_won"]);session.apply("space_acknowledge")
        self.assertEqual(session.state["space_encounter"]["phase"],"closed")
        self.assertEqual(session.state["battle_requests"],[])
        session.apply("advance",hours=1);self.assertEqual(session.state["date"][3],10)

    def test_ground_defeat_at_new_earth_ends_campaign_and_clears_later_requests(self):
        session=ready();order(session);order(session,race=7,world=(1,2,0))
        session.apply("advance",hours=24)
        session.apply("space_retreat");session.apply("space_acknowledge")
        self.assertEqual(len(session.state["battle_requests"]),1)
        self.assertEqual(session.state["ground_encounter"]["conquering_owner"],3)
        session.apply("ground_start");session.apply("ground_command",command="retreat");session.apply("ground_acknowledge")
        self.assertTrue(session.defeated());self.assertEqual(session.state["battle_requests"],[])
        with self.assertRaises(GameError):session.apply("advance",hours=1)

    def test_travelers_cannot_defend_and_expired_orders_still_resolve(self):
        session=ready();order(session,mission=1,travel=0,delay=0)
        session.state["fleets"]["moving"][0][22]=6
        session.state["fleets"]["moving"][0][23:29]=struct.pack("<3h",200,1,200)
        session.apply("advance",hours=1)
        self.assertIsNone(session.state["space_encounter"])
        self.assertEqual(fleet_at(session.state["campaign"]["civilizations"][1],1)[7],0)

    def test_invalid_alien_action_rolls_back_the_entire_hour(self):
        session=ready();order(session,mission=5,travel=0)
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("advance",hours=24)
        self.assertEqual(before,session.state)

    def test_arrival_contact_updates_rng_and_starts_dialog(self):
        session=ready();order(session,race=4,mission=0)
        from openreunion.dos.dialogs import conversation
        session.catalog["dialogs"]={"5":conversation(5,{"5":[[1],[1]]},["02 Ask"],["01 Opening","00 Answer"])}
        session.state["campaign"]["civilizations"][2][27]=0
        before=session.state["campaign"]["rng"];session.apply("advance",hours=1)
        self.assertEqual(session.state["campaign"]["civilizations"][2][27],6)
        self.assertNotEqual(session.state["campaign"]["rng"],before)
        self.assertEqual(session.state["active_dialog"]["script"],5)
        self.assertTrue(any(event["kind"]=="message" and event["id"]==15 for event in session.state["events"]))
        self.assertIsNone(session.state["space_encounter"])

    def test_v11_migration_is_lossless_but_cannot_smuggle_a_queue(self):
        session=ready();state=deepcopy(session.state);state["schema"]="recovered-strategy-v11";del state["battle_requests"];del state['active_scene']
        del state["active_dialog"];del state["campaign"]["system_observatories"];del state["campaign"]["bar"]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"old.json";path.write_text(json.dumps(state),encoding="utf-8")
            loaded=RecoveredSession.load(session.catalog,path)
            self.assertEqual(loaded.state,session.state);self.assertEqual(loaded.state["schema"],SCHEMA)
            state["battle_requests"]=[];path.write_text(json.dumps(state),encoding="utf-8")
            with self.assertRaises(GameError):RecoveredSession.load(session.catalog,path)

    def test_malformed_queues_are_rejected_without_replacing_state(self):
        session=ready();order(session);order(session,race=7,world=(1,2,0));session.apply("advance",hours=1)
        original=deepcopy(session.state)
        for edit in (lambda q:q.append(deepcopy(q[0])),lambda q:q[0].__setitem__("race",True),
                     lambda q:q[0].__setitem__("slot",8),lambda q:q[0].__setitem__("world",[9,1,0]),
                     lambda q:q[0].__setitem__("special",1),lambda q:q[0].__setitem__("unknown",0)):
            damaged=deepcopy(original);edit(damaged["battle_requests"])
            with self.assertRaises(GameError):RecoveredSession(session.catalog,damaged)
            self.assertEqual(original,session.state)
        for field in ("space_encounter","ground_encounter"):
            damaged=deepcopy(original);damaged[field]=True
            with self.assertRaises(GameError):RecoveredSession(session.catalog,damaged)
