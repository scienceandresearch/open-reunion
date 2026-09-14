"""Presentation lifecycle independent of Tk and a physical audio device."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_story_session import scripted
from openreunion.core import GameError
from openreunion.dos.effect_control import initial_effects
from openreunion.dos.effect_output import EffectOutput
from openreunion.dos.samples import Sample


class Player:
    def __init__(self):self.playing=False;self.paused=False;self.completed=False;self.error=None;self.frames=0;self.starts=[]
    def start(self,sample,*,frames=0,paused=False):
        self.starts.append((frames,paused));self.frames=frames;self.paused=paused
        self.completed=frames==sample.frames();self.playing=not self.completed
    def pause(self,value):self.paused=value
    def position(self):return self.frames
    def stop(self):self.playing=False


class EffectOutputTests(unittest.TestCase):
    def setUp(self):
        self.app=SimpleNamespace(session=scripted(),refresh_listeners=[],
            root=SimpleNamespace(bind=lambda *a,**k:None,after=lambda *a:1,after_cancel=lambda *a:None),
            status=SimpleNamespace(set=lambda s:None),content=SimpleNamespace(sample=lambda n:Sample(156,b'\x80'*200)))
        with patch('openreunion.dos.effect_output.SamplePlayer',Player):self.output=EffectOutput(self.app)
        self.addCleanup(self.output.close)

    def trigger(self,name='TRACTOR'):
        self.app.session.effects=initial_effects();self.app.session.effects['sample']=name
        self.app.session.effect_revision+=1;self.output.sync()

    def test_same_name_restarts_once_per_revision_but_refresh_does_not(self):
        self.trigger();self.output.player.frames=123
        for _ in range(3):self.output.sync()
        self.assertEqual(len(self.output.player.starts),1)
        self.trigger();self.assertEqual(len(self.output.player.starts),2);self.assertEqual(self.output.player.frames,0)

    def test_suspend_releases_device_and_reopens_from_consumed_position(self):
        self.trigger();self.output.player.frames=123;before=deepcopy(self.app.session.state)
        self.output.suspend();self.assertFalse(self.output.player.playing)
        self.assertEqual(self.app.session.effects['frames'],123);self.assertTrue(self.app.session.effects['paused'])
        self.output.resume();self.assertEqual(self.output.player.starts[-1],(123,False))
        self.assertEqual(self.app.session.state,before)

    def test_new_loaded_scene_starts_paused_and_eof_does_not_restart(self):
        self.trigger();new=scripted();new.state['presentation_requests']=[{'kind':'scene','id':10}];new.apply('start_presentation')
        new.effects=initial_effects();new.effects.update(sample='TRACTOR',frames=55)
        self.app.session=new;self.output.sync();self.assertEqual(self.output.player.starts[-1],(55,True))
        self.output.player.completed=True;self.output.player.playing=False;self.output.player.frames=960
        self.output.capture();count=len(self.output.player.starts);self.output.resume()
        self.assertEqual(len(self.output.player.starts),count);self.assertEqual(new.effects['frames'],960)

    def test_missing_sample_is_reported_and_retry_preserves_offset(self):
        self.app.content.sample=lambda name:(_ for _ in ()).throw(GameError('missing sound'))
        self.trigger();self.assertEqual(self.output.error,'missing sound');self.assertFalse(self.output.player.playing)
        self.app.content.sample=lambda name:Sample(156,b'\x80'*200)
        self.app.session.effects['frames']=17;self.output.resume()
        self.assertIsNone(self.output.error);self.assertEqual(self.output.player.starts[-1],(17,False))

    def test_device_failure_preserves_last_consumed_cursor_for_retry(self):
        self.trigger();self.output.player.frames=73;self.output.player.error='disconnected';self.output.poll()
        self.assertEqual(self.app.session.effects['frames'],73);self.assertTrue(self.app.session.effects['paused'])
        self.output.resume();self.assertEqual(self.output.player.starts[-1],(73,False))

    def test_prepare_rejects_out_of_sample_resume_without_changing_session(self):
        self.trigger();before=self.app.session
        candidate=scripted();candidate.effects=initial_effects();candidate.effects.update(sample='TRACTOR',frames=961)
        with self.assertRaises(GameError):self.output.prepare(candidate)
        self.assertIs(self.app.session,before);self.assertTrue(self.output.player.playing)

    def test_disable_stops_and_clears_saved_voice_without_retroactive_play(self):
        self.trigger();self.output.set_enabled(False)
        self.assertFalse(self.output.player.playing);self.assertIsNone(self.app.session.effects['sample'])
        count=len(self.output.player.starts);self.output.set_enabled(True)
        self.assertEqual(len(self.output.player.starts),count)

    def test_battle_routing_and_loaded_battle_pause_preserve_cursor(self):
        calls=[]
        def sample(name,folder='SOUND'):
            calls.append((name,folder));return Sample(156,b'\x80'*200)
        self.app.content.sample=sample
        self.trigger('WARSND45');self.trigger('GRSND22');self.trigger('TRACTOR')
        self.assertEqual(calls,[('WARSND45','SOUND2'),('GRSND22','SOUND3'),('TRACTOR','SOUND')])
        new=scripted();new.state['ground_encounter']={'phase':'fighting'}
        new.effects=initial_effects();new.effects.update(sample='GRSND22',frames=45)
        self.app.session=new;self.output.sync()
        self.assertEqual(self.output.player.starts[-1],(45,True))
        self.assertEqual(len(calls),3,'Repeated battle sample should use the bounded name cache')

    def test_missing_numbered_replacement_preserves_voice_without_stop_or_restart(self):
        self.app.content.sample=lambda *args:Sample(156,b'\x80'*200)
        self.trigger('WARSND1');self.output.player.frames=83;state=deepcopy(self.app.session.state)
        self.app.content.sample=lambda *args:(_ for _ in ()).throw(OSError('missing battle file'))
        with patch.object(self.output.player,'stop',wraps=self.output.player.stop) as stop:
            self.trigger('WARSND2');self.assertFalse(stop.called)
        self.assertEqual(self.app.session.effects,dict(initial_effects(),sample='WARSND1',frames=83))
        self.assertTrue(self.output.player.playing);self.assertEqual(len(self.output.player.starts),1)
        self.assertIsNone(self.output.error);self.assertEqual(self.output.warning,'missing battle file')
        self.assertEqual(self.app.session.state,state)
        self.output.player.frames=123;self.output.pause()
        self.assertEqual(self.app.session.effects['frames'],123);self.assertTrue(self.app.session.effects['paused'])
        self.output.resume();self.assertEqual(len(self.output.player.starts),1)
        # Redraw/resume does not retry the missing request. A new request does.
        self.app.content.sample=lambda *args:Sample(156,b'\x80'*200)
        self.trigger('WARSND2');self.assertEqual(len(self.output.player.starts),2)
        self.assertEqual(self.app.session.effects['sample'],'WARSND2');self.assertIsNone(self.output.warning)

    def test_missing_numbered_request_preserves_suspended_and_completed_voices(self):
        for complete in (False,True):
            self.app.content.sample=lambda *args:Sample(156,b'\x80'*200)
            self.trigger('GRSND1');self.output.player.frames=960 if complete else 31
            self.output.player.completed=complete
            if complete:self.output.player.playing=False
            else:self.output.suspend()
            self.output.capture();expected=deepcopy(self.app.session.effects)
            self.app.content.sample=lambda *args:(_ for _ in ()).throw(GameError('bad sample'))
            self.trigger('GRSND2');self.assertEqual(self.app.session.effects,expected)
            count=len(self.output.player.starts);self.output.resume()
            self.assertEqual(len(self.output.player.starts),count if complete else count+1)

    def test_missing_initial_battle_request_does_not_leak_another_sessions_voice(self):
        self.app.content.sample=lambda *args:(_ for _ in ()).throw(GameError('missing sample'))
        self.trigger('WARSND1');self.assertEqual(self.app.session.effects,initial_effects())
        self.assertIsNone(self.output.error);self.assertFalse(self.output.player.playing)
        self.app.content.sample=lambda *args:Sample(156,b'\x80'*200);self.trigger('WARSND1')
        new=scripted();new.effects=dict(initial_effects(),sample='GRSND1',frames=32)
        self.app.session=new
        self.app.content.sample=lambda *args:(_ for _ in ()).throw(GameError('missing new session sample'))
        self.output.sync();self.assertFalse(self.output.player.playing)
        self.assertEqual(new.effects['sample'],'GRSND1');self.assertEqual(new.effects['frames'],32)
        self.assertIsNotNone(self.output.error)

    def test_cached_same_number_restarts_even_when_file_is_no_longer_available(self):
        self.app.content.sample=lambda *args:Sample(156,b'\x80'*200)
        self.trigger('WARSND1');self.output.player.frames=92
        self.app.content.sample=lambda *args:(_ for _ in ()).throw(GameError('missing cached file'))
        self.trigger('WARSND1');self.assertEqual(self.output.player.starts[-1],(0,False))
        self.assertEqual(len(self.output.player.starts),2);self.assertIsNone(self.output.warning)

    def test_missing_named_retreat_stops_prior_voice_like_original_named_loader(self):
        self.app.content.sample=lambda *args:Sample(156,b'\x80'*200)
        self.trigger('WARSND1')
        self.app.content.sample=lambda *args:(_ for _ in ()).throw(GameError('missing retreat'))
        self.trigger('RETREAT')
        self.assertFalse(self.output.player.playing);self.assertEqual(self.output.error,'missing retreat')
        self.assertEqual(self.app.session.effects['sample'],'RETREAT');self.assertIsNone(self.output._voice)

    def test_return_to_previous_number_reads_again_and_preserves_current_on_failure(self):
        calls=[]
        def sample(name,folder='SOUND'):
            calls.append((name,folder));return Sample(156,b'\x80'*200)
        self.app.content.sample=sample
        self.trigger('WARSND1');self.trigger('WARSND2');self.trigger('WARSND1')
        self.assertEqual(calls,[('WARSND1','SOUND2'),('WARSND2','SOUND2'),('WARSND1','SOUND2')])
        self.output.player.frames=66
        self.app.content.sample=lambda *args:(_ for _ in ()).throw(GameError('previous file removed'))
        self.trigger('WARSND2')
        self.assertEqual(self.app.session.effects['sample'],'WARSND1')
        self.assertEqual(self.output.player.frames,66)
        self.assertEqual(len(self.output.player.starts),3)


if __name__=='__main__':unittest.main()
