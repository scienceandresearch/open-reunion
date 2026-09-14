"""Campaign transition regressions using original-free, synthetic world records."""
from copy import deepcopy
import struct
from pathlib import Path
import tempfile
import unittest

from test_recovered import fixture
from openreunion.core import GameError
from openreunion.legacy import SAVE_SIZE
from openreunion.dos.campaign import discovery_tick, schedule_idea, survey_step
from openreunion.dos.savefile import LAYOUT, SaveBlocks
from openreunion.dos.session import RecoveredSession


def session_fixture():
    catalog,state=fixture()
    catalog["worlds"]=[{"id":f"1:{planet}:{moon}","system":1,"planet":planet,"moon":moon,"name":name}
                       for planet,moon,name in ((5,0,"Home"),(5,1,"Moon"),(2,0,"Remote"))]
    for world in catalog["worlds"]:
        state["worlds"][world["id"]]={"raw":[0]*65}
    home=state["worlds"]["1:5:0"]["raw"]
    home[0]=home[6]=1
    home[13:17]=struct.pack("<I",10000)
    home[17:21]=[20,3,50,255]
    state["worlds"]["1:5:1"]["raw"][3]=1
    state["products"][2]["stock"]=3
    for index in (3,4,5):
        state["products"][index].update(research_state=0,research_remaining=10000)
    state["levels"]["developer"]=40
    state["skills"]={key:4 for key in state["skills"]}
    return RecoveredSession(catalog,state)


class SaveBlockTests(unittest.TestCase):
    def test_serializer_covers_every_byte_without_gaps(self):
        end=0
        self.assertEqual(len(LAYOUT["blocks"]),136)
        for block in LAYOUT["blocks"]:
            self.assertEqual(block["save_offset"],end)
            self.assertGreater(block["length"],0)
            end+=block["length"]
        self.assertEqual(end,SAVE_SIZE)
        blocks=SaveBlocks(b"\x04Test"+bytes(SAVE_SIZE-5))
        self.assertEqual(blocks.offset(0x91A0,70),0xA223)
        self.assertEqual(blocks.offset(0xA2C0,2),0x3952)
        self.assertEqual(len(blocks.read(0xA2BC,14000,pointer=True)),14000)

    def test_read_rejects_negative_and_cross_block_ranges(self):
        blocks=SaveBlocks(b"\x04Test"+bytes(SAVE_SIZE-5))
        for address,length in ((0x91A0,-1),(0x91A0,0),(0x91A0,71),(True,1),(65536,1)):
            with self.assertRaises(GameError):
                blocks.read(address,length)
            with self.assertRaises(GameError):
                blocks.offset(address,length)
        with self.assertRaises(GameError):
            blocks.read(0xA2BD,1,pointer=True)


