"""The accepted bargain survives story ordering without erasing other threats."""
from copy import deepcopy
import unittest
from test_story import state_fixture, RULES
from openreunion.dos.aliens import fleet_at
from openreunion.dos.dialogs import response_effect
from openreunion.dos.story import story_hour


def fixture():
    state=state_fixture();state['resources']={};state['hunter_allowed']=1
    state['timers']['5d76']=1
    state['worlds']['2:5:0']['raw'][0]=5
    return state


class PrisonerOrderingTests(unittest.TestCase):
    def test_bargain_before_contact_event_preserves_diversion_and_random_state(self):
        state=response_effect(fixture(),6,5);before=deepcopy(state)
        result,events=story_hour(state,RULES)
        expected=deepcopy(before);expected['timers']['5d76']=0;expected['flags']['5d78']=1
        self.assertEqual(result,expected);self.assertEqual(state,before);self.assertEqual(events,[])
        self.assertEqual(story_hour(result,RULES),(result,[]))

    def test_bargain_in_both_orders_prevents_phelonian_destruction(self):
        for early in (True,False):
            state=fixture()
            if early:state=response_effect(state,6,5)
            state,_=story_hour(state,RULES)
            if not early:state=response_effect(state,6,5)
            for _ in range(4100):state,events=story_hour(state,RULES)
            self.assertEqual(state['timers']['5d7a'],0)
            self.assertEqual(state['flags']['5d7c'],0)
            self.assertEqual(state['worlds']['2:5:0']['raw'][0],5)
            self.assertEqual(fleet_at(state['civilizations'][2],2)[8:11],[3,3,0])

    def test_alternate_choices_retain_the_attack_plan(self):
        for questions in ((1,),(3,),(2,4,6)):
            state=fixture()
            for question in questions:state=response_effect(state,6,question)
            state,_=story_hour(state,RULES)
            self.assertGreaterEqual(state['timers']['5d7a'],3999)
            self.assertEqual(fleet_at(state['civilizations'][2],2)[8:11],[2,5,0])
            state['timers']['5d7a']=1
            state,events=story_hour(state,RULES)
            self.assertIn(('message',24),events)
            self.assertEqual(state['worlds']['2:5:0']['raw'][0],0)

    def test_other_invasions_still_fire_and_past_destruction_is_not_reversed(self):
        state=response_effect(fixture(),6,5)
        state['timers']['5d72']=1
        result,_=story_hour(state,RULES)
        self.assertEqual(result['flags']['5d74'],1)
        self.assertEqual(fleet_at(result['civilizations'][1],3)[8:11],[1,5,0])
        state=fixture();state['timers']['5d76']=0;state['timers']['5d7a']=1
        state,_=story_hour(state,RULES)
        state=response_effect(state,6,5);state['timers']['5d7e']=1
        result,_=story_hour(state,RULES)
        self.assertEqual(result['worlds']['2:5:0']['raw'][0],0)
        self.assertEqual(result['flags']['5d80'],1)
        for race,slot in ((3,4),(4,2)):
            self.assertEqual(fleet_at(result['civilizations'][race-2],slot)[8:11],[1,5,0])


if __name__=='__main__':unittest.main()
