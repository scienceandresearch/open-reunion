"""Mission boundaries, corrected rewards and campaign persistence."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from test_alien_session import ready, order
from openreunion.core import GameError
from openreunion.dos.bar import STATUS_FLAGS, agent_status, bar_hour, intelligence_reports, validate_bar
from openreunion.dos.campaign import random_bounded
from openreunion.dos.catalog import ORE_KEYS
from openreunion.dos.session import RecoveredSession, SCHEMA
from openreunion.dos.strategy import campaign_work, commit_campaign_work


def prepared():
    session=ready()
    agents=[]
    for index in range(1,11):
        row={"prefix":[0]*15,"remaining":0,"parameter":0,"suffix":[0]*8}
        if index not in STATUS_FLAGS:row["status"]=0
        agents.append(row)
    session.state["campaign"]["bar"]={"agents":agents,"contracts":[[0]*24 for _ in range(10)],
        "intelligence":[0]*12,"earth_sabotaged":0,"social":None,"conversation":None}
    session.catalog["ore_names"]=dict(zip(ORE_KEYS,("Detoxin","Energon","Kremir","Lepitium","Raenium","Texon")))
    session.catalog["pirate_messages"]=[f"Original pirate notice {i}" for i in range(1,11)]
    return session


def mission(session,index,parameter=0,remaining=1,status=0):
    campaign=session.state["campaign"];row=campaign["bar"]["agents"][index-1]
    row.update(parameter=parameter,remaining=remaining)
    if index==10:campaign["navigation"]["ending"]=status
    elif index in STATUS_FLAGS:campaign["flags"][STATUS_FLAGS[index]]=status
    else:row["status"]=status


def contract(session,index=1,codes=(1,6,11,0),amounts=(101,203,5,0),threshold=100):
    row=session.state["campaign"]["bar"]["contracts"][index-1]
    row[:4]=codes;row[4:12]=struct.pack("<4H",*amounts);row[13]=threshold;row[19:21]=[10,0]


class BarTests(unittest.TestCase):
    def test_only_active_positive_timers_advance_and_expiry_clears_parameter(self):
        for status in (0,1,2,3,255):
            for remaining in (-32768,-1,0,1,2,32767):
                s=prepared();mission(s,1,17,remaining,status);before=campaign_work(s.state)
                result,events=bar_hour(before);row=result["bar"]["agents"][0]
                advances=status in (0,2) and remaining>0
                self.assertEqual(row["remaining"],remaining-int(advances))
                self.assertEqual(row["parameter"],0 if advances and remaining==1 else 17)
                self.assertEqual(events,[]);self.assertEqual(before,campaign_work(s.state))

    def test_each_ore_credits_its_displayed_resource_including_texon(self):
        for code,key in enumerate(ORE_KEYS,1):
            s=prepared();mission(s,9,1);contract(s,codes=(code,0,0,0),amounts=(65535,0,0,0))
            old=deepcopy(s.state["resources"]);s.apply("advance",hours=1)
            old[key]+=65535;self.assertEqual(s.state["resources"],old)
            self.assertEqual(s.state["campaign"]["bar"]["contracts"][0][19:21],[0,0])
            self.assertTrue(any(e["id"]==47 for e in s.state["events"]))

    def test_half_rewards_round_down_and_do_not_unlock_products(self):
        s=prepared();mission(s,9,11);contract(s);s.state["products"][0]["research_state"]=0
        old=deepcopy(s.state);s.apply("advance",hours=1)
        self.assertEqual(s.state["resources"]["detoxin"],old["resources"]["detoxin"]+50)
        self.assertEqual(s.state["resources"]["texon"],old["resources"]["texon"]+101)
        self.assertEqual(s.state["products"][0]["stock"],old["products"][0]["stock"]+2)
        self.assertEqual(s.state["products"][0]["research_state"],0)

    def test_failure_and_success_use_strict_threshold_and_one_draw(self):
        s=prepared();mission(s,9,1);contract(s)
        work=campaign_work(s.state);seed,roll=random_bounded(work["rng"],100)
        for threshold,notice in ((roll,42),(roll+1,47)):
            work["bar"]["contracts"][0][13]=threshold;result,events=bar_hour(work)
            self.assertEqual(events[0],("message",notice));self.assertEqual(result["rng"],seed)
            self.assertEqual(result["bar"]["agents"][8]["parameter"],0)

    def test_invalid_target_and_inventory_overflow_roll_back_entire_hour(self):
        for mode in ("target","code","ore","stock"):
            s=prepared();mission(s,9,0 if mode=="target" else 1);contract(s)
            if mode=="code":s.state["campaign"]["bar"]["contracts"][0][0]=10
            if mode=="ore":s.state["resources"]["detoxin"]=2**32-1
            if mode=="stock":s.state["products"][0]["stock"]=32767
            before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply("advance",hours=1)
            self.assertEqual(s.state,before)

    def test_diplomatic_returns_and_locked_only_rewards(self):
        for parameter in (0,1,2):
            s=prepared();mission(s,5,parameter,status=2)
            s.state["products"][28]["research_state"]=0;s.state["products"][25]["research_state"]=0
            result,events=bar_hour(campaign_work(s.state))
            self.assertEqual(events,[("message",40)]+([("message",42+parameter)] if parameter else []))
            if parameter:self.assertEqual(result["civilizations"][parameter+4][27],6)
            self.assertEqual(result["products"][28]["research_state"],5 if parameter==2 else 0)
            self.assertEqual(result["products"][25]["research_state"],3 if parameter==2 else 0)
            if parameter==2:self.assertEqual(result["bar"]["agents"][2]["status"],2)
            s.state["products"][28]["research_state"]=1
            self.assertEqual(bar_hour(campaign_work(s.state))[0]["products"][28]["research_state"],1)

    def test_earth_sabotage_clamps_each_force_and_occurs_once(self):
        s=prepared();mission(s,7,status=2)
        work=campaign_work(s.state);raw=[0]*65;raw[27:59]=struct.pack("<8I",5,8,3,9,20,4,16,18)
        work["worlds"]["8:3:0"]={"raw":raw}
        result,events=bar_hour(work)
        self.assertEqual(struct.unpack_from("<8I",bytes(result["worlds"]["8:3:0"]["raw"]),27),(0,8,2,7,20,0,6,8))
        self.assertEqual(events,[("message",41)]);self.assertEqual(result["flags"]["1eb"],1)
        self.assertEqual(result["bar"]["earth_sabotaged"],1)
        repeated,repeated_events=bar_hour(result);self.assertEqual(repeated,result);self.assertEqual(repeated_events,[])

    def test_intelligence_selects_colonies_active_fleets_and_weapon_flags(self):
        s=prepared();work=campaign_work(s.state);work["worlds"]={}
        for identity,owner,colony in (("2:1:1",3,1),("2:1:0",3,1),("1:1:0",4,1),("1:2:0",3,0)):
            raw=[0]*65;raw[0]=owner;raw[6]=colony;work["worlds"][identity]={"raw":raw}
        report=intelligence_reports(work,3,3)
        self.assertEqual([r["world"] for r in report["reports"]],["2:1:0","2:1:1"])
        order(s);work["civilizations"]=deepcopy(s.state["campaign"]["civilizations"])
        self.assertEqual(intelligence_reports(work,3,2)["reports"][0]["forces"][0],3)
        work["civilizations"][1][19:27]=[1,0,1,0,0,0,0,1]
        self.assertEqual(intelligence_reports(work,3,4)["reports"],[{"weapons":[1,3,8]}])

    def test_detailed_intelligence_includes_the_moon_garrison_in_space_combat(self):
        from test_space_roster import fixture
        from openreunion.dos.space_roster import build_space_battle
        args=fixture();fleets,civs,worlds=args[:3]
        civs[1][27]=2;raw=worlds['1:5:1']['raw'];raw[0]=3
        raw[27:59]=struct.pack('<8I',15,5,0,0,0,0,0,0)
        work={'worlds':worlds,'civilizations':civs};before=deepcopy(work)
        detail=intelligence_reports(work,3,3)['reports']
        self.assertEqual(detail,[{'world':'1:5:1','base':False,'garrison':True,'forces':[15,5,0,0,0,0,0,0]}])
        self.assertEqual(intelligence_reports(work,3,1)['reports'],[])
        battle=build_space_battle(*args)
        self.assertEqual(battle['hostile_count'],sum(detail[0]['forces'][:4]))
        self.assertTrue(all(u['origin']=={'source':'world','world':'1:5:1'} for u in battle['hostile']))
        self.assertEqual(work,before)

    def test_garrison_report_excludes_empty_and_other_owners_and_uses_unsigned_counts(self):
        work=campaign_work(prepared().state);work['worlds']={}
        for identity,owner,colony,count in (('1:1:0',3,0,0),('1:2:0',4,0,10),('1:3:0',3,0,2**32-1),('1:4:0',3,1,0)):
            raw=[0]*65;raw[0]=owner;raw[6]=colony;raw[27:31]=struct.pack('<I',count)
            work['worlds'][identity]={'raw':raw}
        reports=intelligence_reports(work,3,3)['reports']
        self.assertEqual([r['world'] for r in reports],['1:3:0','1:4:0'])
        self.assertEqual(reports[0]['forces'][0],2**32-1)
        self.assertNotIn('garrison',reports[1])

    def test_intelligence_level_never_downgrades_and_invalid_race_rejected(self):
        for kind,old,expected in ((1,0,1),(1,2,2),(2,1,1),(3,0,2),(4,1,1)):
            s=prepared();mission(s,2,20*kind+3);s.state["campaign"]["bar"]["intelligence"][2]=old
            result,events=bar_hour(campaign_work(s.state))
            self.assertEqual(result["bar"]["intelligence"][2],expected)
            self.assertEqual(events[0],("message",39))
        s=prepared();mission(s,2,39)
        with self.assertRaises(GameError):bar_hour(campaign_work(s.state))

    def test_contract_announcements_use_exact_calendar_and_original_draws(self):
        s=prepared();work=campaign_work(s.state)
        for i in (0,3):work["bar"]["contracts"][i][14:19]=[*struct.pack("<h",work["date"][0]),*work["date"][1:]]
        result,events=bar_hour(work);seed,_=random_bounded(work["rng"],3);seed,_=random_bounded(seed,3)
        self.assertEqual(events,[("pirate_announcement",1),("pirate_announcement",4)])
        self.assertEqual(result["rng"],seed);self.assertEqual(result["bar"]["contracts"],work["bar"]["contracts"])

    def test_aliases_have_one_owner_and_persist_without_reward_replay(self):
        s=prepared();mission(s,9,1);contract(s)
        for index,key in STATUS_FLAGS.items():
            self.assertNotIn("status",s.state["campaign"]["bar"]["agents"][index-1])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"missions.json";s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            for current in (s,loaded):current.apply("advance",hours=1)
            self.assertEqual(s.state,loaded.state)
            s.save(path);loaded=RecoveredSession.load(s.catalog,path);resources=deepcopy(loaded.state["resources"])
            loaded.apply("advance",hours=1);self.assertEqual(loaded.state["resources"],resources)
        work=campaign_work(s.state);work["flags"]["164"]=2;commit_campaign_work(s.state,work)
        self.assertEqual(agent_status(campaign_work(s.state),2),2)
        s.state["campaign"]["bar"]["agents"][1]["status"]=1
        with self.assertRaises(GameError):validate_bar(s.state["campaign"]["bar"])

    def test_bar_rng_precedes_pending_battle_roster(self):
        s=prepared();order(s);mission(s,9,1);contract(s,codes=(0,0,0,0))
        from openreunion.dos.space_encounter import open_space_encounter
        captured=[]
        def capture(work,*args,**kwargs):
            captured.append(deepcopy(work));return open_space_encounter(work,*args,**kwargs)
        with patch("openreunion.dos.space_encounter.open_space_encounter",capture):
            s.apply("advance",hours=24)
            self.assertEqual(captured,[])
            while s.state['presentation_requests']:s.apply('dismiss_presentation')
        self.assertEqual(len(captured),1)
        self.assertEqual(captured[0]["bar"]["agents"][8]["remaining"],0)
        self.assertEqual(captured[0]["bar"]["contracts"][0][19:21],[0,0])
        self.assertEqual(s.state["date"][3],9)

    def test_old_save_records_remain_explicitly_unavailable(self):
        s=prepared();state=deepcopy(s.state);state["schema"]="recovered-strategy-v13";del state["campaign"]["bar"];del state['active_scene']
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"v13.json";path.write_text(json.dumps(state),encoding="utf-8")
            loaded=RecoveredSession.load(s.catalog,path)
            self.assertEqual(loaded.state["schema"],SCHEMA);self.assertIsNone(loaded.state["campaign"]["bar"])
            self.assertEqual(loaded.state["campaign"]["flags"],state["campaign"]["flags"])
            state["campaign"]["bar"]=None;path.write_text(json.dumps(state),encoding="utf-8")
            with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)


if __name__=="__main__":unittest.main()
