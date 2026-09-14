"""Contact/arrival conversations, atomic hours and deferred battles."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest
from test_alien_session import ready,order
from openreunion.core import GameError
from openreunion.dos.dialogs import conversation
from openreunion.dos.navigation import arrival
from openreunion.dos.session import RecoveredSession
from openreunion.dos.strategy import navigation_view


def fixture():
    session=ready();session.catalog["dialogs"]={}
    for script,target in ((5,4),(6,2),(9,3),(10,6)):
        questions=["02 Response"]*6
        session.catalog["dialogs"][str(script)]=conversation(script,{str(script):[[1],[target]]},questions,["01 Opening","00 Terminal"])
    return session


def arriving_contact(session,race):
    order(session,race=race,mission=0)
    session.state["campaign"]["civilizations"][race-2][27]=0


class ContactDialogTests(unittest.TestCase):
    def test_player_fleet_first_contacts_open_both_original_conversations(self):
        for race,script in ((4,5),(11,10)):
            with self.subTest(race=race):
                session=fixture();row=session.state["fleets"]["moving"][0]
                row[19:23]=[1,2,0,4];row[23:29]=struct.pack("<3h",0,0,1)
                session.state["worlds"]["1:2:0"]["raw"][0]=race
                session.state["campaign"]["civilizations"][race-2][27]=0
                before=session.state["date"][:];session.apply("advance",hours=24)
                self.assertEqual(session.state["active_dialog"]["script"],script)
                self.assertEqual(session.state["date"][3],before[3]+1)
                self.assertNotIn({"kind":"scene","id":script},session.state["presentation_requests"])

    def test_two_same_hour_contacts_preserve_order_without_extra_time(self):
        session=fixture();arriving_contact(session,4);arriving_contact(session,11)
        session.apply("advance",hours=24);date=session.state["date"][:]
        self.assertEqual(session.state["active_dialog"]["script"],5)
        self.assertIn({"kind":"dialog","id":10},session.state["presentation_requests"])
        session.apply("dialog_answer",question=4);session.apply("dialog_acknowledge")
        self.assertEqual(session.state["active_dialog"]["script"],10)
        session.apply("dialog_answer",question=6);session.apply("dialog_acknowledge")
        self.assertIsNone(session.state["active_dialog"]);self.assertEqual(session.state["date"],date)
        self.assertEqual(session.state["known_systems"][7],0)
        self.assertEqual(session.state["campaign"]["flags"]["1eb"],2)

    def test_contact_choice_precedes_same_hour_defensive_battle(self):
        session=fixture();arriving_contact(session,4);order(session,race=3)
        session.apply("advance",hours=24)
        self.assertEqual(session.state["active_dialog"]["script"],5)
        self.assertIsNone(session.state["space_encounter"]);self.assertEqual(len(session.state["battle_requests"]),1)
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("advance",hours=1)
        self.assertEqual(session.state,before)
        session.apply("dialog_answer",question=4);session.apply("dialog_acknowledge")
        self.assertEqual(session.state["space_encounter"]["conquering_owner"],3)

    def test_missing_contact_definition_rolls_back_arrival_and_entire_hour(self):
        session=fixture();arriving_contact(session,4);del session.catalog["dialogs"]["5"]
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("advance",hours=24)
        self.assertEqual(session.state,before)

    def test_contact_gift_survives_open_and_terminal_saves_without_repeating(self):
        session=fixture();arriving_contact(session,4);old=session.state["products"][15]["stock"]
        session.apply("advance",hours=1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"contact.json";session.save(path);session=RecoveredSession.load(session.catalog,path)
            session.apply("dialog_answer",question=4);self.assertEqual(session.state["products"][15]["stock"],old+10)
            session.save(path);session=RecoveredSession.load(session.catalog,path)
            session.apply("dialog_acknowledge");session.apply("advance",hours=1)
        self.assertIsNone(session.state["active_dialog"])
        self.assertEqual(session.state["products"][15]["stock"],old+10)

    def test_eran_offer_requires_flag_system_colony_and_permitted_owner(self):
        for flag,system,settled,owner in ((0,4,1,6),(1,3,1,6),(1,4,0,6),(1,4,1,4),(1,4,1,6),(1,4,1,1)):
            with self.subTest(flag=flag,system=system,settled=settled,owner=owner):
                session=fixture();view=navigation_view(session.state["campaign"]);view["navigation"]["flags"]["5d95"]=flag
                row=[0]*161;row[0]=2;row[19:23]=[system,1,0,2]
                raw=[0]*65;raw[0]=owner;raw[6]=settled
                view["alien_status"]=[6]*11
                _,events=arrival(row,view,session.state["products"],[1]*8,{f"{system}:1:0":{"raw":raw}})
                expected=bool(flag and system==4 and settled and owner in (1,6))
                self.assertEqual(("dialog",9) in events,expected)
                self.assertEqual(view["navigation"]["flags"]["5d95"],0 if expected else flag)


if __name__=="__main__":unittest.main()
