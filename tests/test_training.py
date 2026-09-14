"""Training transactions, save continuity and interactions with hourly research."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from test_recovered import fixture
from openreunion.core import GameError
from openreunion.dos.campaign import random_bounded
from openreunion.dos.commanders import commander_hour,training_quote,validate_training_rules
from openreunion.dos.session import RecoveredSession


class TrainingTests(unittest.TestCase):
    def session(self,role="developer",rank=2):
        catalog,state=fixture();state["resources"]["credits"]=1000000
        session=RecoveredSession(catalog,state);session.apply("hire",role=role,rank=rank)
        return session

    def rejected(self,session,action,**args):
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply(action,**args)
        self.assertEqual(session.state,before)

    def test_reviewable_quote_persists_and_charges_once(self):
        s=self.session();seed=s.state["campaign"]["rng"];credits=s.state["resources"]["credits"]
        s.apply("quote_training",role="developer",course=1)
        cost,seed=training_quote(20,seed)
        self.assertEqual(s.state["campaign"]["rng"],seed)
        self.assertEqual(s.state["resources"]["credits"],credits)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"quoted.json";s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            loaded.apply("train");s.apply("train");self.assertEqual(loaded.state,s.state)
        self.assertEqual(s.state["resources"]["credits"],credits-cost)
        self.assertTrue(50<=s.state["campaign"]["training_remaining"]<=69)
        self.assertIsNone(s.state["campaign"]["training"]["quote"])
        self.rejected(s,"train")

    def test_insufficient_funds_preserve_quote_seed_and_state(self):
        s=self.session();s.apply("quote_training",role="developer",course=1)
        s.state["resources"]["credits"]=s.state["campaign"]["training"]["quote"]["cost"]-1
        self.rejected(s,"train")

    def test_hired_role_course_and_occupancy_guards(self):
        s=self.session()
        for role,course in (("pilot",0),("developer",0),("developer",5),("developer",True),("unknown",0)):
            self.rejected(s,"quote_training",role=role,course=course)
        s.apply("quote_training",role="developer",course=1);s.apply("train")
        self.rejected(s,"quote_training",role="developer",course=2)
        s.apply("hire",role="pilot",rank=1)
        self.rejected(s,"quote_training",role="pilot")

    def test_research_pauses_until_hour_after_completion_and_save_resumes(self):
        s=self.session();s.state["products"][0].update(research_state=2,research_remaining=10000)
        s.state["campaign"]["idea_timers"][1]=10;s.state["products"][1]["research_state"]=0
        s.apply("quote_training",role="developer",course=1);s.apply("train")
        duration=s.state["campaign"]["training_remaining"]
        s.apply("advance",hours=duration-1)
        self.assertEqual(s.state["products"][0]["research_remaining"],10000)
        self.assertEqual(s.state["campaign"]["idea_timers"][1],10)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"training.json";s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            s.apply("advance",hours=1);loaded.apply("advance",hours=1)
            self.assertEqual(s.state,loaded.state)
        self.assertEqual(s.state["campaign"]["training_role"],0)
        self.assertEqual(s.state["products"][0]["research_remaining"],10000)
        self.assertEqual(s.state["levels"]["developer"],70)
        self.assertEqual(list(s.state["skills"].values()),[4,3,2,2])
        s.apply("advance",hours=1)
        self.assertLess(s.state["products"][0]["research_remaining"],10000)
        self.assertEqual(s.state["campaign"]["idea_timers"][1],9)

    def test_other_role_training_does_not_block_research(self):
        s=self.session();s.apply("hire",role="pilot",rank=1)
        s.state["products"][0].update(research_state=2,research_remaining=10000)
        s.apply("quote_training",role="pilot");s.apply("train");s.apply("advance",hours=1)
        self.assertLess(s.state["products"][0]["research_remaining"],10000)

    def test_replacement_ends_only_that_roles_course_without_refund(self):
        s=self.session(rank=1);s.apply("quote_training",role="developer",course=1);s.apply("train")
        remaining=s.state["campaign"]["training_remaining"]
        s.apply("hire",role="pilot",rank=1)
        self.assertEqual(s.state["campaign"]["training_role"],4)
        credits=s.state["resources"]["credits"];s.apply("hire",role="developer",rank=2)
        self.assertEqual(s.state["resources"]["credits"],credits-200)
        self.assertEqual(s.state["campaign"]["training_role"],0)
        self.assertEqual(s.state["campaign"]["training_remaining"],remaining)
        self.assertEqual(list(s.state["skills"].values()),[2]*4)

    def test_quote_is_invalidated_by_replacement(self):
        s=self.session(rank=1);s.apply("quote_training",role="developer",course=1)
        s.apply("hire",role="developer",rank=2)
        self.assertIsNone(s.state["campaign"]["training"]["quote"])
        self.rejected(s,"train")

    def test_current_story_skill_limits_gate_courses(self):
        s=self.session();s.state["skills"].update(math=7,physics=7)
        self.rejected(s,"quote_training",role="developer",course=1)
        s.apply("quote_training",role="developer",course=2)
        s.state["skills"]["electronics"]=7
        self.rejected(s,"train")

    def test_completion_clamps_all_skills_and_preserves_hiring_candidates(self):
        s=self.session();c=s.state["campaign"];before=deepcopy((c["commander_levels"],c["developer_skill_choices"]))
        c.update(training_role=4,training_remaining=1);c["training"]["course"]=4
        s.state["skills"].update(math=9,physics=9,electronics=9,artificial_intelligence=6)
        s.apply("advance",hours=1)
        self.assertEqual(list(s.state["skills"].values()),[7]*4)
        self.assertEqual((c["commander_levels"],c["developer_skill_choices"]),before)
        self.assertEqual((s.state["campaign"]["commander_levels"],s.state["campaign"]["developer_skill_choices"]),before)

    def test_hourly_rng_consumed_at_cap_but_not_for_unhired_roles(self):
        s=self.session("pilot",1);s.state["levels"]["pilot"]=30;c=s.state["campaign"]
        expected,_=random_bounded(c["rng"],100)
        commander_hour(s.state["levels"],s.state["ranks"],s.state["skills"],c,s.catalog["training_rules"])
        self.assertEqual(c["rng"],expected);self.assertEqual(s.state["levels"]["pilot"],30)

    def test_large_unsigned_credit_balance_can_train(self):
        s=self.session();s.state["resources"]["credits"]=2**31
        s.apply("quote_training",role="developer",course=1);cost=s.state["campaign"]["training"]["quote"]["cost"]
        s.apply("train");self.assertEqual(s.state["resources"]["credits"],2**31-cost)

    def test_malformed_nested_training_rejected(self):
        catalog,state=fixture()
        for change in (lambda c:c["training"].update(phase=7),lambda c:c["training"].update(course=True),
                       lambda c:c.update(training_role=4),lambda c:c["training"].update(quote={"role":"developer","rank":2,"course":1,"cost":20000})):
            bad=deepcopy(state);change(bad["campaign"])
            with self.assertRaises(GameError):RecoveredSession(catalog,bad)
        for change in (lambda r:r["skill_caps"].pop(),lambda r:r["course_gains"][0].append(1),
                       lambda r:r.update(level_gain=True),lambda r:r["level_caps"].__setitem__(0,91)):
            bad=deepcopy(catalog["training_rules"]);change(bad)
            with self.assertRaises(GameError):validate_training_rules(bad)


if __name__=="__main__":unittest.main()
