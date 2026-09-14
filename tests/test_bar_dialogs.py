"""Bar purchase transactions, shared state and saved conversation boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from test_bar import prepared
from openreunion.core import GameError
from openreunion.dos.bar_dialogs import SOCIAL_FLAGS,choices,current_contract,initialize_contracts
from openreunion.dos.session import RecoveredSession,SCHEMA
from openreunion.dos.strategy import campaign_work


def session_fixture():
    s=prepared();bar=s.state["campaign"]["bar"];bar["social"]={key:0 for key in SOCIAL_FLAGS}
    s.state["resources"]["credits"]=500000
    s.state["campaign"]["flags"]["164"]=2;s.state["campaign"]["flags"]["1eb"]=2
    # Synthetic text with compact paths through the actual quote/purchase IDs.
    spy={"nodes":[[1] for _ in range(11)],"questions":[{"next":1,"text":"Ask"} for _ in range(26)],
         "answers":[{"next":0,"text":"Answer"} for _ in range(16)]}
    spy["nodes"][1]=[10];spy["nodes"][8]=[19,20,21,22];spy["nodes"][9]=[23,24]
    spy["questions"][9]["next"]=9;spy["answers"][8]["next"]=8
    for q in range(19,23):spy["questions"][q-1]["next"]=q-9;spy["answers"][q-10]["next"]=9
    spy["questions"][22]["next"]=14;spy["questions"][23]["next"]=15
    bounty={"nodes":[[1],[4,5]],"questions":[{"next":i,"text":"Ask"} for i in range(1,8)],
            "answers":[{"next":0,"text":"Answer"} for _ in range(7)]}
    s.catalog["bar_dialogs"]={"definitions":{"2":spy,"7":bounty},"prices":[10000,14000,20000,7000],
        "multipliers":[1,1,5,3,2,1,10,8,7,5,1,15],"names":{"7":"Bounty-Hunter"},
        "quote_prefixes":["It will be ","My work will cost "],"quote_suffix":" credits"}
    return s


def get_quote(s,question=19):
    s.apply("bar_talk",agent=2);s.apply("bar_answer",question=10);s.apply("bar_acknowledge")
    s.apply("bar_answer",question=question);s.apply("bar_acknowledge")


class BarDialogTests(unittest.TestCase):
    def test_quote_preserves_price_wording_and_seed_across_save(self):
        s=session_fixture();get_quote(s,20)
        current=s.state["campaign"]["bar"]["conversation"]
        self.assertEqual(current["quote"]["price"],70000)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"quote.json";s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            self.assertEqual(loaded.state,s.state)
            for item in (s,loaded):item.apply("bar_answer",question=23)
            self.assertEqual(loaded.state,s.state)
            self.assertTrue(100<=s.state["campaign"]["bar"]["agents"][1]["remaining"]<200)

    def test_underfunded_quote_retains_every_field_and_admin_can_fund(self):
        s=session_fixture();get_quote(s);s.state["resources"]["credits"]=49999;before=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply("bar_answer",question=23)
        self.assertEqual(s.state,before)
        s.admin_enabled=True;s.apply("admin",command="give credits 1");s.apply("bar_answer",question=23)
        self.assertEqual(s.state["resources"]["credits"],0);self.assertTrue(s.state["assisted"])

    def test_repeated_and_unoffered_purchase_cannot_spend_twice(self):
        s=session_fixture();get_quote(s);s.apply("bar_answer",question=23);before=deepcopy(s.state)
        for question in (23,5):
            with self.assertRaises(GameError):s.apply("bar_answer",question=question)
            self.assertEqual(s.state,before)
        s.apply("bar_acknowledge");self.assertIsNone(s.state["campaign"]["bar"]["conversation"])
        with self.assertRaises(GameError):s.apply("bar_talk",agent=2)

    def test_declined_quote_leaves_resources_and_timer_unchanged(self):
        s=session_fixture();get_quote(s);before=deepcopy(s.state)
        s.apply("bar_answer",question=24);s.apply("bar_acknowledge")
        self.assertEqual(s.state["resources"],before["resources"])
        self.assertEqual(s.state["campaign"]["bar"]["agents"][1]["remaining"],0)

    def test_bar_holds_clock_until_explicit_leave_or_final_ack(self):
        s=session_fixture();s.apply("bar_talk",agent=7);before=deepcopy(s.state)
        for action,args in (("advance",{"hours":1}),("bar_talk",{"agent":2}),("research",{"product_id":1})):
            with self.assertRaises(GameError):s.apply(action,**args)
            self.assertEqual(s.state,before)
        s.apply("bar_leave");s.apply("advance",hours=1)
        self.assertNotEqual(s.state["date"],before["date"])

    def test_bounty_payment_and_mission_survive_terminal_answer_reload(self):
        s=session_fixture();s.apply("bar_talk",agent=7);old=s.state["resources"]["credits"]
        s.apply("bar_answer",question=4);self.assertEqual(s.state["resources"]["credits"],old-100000)
        row=deepcopy(s.state["campaign"]["bar"]["agents"][6])
        self.assertTrue(100<=row["remaining"]<200);self.assertEqual(row["parameter"],2)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"return.json";s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            loaded.apply("bar_acknowledge");self.assertEqual(loaded.state["campaign"]["bar"]["agents"][6],row)
        self.assertEqual(s.state["campaign"]["bar"]["social"]["7748"],1)

    def test_invalid_saved_quote_is_rejected(self):
        s=session_fixture();get_quote(s);state=deepcopy(s.state)
        for change in ("price","wording","phase","answer"):
            damaged=deepcopy(state);current=damaged["campaign"]["bar"]["conversation"]
            if change in ("price","wording"):current["quote"][change]=999
            elif change=="phase":current["phase"]="unknown"
            else:current["answer"]=999
            with self.assertRaises(GameError):RecoveredSession(s.catalog,damaged)

    def test_v14_keeps_missions_but_cannot_invent_missing_social_flags(self):
        s=session_fixture();old=deepcopy(s.state);old["schema"]="recovered-strategy-v14";del old['active_scene']
        del old["campaign"]["bar"]["social"];del old["campaign"]["bar"]["conversation"]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"v14.json";path.write_text(json.dumps(old),encoding="utf-8")
            loaded=RecoveredSession.load(s.catalog,path)
            self.assertEqual(loaded.state["schema"],SCHEMA);self.assertIsNone(loaded.state["campaign"]["bar"]["social"])
            self.assertEqual(loaded.state["campaign"]["bar"]["agents"],old["campaign"]["bar"]["agents"])
            with self.assertRaises(GameError):loaded.apply("bar_talk",agent=7)

    def test_contract_windows_are_strict_and_last_overlap_wins(self):
        import struct
        s=session_fixture();work=campaign_work(s.state);work["date"]=[2927,8,13,12]
        for row in work["bar"]["contracts"]:
            row[14:19]=[*struct.pack("<h",2927),8,13,11];row[19:24]=[*struct.pack("<h",2927),8,13,13]
        self.assertEqual(current_contract(work),10)
        work["date"][-1]=11;self.assertEqual(current_contract(work),0)
        work["date"][-1]=13;self.assertEqual(current_contract(work),0)

    def test_contract_initialization_carries_real_calendar_units(self):
        import struct
        work=campaign_work(session_fixture().state);work["date"]=[2927,12,30,23]
        row=work["bar"]["contracts"][0];row[14:19]=[*struct.pack("<h",0),0,0,1]
        initialize_contracts(work)
        self.assertEqual(row[14:19],[*struct.pack("<h",2928),1,1,0])


if __name__=="__main__":unittest.main()
