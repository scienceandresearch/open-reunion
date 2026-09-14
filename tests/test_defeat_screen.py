"""Terminal presentation must preserve results and cancel stale callbacks."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
from test_space_screen import Scheduler
from openreunion.dos.control_input import PanelPress
from openreunion.dos.defeat_screen import DefeatScreen
from openreunion.dos.defeat_cinema import defeat_cause


def fixture():
    state={'campaign_phase':'defeat','presentation_requests':[],
           'active_scene':None,'active_dialog':None,'space_encounter':None,
           'ground_encounter':None,'worlds':{'1:5:0':{'raw':[2]}}}
    session=SimpleNamespace(state=state,audio=None,defeated=lambda:True)
    app=SimpleNamespace(session=session,hero=2,root=Scheduler(),pointer=PanelPress(),
        screen='defeat',original=SimpleNamespace(winfo_ismapped=lambda:True),
        content=Mock(),music_panel=Mock(),render_original=Mock(),guard=lambda f:f())
    view=DefeatScreen(app);view.sync();return app,view


class DefeatScreenTests(unittest.TestCase):
    def test_music_pauses_resumes_restarts_and_respects_opt_out(self):
        app,view=fixture();view.music=Mock();view.music.playing=True
        app.session.audio={'track':'MAIN1','automatic':True}
        view.play();view.music.start.assert_called_once_with(app.content.module_music.return_value)
        view.pause();view.music.pause.assert_called_with(True)
        view.play();view.music.pause.assert_called_with(False)
        self.assertEqual(view.music.start.call_count,1)
        view.replay();self.assertEqual(view.music.start.call_count,2)
        view.pause();app.session.audio['automatic']=False;view.play()
        self.assertFalse(view.music_started);self.assertEqual(view.music.start.call_count,2)
        view.close();view.music.stop.assert_called()

    def test_loaded_result_starts_paused_live_result_autoplays_after_notices(self):
        app,view=fixture();self.assertFalse(view.running)
        state=app.session.state;state['presentation_requests']=[{'kind':'message','id':1}]
        self.assertFalse(view.sync());self.assertFalse(view.active)
        state['presentation_requests']=[]
        self.assertTrue(view.sync());self.assertTrue(view.active)
        self.assertFalse(view.sync())

    def test_pending_presentations_and_open_encounters_delay_film(self):
        app,view=fixture()
        for key,value in (('active_scene',{}),('active_dialog',{}),
                          ('space_encounter',{'phase':'result'}),('ground_encounter',{'phase':'result'})):
            app.session.state[key]=value;self.assertFalse(view.active,key)
            app.session.state[key]=None
        app.session.state['campaign_phase']='victory';self.assertFalse(view.active)

    def test_old_callback_cannot_advance_or_replace_resumed_timer(self):
        app,view=fixture();view.play();old=app.root.jobs[view.timer]
        view.pause();view.play();current=view.timer;old()
        self.assertEqual(view.position,0);self.assertEqual(view.timer,current)
        app.root.fire(current);self.assertEqual(view.position,1)
        view.pause();self.assertEqual(app.root.jobs,{})

    def test_load_and_hidden_window_cancel_callbacks(self):
        for reason in ('load','screen','unmap'):
            app,view=fixture();view.play();old=app.root.jobs[view.timer]
            if reason=='load':
                app.session=deepcopy(app.session);view.sync();old()
            else:
                if reason=='screen':app.screen='startup'
                else:app.original.winfo_ismapped=lambda:False
                app.root.fire(view.timer)
            self.assertFalse(view.running);self.assertEqual(view.position,0)
            self.assertEqual(app.root.jobs,{})

    def test_complete_and_replay_preserve_result_state(self):
        app,view=fixture();before=deepcopy(app.session.state);view.play()
        for _ in range(len(view.frames)):view.step()
        self.assertTrue(view.done);self.assertFalse(view.running)
        self.assertEqual(app.root.jobs,{})
        view.play();self.assertFalse(view.running)
        view.replay();self.assertTrue(view.running);self.assertEqual(view.position,0)
        self.assertEqual(app.session.state,before);view.pause()

    def test_defeat_notice_uses_retained_battle_result_or_home_owner(self):
        app,view=fixture();state=app.session.state
        self.assertEqual(defeat_cause(state),1)
        state['worlds']['1:5:0']['raw'][0]=0;self.assertEqual(defeat_cause(state),2)
        state['ground_encounter']={'phase':'closed','next_phase':'defeat'}
        self.assertEqual(defeat_cause(state),1)


if __name__=='__main__':unittest.main()
