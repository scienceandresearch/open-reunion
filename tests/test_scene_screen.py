"""Main story callbacks belong to a particular session and presentation entry."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from test_story_session import scripted
from test_scene_display import Source
from test_space_screen import Scheduler
from openreunion.dos.control_input import PanelPress
from openreunion.dos.scene_screen import SceneScreen
from openreunion.dos.session import RecoveredSession


def fixture():
    session=scripted();source=Source();source.prepare_story_scene=Mock()
    session.catalog['story_cinema']=source.catalog['story_cinema']
    session.state['presentation_requests']=[{'kind':'scene','id':3}];session.apply('start_presentation')
    app=SimpleNamespace(session=session,content=source,root=Scheduler(),effects=Mock(),pointer=PanelPress(),
        screen='scene',original=SimpleNamespace(winfo_ismapped=lambda:True,focus_set=lambda:None),
        render_original=Mock(),guard=lambda f:f(),act=Mock())
    view=SceneScreen(app);view.sync();return app,view


class SceneScreenTests(unittest.TestCase):
    def test_pause_resume_rejects_old_callback_without_clearing_new_job(self):
        app,view=fixture();view.play();old=app.root.jobs[view.timer]
        view.mouse=True;view.key_pending=True;view.pause();view.play();current=view.timer
        self.assertFalse(view.mouse or view.key_pending)
        with patch.object(app.session,'apply',wraps=app.session.apply) as apply:
            old();apply.assert_not_called();self.assertEqual(view.timer,current)
            app.root.fire(current);apply.assert_called_once_with('scene_tick',mouse=False,key=False)

    def test_identical_load_and_repeated_scene_entry_invalidate_timer(self):
        app,view=fixture();view.play();old=app.root.jobs[view.timer]
        app.session=RecoveredSession(app.session.catalog,deepcopy(app.session.state));view.sync();old()
        self.assertFalse(view.running);self.assertEqual(app.root.jobs,{})
        view.play();old=app.root.jobs[view.timer];before=deepcopy(app.session.state)
        app.session.scene_revision+=1;old()
        self.assertEqual(app.session.state,before);self.assertFalse(view.running)

    def test_hidden_view_stops_without_advancing_and_rebuild_is_read_only(self):
        app,view=fixture();view.play();before=deepcopy(app.session.state)
        app.original.winfo_ismapped=lambda:False;app.root.fire(view.timer)
        self.assertEqual(app.session.state,before);self.assertEqual(app.root.jobs,{})
        view.snapshot=None;view.sync();self.assertEqual(app.session.state,before)

    def test_continue_cannot_skip_unfinished_scene(self):
        app,view=fixture();view.acknowledge();app.act.assert_not_called()
        while app.session.state['active_scene']['playback']['phase']!='done':app.session.apply('scene_tick',key=True)
        view.sync();before=deepcopy(app.session.state);view.acknowledge()
        app.act.assert_called_once_with('scene_acknowledge');self.assertEqual(app.session.state,before)

    def test_identical_queued_notices_invalidate_held_continue(self):
        app,view=fixture();app.session.state['active_scene']=None
        app.session.state['presentation_requests']=[{'kind':'message','id':3},{'kind':'message','id':3}]
        view.sync();app.pointer.press(1,1,True)
        app.session.apply('dismiss_presentation');view.sync()
        self.assertTrue(view.notice);self.assertFalse(app.pointer.buttons)

    def test_report_changes_and_scrolling_invalidate_held_continue(self):
        app,view=fixture();app.session.state['active_scene']=None
        app.session.state['presentation_requests']=[{'kind':'report','id':1,'report':['First intelligence report']}]
        view.sync();app.pointer.press(1,1,True)
        app.session.state['presentation_requests'][0]['report']=['Updated intelligence report']
        view.sync();self.assertFalse(app.pointer.buttons)
        self.assertEqual(view.lines(),['Updated intelligence report'])
        app.pointer.press(1,1,True);before=deepcopy(app.session.state);view.scroll(5)
        self.assertFalse(app.pointer.buttons);self.assertEqual(app.session.state,before)
