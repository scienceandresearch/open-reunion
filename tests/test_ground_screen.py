"""Ground combat and result timers retain session/pointer ownership."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest
from test_strategy_session import battle_session
from test_control_layouts import layouts
from test_space_screen import Scheduler
from openreunion.dos.control_input import PanelPress
from openreunion.dos.ground_screen import GroundScreen


def fixture():
    session=battle_session();session.apply('ground_start');session.catalog['control_layouts']=layouts()
    app=SimpleNamespace(session=session,catalog=session.catalog,root=Scheduler(),effects=Mock(),pointer=PanelPress(),
        screen='ground',original=SimpleNamespace(winfo_ismapped=lambda:True),render_original=Mock(),refresh=Mock(),guard=lambda f:f())
    view=GroundScreen(app);view.result_pixels=Mock();view.sync();return app,view


class GroundScreenTests(unittest.TestCase):
    def test_pause_resume_rejects_stale_callback_and_keeps_new_timer(self):
        app,view=fixture();view.toggle();old=app.root.jobs[view.timer]
        view.pause();view.toggle();current=view.timer
        with patch.object(app.session,'apply',wraps=app.session.apply) as apply:
            old();apply.assert_not_called();self.assertEqual(view.timer,current)
            app.root.fire(current);apply.assert_called_once_with('ground_tick')

    def test_result_animation_changes_only_presentation_and_stops_on_load(self):
        app,view=fixture();app.session.apply('ground_command',command='retreat');view.sync()
        self.assertFalse(view.enabled(65));before=deepcopy(app.session.state)
        while view.fade_timer is not None:app.root.fire(view.fade_timer)
        self.assertTrue(view.enabled(65));before_animation=dict(app.session.result_animation)
        for _ in range(14):app.root.fire(view.result_timer)
        self.assertEqual(app.session.state,before);self.assertNotEqual(before_animation,app.session.result_animation)
        callback=app.root.jobs[view.result_timer];app.session=battle_session();view.sync();callback()
        self.assertFalse(view.active);self.assertIsNone(view.result_timer);self.assertEqual(app.root.jobs,{})

    def test_changed_unit_state_cancels_held_targeting(self):
        app,view=fixture();app.pointer.press(1,24,True)
        app.session.state['ground_encounter']['battle']['selected_group']=1
        view.sync();self.assertFalse(app.pointer.buttons)

    def test_hidden_ground_screen_stops_combat_and_result_callbacks(self):
        app,view=fixture();view.toggle();app.screen='bridge';app.root.fire(view.timer)
        self.assertFalse(view.running);self.assertIsNone(view.timer)
        app.screen='ground';app.session.apply('ground_command',command='retreat');view.sync()
        app.screen='bridge';app.root.fire(view.result_timer)
        self.assertIsNone(view.result_timer);self.assertTrue(app.session.result_animation['paused'])
