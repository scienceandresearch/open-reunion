"""Consultation transactions, RNG continuity and original recommendation order."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from test_recovered import fixture
from openreunion.core import GameError
from openreunion.dos.advice import PHRASES,consult,recommendation,validate_rules
from openreunion.dos.campaign import random_bounded
from openreunion.dos.session import RecoveredSession


def rules():
    return {'priorities':[[1,4],[1,6],[2,3],[2,4],[2,5],[2,7],[3,25],[3,16],[4,3]],
            'questions':[f'Question {i}' for i in range(4)],'replies':[f'Reply {i}' for i in range(5)],
            'reasons':[f'Reason {i}' for i in range(9)],'phrases':{key:key for key in PHRASES}}


class AdviceTests(unittest.TestCase):
    def session(self):
        catalog,state=fixture();catalog['commander_advice']=rules()
        session=RecoveredSession(catalog,state);session.apply('hire',role='pilot',rank=1);return session

    def test_priority_is_last_matching_research_state_not_stock(self):
        r=rules();products=[{'research_state':0,'stock':999} for _ in range(35)]
        for status in (1,2,3,4):
            products[3]['research_state']=products[5]['research_state']=status
            self.assertEqual(recommendation(r,products,'pilot',False),1)
            self.assertIsNone(recommendation(r,products,'pilot',True))
        products[5]['research_state']=5
        self.assertEqual(recommendation(r,products,'pilot',False),0)
        self.assertEqual(recommendation(r,products,'pilot',True),1)
        self.assertIsNone(recommendation(r,products,'developer',False))

    def test_only_original_questions_consume_random_draws(self):
        catalog,state=fixture();r=rules();products=state['products'];seed=1944
        _,after=consult(r,products,catalog['products'],'pilot',3,seed)
        self.assertEqual(seed,after) # All research complete: no recommendation.
        for question,bound in ((1,2),(2,50),(4,50)):
            _,after=consult(r,products,catalog['products'],'pilot',question,seed)
            self.assertEqual(after,random_bounded(seed,bound)[0])

    def test_consultation_only_changes_rng_and_persisted_log(self):
        s=self.session();before=deepcopy(s.state)
        response=s.apply('consult_commander',role='pilot',question=4)[0]
        self.assertEqual(response['product_id'],6)
        self.assertIn(response['answer'],s.state['log'][-1])
        after=deepcopy(s.state);after['log']=before['log'];after['campaign']['rng']=before['campaign']['rng']
        self.assertEqual(after,before)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'advice.json';s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            for question in (1,2,3,4):
                self.assertEqual(s.apply('consult_commander',role='pilot',question=question),
                                 loaded.apply('consult_commander',role='pilot',question=question))
            self.assertEqual(s.state,loaded.state)

    def test_invalid_or_absent_commander_rejects_atomically(self):
        s=self.session()
        for role,question in (('pilot',0),('pilot',5),('pilot',True),('builder',1),('unknown',1)):
            before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply('consult_commander',role=role,question=question)
            self.assertEqual(s.state,before)
        del s.catalog['commander_advice'];before=deepcopy(s.state)
        with self.assertRaisesRegex(GameError,'extract'):s.apply('consult_commander',role='pilot',question=1)
        self.assertEqual(s.state,before)

    def test_training_and_research_interruption_block_consultation(self):
        s=self.session();s.state['campaign']['training_role']=1;s.state['campaign']['training_remaining']=20
        before=deepcopy(s.state)
        with self.assertRaisesRegex(GameError,'university'):s.apply('consult_commander',role='pilot',question=1)
        self.assertEqual(s.state,before)
        s.apply('hire',role='developer',rank=1);s.state['campaign']['research_block_remaining']=3
        before=deepcopy(s.state)
        with self.assertRaisesRegex(GameError,'interruption'):s.apply('consult_commander',role='developer',question=1)
        self.assertEqual(s.state,before)

    def test_corrupt_extracted_rules_reject(self):
        validate_rules(rules())
        for key,value in (('questions',[]),('replies',[None]*5),('priorities',[[1,36]]*9),('phrases',{})):
            invalid=rules();invalid[key]=value
            with self.assertRaises(GameError):validate_rules(invalid)


if __name__=='__main__':unittest.main()
