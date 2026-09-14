"""Saved university quotes and adviser screen invalidation without Tk assets."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_recovered import fixture
from test_advice import rules
from openreunion.dos.session import RecoveredSession
from openreunion.dos.adviser_screen import AdviserScreen
from openreunion.dos.control_input import PanelPress


def app_fixture(role='pilot'):
    catalog,state=fixture();catalog['commander_advice']=rules();state['resources']['credits']=120000
    session=RecoveredSession(catalog,state);session.apply('hire',role=role,rank=1)
    texts={'KERDES1.SP':[f'Question {i}' for i in range(1,12)],'RKERDES1.SP':[f'Choice {i}' for i in range(1,12)],
           'VALASZ1.SP':[f'01 Reply {i}' for i in range(1,16)]}
    app=SimpleNamespace(session=session,catalog=catalog,content=SimpleNamespace(text=lambda n:texts[n]),pointer=PanelPress(),
                        show_original=Mock(),render_original=Mock(),clock_panel=SimpleNamespace(clock=Mock()))
    view=AdviserScreen(app)
    def act(action,**kwargs):
        result=app.session.apply(action,**kwargs);view.sync();return result
    app.act=Mock(side_effect=act);view.open(role);return app,view


class AdviserScreenTests(unittest.TestCase):
    def test_advice_uses_shared_reply_and_unoffered_question_is_ignored(self):
        app,view=app_fixture();reference=RecoveredSession(app.catalog,app.session.state)
        expected=reference.apply('consult_commander',role='pilot',question=3)[0]
        view.dispatch(('adviser_choice',3));self.assertEqual(app.session.state,reference.state)
        self.assertEqual(view.answer,expected['answer']);before=deepcopy(app.session.state)
        view.dispatch(('adviser_choice',6));self.assertEqual(app.session.state,before)

    def test_saved_quote_reopens_without_another_random_draw_or_purchase(self):
        app,view=app_fixture();view.dispatch(('adviser_choice',5));before=deepcopy(app.session.state)
        app.pointer.press(1,21,True);app.session=RecoveredSession(app.catalog,before);view.sync()
        self.assertFalse(view.active);self.assertFalse(app.pointer.buttons)
        view.open('pilot');self.assertEqual(view.menu,2);self.assertEqual(app.session.state,before)
        view.dispatch(('adviser_choice',7));self.assertEqual(app.session.state,before);self.assertEqual(view.menu,1)

    def test_developer_course_and_accept_keep_exact_quote_and_duration(self):
        for course in range(1,5):
            app,view=app_fixture('developer');reference=RecoveredSession(app.catalog,app.session.state)
            view.dispatch(('adviser_choice',5));self.assertEqual(view.menu,3);self.assertEqual(app.session.state,reference.state)
            view.dispatch(('adviser_choice',7+course));reference.apply('quote_training',role='developer',course=course)
            self.assertEqual(app.session.state,reference.state)
            view.dispatch(('adviser_choice',6));reference.apply('train')
            self.assertEqual(app.session.state,reference.state);self.assertFalse(view.active)

    def test_insufficient_money_cap_and_busy_university_do_not_mutate_campaign(self):
        app,view=app_fixture();view.dispatch(('adviser_choice',5));app.session.state['resources']['credits']=0;view.sync()
        before=deepcopy(app.session.state);view.dispatch(('adviser_choice',6))
        self.assertEqual(app.session.state,before);self.assertEqual(view.answer,'Reply 12')
        app.session.state['levels']['pilot']=30;before=deepcopy(app.session.state);view.dispatch(('adviser_choice',5))
        self.assertEqual(app.session.state,before);self.assertEqual(view.answer,'Reply 15')
        app.session.state['campaign']['training_role']=2;before=deepcopy(app.session.state);view.dispatch(('adviser_choice',5))
        self.assertEqual(app.session.state,before);self.assertEqual(view.answer,'Reply 9')

    def test_rank_change_and_changed_quote_cancel_held_input(self):
        app,view=app_fixture();view.dispatch(('adviser_choice',5));app.pointer.press(1,21,True)
        app.session.apply('quote_training',role='pilot');view.sync();self.assertFalse(app.pointer.buttons)
        app.pointer.press(1,21,True);app.session.apply('hire',role='pilot',rank=2);view.sync()
        self.assertFalse(view.active);self.assertFalse(app.pointer.buttons)


if __name__=='__main__':unittest.main()
