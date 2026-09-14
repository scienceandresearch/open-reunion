"""Saved bar quotes, changing offers and clipped original sprite records."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_bar_dialogs import session_fixture,get_quote
from openreunion.dos.bar_screen import BarScreen,clipped_copy
from openreunion.dos.control_input import PanelPress
from openreunion.dos.session import RecoveredSession
from openreunion.dos.music_control import campaign_scene,scene_music,initial_audio


def fixture():
    session=session_fixture();get_quote(session)
    app=SimpleNamespace(session=session,catalog=session.catalog,pointer=PanelPress(),act=Mock(),render_original=Mock(),show_original=Mock())
    view=BarScreen(app);view.sync();return app,view


class BarScreenTests(unittest.TestCase):
    def test_bar_conversation_selects_talk_and_restores_main_after_leaving(self):
        app,view=fixture();self.assertEqual(campaign_scene(app.session.state),'talk')
        audio,changed=scene_music(initial_audio(),campaign_scene(app.session.state))
        self.assertTrue(changed);self.assertEqual(audio['track'],'TALK')
        app.session.apply('bar_leave');self.assertEqual(campaign_scene(app.session.state),'main')
        audio,changed=scene_music(audio,'main');self.assertTrue(changed);self.assertEqual(audio['track'],'MAIN1')

    def test_saved_quote_and_rendered_choices_do_not_mutate_session(self):
        app,view=fixture();before=deepcopy(app.session.state)
        rows=view.rows();self.assertTrue(rows);self.assertEqual(app.session.state,before)
        app.pointer.press(1,21,True);app.session=RecoveredSession(app.catalog,before);view.sync()
        self.assertFalse(app.pointer.buttons);self.assertEqual(view.rows(),rows)

    def test_changed_target_eligibility_cancels_held_response(self):
        app,view=fixture();app.session.state['campaign']['civilizations'][1][27]=2
        app.session.state['known_systems'][2]=1;view.sync();app.pointer.press(1,21,True)
        app.session.state['campaign']['civilizations'][1][27]=6;view.sync()
        self.assertFalse(app.pointer.buttons)

    def test_answer_and_leave_use_shared_commands(self):
        app,view=fixture();view.dispatch(('bar_choice',23));app.act.assert_called_once_with('bar_answer',question=23)
        app.act.reset_mock();app.session.apply('bar_answer',question=23);view.sync()
        self.assertTrue(view.reading);view.dispatch(('bar_choice',23));app.act.assert_not_called()
        view.dispatch(('bar_continue',));app.act.assert_called_once_with('bar_acknowledge')
        app.act.reset_mock();view.dispatch(24);app.act.assert_called_once_with('bar_leave')

    def test_sprite_copy_clips_original_extra_row_and_offscreen_edges(self):
        target=Mock();picture=SimpleNamespace(width=320,height=140)
        clipped_copy(target,picture,(281,60,38,140),(1,1,38,140),transparent=0)
        target.blit.assert_called_once_with(picture,281,60,source=(1,1,38,139),transparent=0)
        target.reset_mock();clipped_copy(target,picture,(-2,198,10,10),(0,0,10,10))
        target.blit.assert_called_once_with(picture,0,198,source=(2,0,8,2),transparent=None)
