"""Presentation timers cannot leak across pause, load or combat result."""
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
from test_battle_dispatch import ready
from test_control_layouts import layouts
from openreunion.dos.space_screen import SpaceScreen
from openreunion.dos.control_input import PanelPress


class Scheduler:
    def __init__(self):self.jobs={};self.index=0
    def after(self,delay,callback):
        self.index+=1;self.jobs[self.index]=callback;return self.index
    def after_cancel(self,key):self.jobs.pop(key,None)
    def fire(self,key):self.jobs.pop(key)()


def fixture():
    session=ready();session.apply('attack',fleet_index=0)
    session.catalog['control_layouts']=layouts()
    app=SimpleNamespace(session=session,catalog=session.catalog,root=Scheduler(),effects=Mock(),pointer=PanelPress(),
                        screen='space',original=SimpleNamespace(winfo_ismapped=lambda:True),
                        render_original=Mock(),refresh=Mock(),guard=lambda f:f())
    view=SpaceScreen(app);view.sync();return app,view


class SpaceScreenTests(unittest.TestCase):
    def test_old_callback_cannot_tick_or_replace_timer_after_pause_resume(self):
        app,view=fixture();view.toggle();old=app.root.jobs[view.timer]
        view.pause();view.toggle();current=view.timer
        with unittest.mock.patch.object(app.session,'apply',wraps=app.session.apply) as apply:
            old();apply.assert_not_called()
            self.assertEqual(view.timer,current)
            app.root.fire(current);apply.assert_called_once_with('space_tick',render=True)

    def test_load_invalidates_callback_and_stops_running(self):
        app,view=fixture();view.toggle();old=app.root.jobs[view.timer]
        app.session=ready();view.sync();old()
        self.assertFalse(view.running);self.assertIsNone(view.timer)
        self.assertFalse(view.active);self.assertEqual(app.root.jobs,{})

    def test_held_pointer_defers_timer_without_advancing_simulation(self):
        app,view=fixture();app.pointer.press(1,1,True);view.toggle()
        with unittest.mock.patch.object(app.session,'apply',wraps=app.session.apply) as apply:
            app.root.fire(view.timer);apply.assert_not_called()
            app.pointer.cancel(reset=True);app.root.fire(view.timer)
            apply.assert_called_once_with('space_tick',render=True)

    def test_result_fade_locks_continue_without_game_ticks_and_load_cancels(self):
        app,view=fixture();app.session.apply('space_retreat');view.sync()
        self.assertEqual(view.fade_step,0);self.assertFalse(view.enabled(65))
        self.assertFalse(view.enabled(62))
        with unittest.mock.patch.object(app.session,'apply',wraps=app.session.apply) as apply:
            while view.fade_timer is not None:app.root.fire(view.fade_timer)
            apply.assert_not_called()
        self.assertTrue(view.enabled(65))
        app.session=ready();view.sync()
        self.assertFalse(view.enabled(65));self.assertIsNone(view.fade_timer)

    def test_hidden_screen_stops_scheduling(self):
        app,view=fixture();view.toggle();app.screen='bridge'
        app.root.fire(view.timer)
        self.assertFalse(view.running);self.assertEqual(app.root.jobs,{})