class CampaignTests(unittest.TestCase):
    def test_scheduling_does_not_reroll_pending_or_known_projects(self):
        session=session_fixture()
        campaign,products=session.state["campaign"],session.state["products"]
        schedule_idea(campaign,products,4,10,10)
        before=deepcopy(campaign)
        schedule_idea(campaign,products,4,500,100)
        schedule_idea(campaign,products,1,500,100)
        self.assertEqual(campaign,before)

    def test_trade_gate_and_training_pause_discoveries(self):
        session=session_fixture()
        campaign,products=session.state["campaign"],session.state["products"]
        campaign["idea_timers"][14]=1
        products[8]["research_state"]=1
        discovered,_=discovery_tick(campaign,products,40)
        self.assertNotIn(15,discovered)
        self.assertEqual(campaign["idea_timers"][14],10)
        campaign.update(training_role=4,training_remaining=1)
        before=deepcopy(campaign)
        discovery_tick(campaign,products,40)
        self.assertEqual(campaign,before)
        campaign.update(training_role=0,training_remaining=0)
        products[8]["research_state"]=5
        for _ in range(10):
            discovered,_=discovery_tick(campaign,products,40)
        self.assertIn(15,discovered)

    def test_satellite_launch_is_atomic_and_rejects_existing_support(self):
        session=session_fixture()
        for world_id in ("1:5:0","8:1:0"):
            before=deepcopy(session.state)
            with self.assertRaises(GameError):
                session.apply("launch_satellite",world_id=world_id)
            self.assertEqual(session.state,before)
        session.apply("launch_satellite",world_id="1:5:1")
        self.assertEqual(session.state["products"][2]["stock"],2)
        self.assertEqual(session.state["worlds"]["1:5:1"]["raw"][8],1)
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("launch_satellite",world_id="1:5:1")
        self.assertEqual(session.state,before)

    def test_remote_failure_unlocks_carrier_and_prevents_another_direct_launch(self):
        session=session_fixture()
        session.apply("launch_satellite",world_id="1:2:0")
        self.assertEqual(session.state["worlds"]["1:2:0"]["raw"][8],226)
        for _ in range(40):
            session.apply('advance',hours=1)
            if session.state['active_scene'] is not None:
                self.assertEqual(session.state['active_scene']['playback']['scene'],9)
                session.apply('scene_acknowledge')
                while session.state['active_scene']['playback']['phase']!='done':session.apply('scene_tick')
                session.apply('scene_acknowledge')
        self.assertTrue(session.state["campaign"]["carrier_failure_reported"])
        self.assertEqual(session.state["products"][3]["research_state"],1)
        self.assertIn(("message",1),[(e["kind"],e["id"]) for e in session.state["events"]])
        session.apply("advance",hours=72)
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("launch_satellite",world_id="1:2:0")
        self.assertEqual(session.state,before)

    def test_survey_discovery_research_transfer_chain_survives_save_load(self):
        session=session_fixture()
        session.apply("launch_satellite",world_id="1:5:1")
        session.apply("advance",hours=240)
        self.assertEqual(session.state["products"][4]["research_state"],1)
        session.apply("research",product_id=5)
        session.apply("advance",hours=5)
        self.assertEqual(session.state["products"][4]["research_state"],5)
        self.assertIn(("message",3),[(e["kind"],e["id"]) for e in session.state["events"]])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"session.json"
            session.save(path)
            loaded=RecoveredSession.load(session.catalog,path)
            loaded.apply("advance",hours=40)
            session.apply("advance",hours=40)
            self.assertEqual(loaded.state,session.state)
        self.assertEqual(session.state["products"][5]["research_state"],1)
        session.apply("research",product_id=6)
        session.apply("advance",hours=5)
        self.assertEqual(session.state["campaign"]["capabilities"]["transfer"],1)
        self.assertEqual(session.state["campaign"]["capabilities"]["transport"],1)

    def test_survey_uses_midnight_and_original_random_call_order(self):
        session=session_fixture()
        session.state["worlds"]["1:5:0"]["raw"][6]=0
        session.catalog["worlds"]=session.catalog["worlds"][1:]
        del session.state["worlds"]["1:5:0"]
        session.apply("launch_satellite",world_id="1:5:1")
        session.state["date"][3]=22
        before=deepcopy(session.state["worlds"])
        session.apply("advance",hours=1)
        self.assertEqual(session.state["worlds"],before)
        moon,seed,_=survey_step(before["1:5:1"]["raw"],1994)
        session.apply("advance",hours=1)
        self.assertEqual(session.state["campaign"]["rng"],seed)
        self.assertEqual(session.state["worlds"]["1:5:1"]["raw"],moon)

    def test_hiring_uses_saved_candidate_training(self):
        session=session_fixture()
        session.state["campaign"]["commander_levels"][9]=37
        session.state["campaign"]["developer_skill_choices"][:4]=[8,9,10,11]
        session.apply("hire",role="developer",rank=1)
        self.assertEqual(session.state["levels"]["developer"],37)
        self.assertEqual(list(session.state["skills"].values()),[8,9,10,11])

    def test_invalid_nested_campaign_state_cannot_load(self):
        session=session_fixture()
        for mutate in (lambda s:s["campaign"].update(rng=True),lambda s:s["worlds"]["1:5:1"]["raw"].pop(),
                       lambda s:s["campaign"]["idea_timers"].pop(),lambda s:s["campaign"].update(training_role=5)):
            bad=deepcopy(session.state)
            mutate(bad)
            with self.assertRaises(GameError):
                RecoveredSession(session.catalog,bad)
