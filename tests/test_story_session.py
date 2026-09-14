"""Campaign story order, choice transactions and saved conversations."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from test_alien_session import ready,order
from test_colony import building
from openreunion.core import GameError
from openreunion.dos.aliens import fleet_at
from openreunion.dos.dialogs import conversation,start_conversation,validate_definition
from openreunion.dos.session import RecoveredSession,SCHEMA


def scripted():
    session=ready();session.catalog["dialogs"]={}
    for script,choices in ((2,[4,5]),(3,[6,5]),(4,[4,5]),(7,[9,5])):
        questions=["01 Ask"]*9
        for question in choices:questions[question-1]="02 Choose"
        definition=conversation(script,{str(script):[[1],choices]},questions,["01 Opening","00 Final answer"])
        validate_definition(definition);session.catalog["dialogs"][str(script)]=definition
    session.state["campaign"]["civilizations"][0][27]=4
    session.state["levels"]["developer"]=10;session.state["ranks"]["developer"]=1
    session.state["products"][7]["research_state"]=5
    return session


def acknowledge_notices(session):
    while session.state['active_dialog'] is None and session.state['presentation_requests'] and session.state['presentation_requests'][0]['kind']=='message':
        session.apply('dismiss_presentation')


class StorySessionTests(unittest.TestCase):
    def test_hour_completes_before_choice_and_scientist_counter_ticks_once(self):
        session=scripted();session.state["campaign"]["timers"]["5d4e"]=1
        session.state["products"][0]["queued"]=2
        old=deepcopy(session.state);session.apply("advance",hours=24)
        self.assertEqual(session.state["date"][3],old["date"][3]+1)
        self.assertEqual(session.state["products"][0]["stock"],old["products"][0]["stock"]+1)
        self.assertEqual(session.state["active_dialog"]["script"],2)
        date=list(session.state["date"])
        session.apply("dialog_answer",question=4)
        duration=session.state["campaign"]["research_block_remaining"]
        self.assertTrue(60<=duration<90);self.assertEqual(session.state["date"],date)
        with self.assertRaises(GameError):session.apply("advance",hours=1)
        session.apply("dialog_acknowledge");session.apply("advance",hours=1)
        self.assertEqual(session.state["campaign"]["research_block_remaining"],duration-1)

    def test_saved_final_answer_does_not_repeat_reward(self):
        session=scripted();session.state["campaign"]["timers"]["5d58"]=1
        session.state["products"][9]["research_state"]=0;session.state["products"][10]["research_state"]=0
        session.apply("advance",hours=1)
        acknowledge_notices(session)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"story.json";session.save(path);resumed=RecoveredSession.load(session.catalog,path)
            for current in (session,resumed):current.apply("dialog_answer",question=4)
            self.assertEqual(session.state,resumed.state)
            self.assertEqual(session.state["products"][9]["research_state"],5)
            self.assertEqual(session.state["products"][10]["research_state"],5)
            session.save(path);resumed=RecoveredSession.load(session.catalog,path)
            for current in (session,resumed):current.apply("dialog_acknowledge")
            self.assertEqual(session.state,resumed.state)
            before=deepcopy(session.state)
            with self.assertRaises(GameError):session.apply("dialog_acknowledge")
            self.assertEqual(before,session.state)

    def test_failed_bargain_preserves_answer_and_can_be_funded_by_admin(self):
        session=scripted();session.state["campaign"]["timers"]["5d54"]=1
        session.state["resources"]["credits"]=15999;session.apply("advance",hours=1);acknowledge_notices(session)
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("dialog_answer",question=6)
        self.assertEqual(before,session.state)
        session.admin_enabled=True;session.apply("admin",command="give credits 1")
        session.apply("dialog_answer",question=6)
        self.assertEqual(session.state["resources"]["credits"],0)

    def test_simultaneous_dialogs_finish_before_queued_defense(self):
        session=scripted();order(session)
        session.state["campaign"]["timers"].update({"5d4e":1,"5d54":1})
        session.apply("advance",hours=24)
        self.assertEqual(session.state["active_dialog"]["script"],2)
        self.assertIsNone(session.state["space_encounter"]);self.assertEqual(len(session.state["battle_requests"]),1)
        session.apply("dialog_answer",question=5);session.apply("dialog_acknowledge")
        acknowledge_notices(session)
        self.assertEqual(session.state["active_dialog"]["script"],3)
        session.apply("dialog_answer",question=5);session.apply("dialog_acknowledge")
        self.assertIsNone(session.state["active_dialog"])
        self.assertEqual(session.state["space_encounter"]["destination"],[1,5,0])
        self.assertEqual(session.state["date"][3],9)

    def test_observatory_story_uses_previous_building_pass(self):
        session=scripted();definition=deepcopy(session.catalog["worlds"][0])
        definition.update(id="4:1:0",system=4,planet=1,moon=0);session.catalog["worlds"].append(definition)
        session.state["worlds"]["4:1:0"]={"raw":[0]*65}
        row=building(6);row[1:4]=[4,1,0];row[8]=0;session.state["buildings"].append(row)
        session.state["campaign"]["timers"]["5d92"]=1
        session.apply("advance",hours=1)
        self.assertEqual(session.state["campaign"]["timers"]["5d92"],1)
        self.assertEqual(session.state["campaign"]["system_observatories"][3],1)
        session.apply("advance",hours=1)
        self.assertEqual(session.state["campaign"]["flags"]["5d94"],1)
        self.assertTrue(any(e["kind"]=="message" and e["id"]==25 for e in session.state["events"]))

    def test_unoffered_or_repeated_response_is_atomic(self):
        session=scripted();session.state["campaign"]["timers"]["5d4e"]=1;session.apply("advance",hours=1)
        before=deepcopy(session.state)
        for question in (1,True,0,100):
            with self.assertRaises(GameError):session.apply("dialog_answer",question=question)
            self.assertEqual(before,session.state)
        session.apply("dialog_answer",question=4);before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("dialog_answer",question=4)
        self.assertEqual(before,session.state)

    def test_v12_migrates_observatory_cache_and_rejects_smuggled_dialog(self):
        session=scripted();state=deepcopy(session.state);state["schema"]="recovered-strategy-v12";del state['active_scene']
        del state["active_dialog"];del state["campaign"]["system_observatories"];del state["campaign"]["bar"]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"v12.json";path.write_text(json.dumps(state),encoding="utf-8")
            loaded=RecoveredSession.load(session.catalog,path)
            self.assertEqual(loaded.state,session.state);self.assertEqual(loaded.state["schema"],SCHEMA)
            state["active_dialog"]=None;path.write_text(json.dumps(state),encoding="utf-8")
            with self.assertRaises(GameError):RecoveredSession.load(session.catalog,path)

    def test_missing_dialog_content_rolls_back_hour(self):
        session=scripted();session.state["campaign"]["timers"]["5d4e"]=1;del session.catalog["dialogs"]
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply("advance",hours=24)
        self.assertEqual(before,session.state)

    def test_closing_notice_waits_for_final_answer_acknowledgment(self):
        session=scripted();definition=deepcopy(session.catalog["dialogs"]["4"]);definition["id"]=6
        session.catalog["dialogs"]["6"]=definition
        session.state["presentation_requests"].append({"kind":"dialog","id":6})
        session.apply("advance",hours=1)
        self.assertEqual(session.state['active_scene']['playback']['scene'],10)
        while session.state['active_scene']['playback']['phase']!='done':session.apply('scene_tick')
        session.apply('scene_acknowledge');session.apply("dialog_answer",question=5)
        notices=lambda:sum(e["kind"]=="message" and e["id"]==48 for e in session.state["events"])
        self.assertEqual(notices(),0)
        session.apply("dialog_acknowledge");self.assertEqual(notices(),1)
        with self.assertRaises(GameError):session.apply("dialog_acknowledge")
        self.assertEqual(notices(),1)

    def test_saved_prisoner_refusal_preserves_attack_and_closes_once(self):
        session=scripted()
        # Original-free session fixture for the actual script-6 refusal IDs
        # [2, 4, 6]. Original graph parity remains covered by verify_dialogs.
        definition=conversation(6,{"6":[[1],[2],[4],[6]]},
            ["01 Unused","03 Ask plans","","04 Send warning","","05 Refuse release"],
            ["01 Opening","00 Released","02 Plans","03 Warning","00 Refused"])
        validate_definition(definition);session.catalog["dialogs"]["6"]=definition
        campaign=session.state["campaign"];campaign["flags"]["5d3f"]=0
        campaign["timers"]["5d7a"]=777
        order(session,race=4,slot=2,world=(2,5,0),mission=2,travel=1,delay=50)
        campaign=session.state["campaign"]
        before=deepcopy(campaign)
        session.state["active_dialog"]=start_conversation(definition)
        for question in (2,4,6):session.apply("dialog_answer",question=question)
        self.assertTrue(session.state["active_dialog"]["closed"])
        self.assertEqual(session.state["campaign"],before)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"prisoner-refusal.json";session.save(path)
            resumed=RecoveredSession.load(session.catalog,path)
            self.assertEqual(resumed.state,session.state)
            for current in (session,resumed):
                self.assertFalse(any(e["kind"]=="message" and e["id"]==48 for e in current.state["events"]))
                current.apply("dialog_acknowledge")
                self.assertIsNone(current.state["active_dialog"])
                self.assertEqual(sum(e["kind"]=="message" and e["id"]==48 for e in current.state["events"]),1)
                self.assertEqual(current.state["campaign"]["flags"]["5d3f"],0)
                self.assertEqual(current.state["campaign"]["timers"]["5d7a"],777)
                civilization=current.state["campaign"]["civilizations"][2]
                self.assertEqual(fleet_at(civilization,2)[8:11],[2,5,0])
                rejected=deepcopy(current.state)
                with self.assertRaises(GameError):current.apply("dialog_acknowledge")
                self.assertEqual(current.state,rejected)
            self.assertEqual(resumed.state,session.state)
