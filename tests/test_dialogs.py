"""Conversation routing and corrected bargains, using original-free fixtures."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.core import GameError
from openreunion.dos.dialogs import conversation,start_conversation,choose_answer,respond,response_effect,validate_dialog_state,closing_messages


def fixture():
    return {"rng":1994,"flags":dict.fromkeys(("5d50","5d3f","5d74","1b5","1eb"),0),
            "timers":dict.fromkeys(("5d52","5d7a","5d72"),0),"hunter_allowed":0,
            "products":[{"research_state":0,"research_remaining":10000,"stock":0,"queued":0} for _ in range(35)],
            "resources":dict(credits=100000,energon=30000,kremir=40000),"civilizations":[[0]*228 for _ in range(11)],
            "known_systems":[1,0,255,255,255,255,255,255]}


class DialogTests(unittest.TestCase):
    def definition(self):
        return conversation(3,{"3":[[1],[1],[2,3]]},["02 Ask","03 Buy","04 Leave"],
                            ["01 Start","02 Price|shown","00 Received","00 Goodbye",""])

    def test_text_codes_and_choice_graph_are_separate(self):
        d=self.definition();current=start_conversation(d)
        self.assertEqual(choose_answer(d,current,1),dict(script=3,node=2,answer=2,closed=False))
        self.assertEqual(d["answers"][1]["text"],"Price\nshown")
        with self.assertRaises(GameError):choose_answer(d,current,2)
        current=choose_answer(d,choose_answer(d,current,1),3)
        self.assertTrue(current["closed"])
        with self.assertRaises(GameError):choose_answer(d,current,1)

    def test_malformed_routing_and_saved_state_rejected(self):
        for questions,answers in ((["xx Bad"],["01 Test"]),(["99 Missing"],["01 Test"]),(["01 Test"],["99 Bad node"])):
            with self.assertRaises(GameError):conversation(3,{"3":[[1],[1]]},questions,answers)
        d=self.definition()
        for current in (dict(script=3,node=1,answer=True,closed=False),dict(script=3,node=0,answer=0,closed=True),
                        dict(script=3,node=1,answer=3,closed=False)):
            with self.assertRaises(GameError):validate_dialog_state(d,current)

    def test_atomic_refusal_preserves_current_dialog_and_economic_state(self):
        d=conversation(3,{"3":[[1],[6]]},["01 Unused"]*5+["02 Buy"],["01 Start","00 Received"])
        current=start_conversation(d);state=fixture();state["resources"]["credits"]=15999
        before=deepcopy((current,state))
        with self.assertRaises(GameError):respond(d,current,state,6)
        self.assertEqual((current,state),before)
        state["resources"]["credits"]=16000
        updated,result,messages=respond(d,current,state,6)
        self.assertTrue(updated["closed"]);self.assertEqual(result["resources"]["credits"],0)
        self.assertEqual(result["products"][13]["research_state"],3);self.assertEqual(messages,[])

    def test_scientist_leave_and_refusal_are_distinct(self):
        state=fixture();accepted=response_effect(state,2,4)
        self.assertTrue(60<=accepted["timers"]["5d52"]<=89)
        self.assertNotEqual(accepted["rng"],state["rng"])
        declined=response_effect(state,2,5)
        self.assertEqual(declined["timers"]["5d52"],0);self.assertEqual(declined["rng"],state["rng"])
        self.assertEqual(accepted["flags"]["5d50"],declined["flags"]["5d50"])

    def test_money_trades_take_promised_ore_and_preserve_other_stock(self):
        for choice,price in ((5,100000),(8,120000)):
            state=fixture();result=response_effect(state,7,choice)
            self.assertEqual(result["resources"],dict(credits=100000+price,energon=20000,kremir=40000))
            self.assertEqual(state["resources"]["energon"],30000)
        state=fixture();state["resources"]["energon"]=7
        self.assertEqual(response_effect(state,7,8)["resources"],dict(credits=100084,energon=0,kremir=40000))

    def test_technology_bargain_cost_is_fixed_and_requires_sufficient_energon(self):
        state=fixture();result=response_effect(state,7,9)
        self.assertEqual(result["resources"],dict(credits=100000,energon=20000,kremir=40000))
        self.assertEqual(result["products"][20]["research_state"],5)
        self.assertEqual(result["products"][20]["research_remaining"],0)
        state["resources"]["energon"]=9999
        with self.assertRaises(GameError):response_effect(state,7,9)

    def test_rewards_preserve_original_locked_only_rule(self):
        state=fixture();state["products"][9]["research_state"]=2
        result=response_effect(state,4,4)
        self.assertEqual(result["products"][9],state["products"][9])
        self.assertEqual(result["products"][10]["research_state"],5);self.assertEqual(result["hunter_allowed"],1)

    def test_inventory_currency_and_timer_overflow_are_atomic(self):
        for script,question,mutate in ((5,4,lambda s:s["products"][15].update(stock=32760,queued=1)),
            (5,4,lambda s:s["products"][15].update(stock=32750,queued=10)),
            (7,8,lambda s:s["resources"].update(credits=2**32-1)),
            (6,5,lambda s:s["timers"].update({"5d72":32700}))):
            state=fixture();mutate(state);before=deepcopy(state)
            with self.assertRaises(GameError):response_effect(state,script,question)
            self.assertEqual(state,before)

    def test_accepted_prisoner_bargain_orders_the_original_kall_fleet(self):
        state=fixture();state["timers"]["5d7a"]=1000
        result=response_effect(state,6,5)
        self.assertEqual(result["flags"]["5d3f"],1);self.assertEqual(result["timers"]["5d7a"],0)
        self.assertEqual(result["civilizations"][2][74:77],[3,3,0])
        self.assertEqual(closing_messages(6,result["flags"]),[48])

    def test_prisoner_information_release_and_refusal_do_not_earn_diversion(self):
        for questions in ((1,), (3,), (2,4,6)):
            state=fixture();state['timers']['5d7a']=1000
            before=deepcopy(state)
            for question in questions:state=response_effect(state,6,question)
            self.assertEqual(state,before)

    def test_eran_acceptance_and_earth_revelation(self):
        state=fixture();accepted=response_effect(state,9,3)
        self.assertEqual(accepted["civilizations"][4][27],6)
        self.assertEqual(closing_messages(9,accepted["flags"]),[46])
        self.assertEqual(closing_messages(9,state["flags"]),[])
        revealed=response_effect(state,10,6)
        self.assertEqual(revealed["known_systems"][7],0)
        self.assertEqual(revealed["products"][34]["research_state"],5)
        self.assertEqual(revealed["flags"]["1eb"],2)


if __name__=="__main__":unittest.main()
