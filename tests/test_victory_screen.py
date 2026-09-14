"""Victory must follow audio time without changing the completed campaign."""
from copy import deepcopy
from unittest.mock import Mock,patch
import unittest
from test_defeat_screen import fixture as defeat_fixture
from openreunion.dos.module_music import decode_module
from openreunion.dos.victory_screen import VictoryScreen


def fixture():
    app,old=defeat_fixture();old.close();app.screen='victory';app.session.state['campaign_phase']='victory'
    data=bytearray(1084+13*1024);data[950]=13;data[952:965]=bytes(range(13));data[1080:1084]=b'M.K.'
    app.content.module_music.return_value=decode_module(bytes(data))
    view=VictoryScreen(app);view.sync();return app,view


class VictoryScreenTests(unittest.TestCase):
    def test_audio_failure_falls_back_without_rewinding_the_film(self):
        app,view=fixture();view.music_started=True;view.music=Mock();view.music.error='Device lost'
        view.wall_start=1_000_000_000;view.base_elapsed=0;view.elapsed=2_000_000_000
        with patch('openreunion.dos.victory_screen.time.perf_counter_ns',return_value=2_000_000_000):
            self.assertEqual(view.current_time(),2_000_000_000)
        with patch('openreunion.dos.victory_screen.time.perf_counter_ns',return_value=4_000_000_000):
            self.assertEqual(view.current_time(),3_000_000_000)
        view.close()

    def test_loaded_victory_paused_pending_notice_blocks_and_live_ack_autoplays(self):
        app,view=fixture();self.assertTrue(view.active);self.assertFalse(view.running)
        app.session.state['presentation_requests']=[{'kind':'message','id':1}]
        self.assertFalse(view.sync());self.assertFalse(view.active)
        app.session.state['presentation_requests']=[]
        self.assertTrue(view.sync());self.assertFalse(view.sync())

    def test_audio_position_selects_visual_time_without_campaign_ticks(self):
        app,view=fixture();before=deepcopy(app.session.state)
        app.session.audio={'track':'MAIN1','automatic':True}
        view.music=Mock();view.music.error=None;view.music.position.return_value=48000*30
        view.play();app.root.fire(view.timer)
        self.assertEqual(view.elapsed,30_000_000_000)
        self.assertGreater(view.position,1);self.assertEqual(app.session.state,before)
        view.close();self.assertEqual(app.root.jobs,{})

    def test_muted_clock_pauses_and_stale_callback_cannot_resume(self):
        app,view=fixture()
        with patch('openreunion.dos.victory_screen.time.perf_counter_ns',return_value=1_000_000_000):view.play()
        old=app.root.jobs[view.timer]
        with patch('openreunion.dos.victory_screen.time.perf_counter_ns',return_value=2_000_000_000):view.pause()
        self.assertEqual(view.elapsed,1_000_000_000)
        with patch('openreunion.dos.victory_screen.time.perf_counter_ns',return_value=3_000_000_000):view.play()
        current=view.timer;old();self.assertEqual(view.timer,current)
        with patch('openreunion.dos.victory_screen.time.perf_counter_ns',return_value=3_000_000_000):view.close()

    def test_load_invalidates_audio_and_film_and_completion_preserves_result(self):
        app,view=fixture();before=deepcopy(app.session.state);view.play();old=app.root.jobs[view.timer]
        app.session=deepcopy(app.session);view.sync();old()
        self.assertFalse(view.running);self.assertEqual(view.position,0);self.assertEqual(app.root.jobs,{})
        while not view.done:view.step()
        self.assertEqual(view.elapsed,view.duration);self.assertEqual(app.session.state,before)
        view.replay();self.assertEqual(view.position,0);self.assertEqual(view.elapsed,0);view.close()


if __name__=='__main__':unittest.main()
