"""Cinematics block campaign changes, retain ordering and survive atomic saves."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from test_story_session import scripted
from openreunion.core import GameError
from openreunion.dos.session import RecoveredSession,SCHEMA
from openreunion.dos.scene_playback import begin_scene,tick_scene


def finish(session):
    current=session.state['active_scene']
    if current['notice'] is not None:session.apply('scene_acknowledge')
    while session.state['active_scene']['playback']['phase']!='done':session.apply('scene_tick',key=True)
    session.apply('scene_acknowledge')


class SceneSessionTests(unittest.TestCase):
    def test_pending_notice_scene_dialog_are_consumed_in_call_order_without_clock_ticks(self):
        s=scripted();s.state['presentation_requests']=[{'kind':'message','id':3},{'kind':'scene','id':9},{'kind':'dialog','id':2}]
        date=deepcopy(s.state['date']);seed=s.state['campaign']['rng']
        s.apply('advance',hours=24);self.assertIsNone(s.state['active_scene']);self.assertIsNone(s.state['active_dialog'])
        before=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply('pause_research',paused=True)
        self.assertEqual(s.state,before)
        s.apply('dismiss_presentation');self.assertEqual(s.state['active_scene']['notice'],1)
        self.assertEqual(s.state['campaign']['rng'],seed)
        with self.assertRaises(GameError):s.apply('scene_tick')
        finish(s);self.assertEqual(s.state['active_dialog']['script'],2);self.assertEqual(s.state['date'],date)

    def test_each_saved_tick_commits_exactly_the_controller_rng_once(self):
        s=scripted();s.state['presentation_requests']=[{'kind':'scene','id':9}];s.apply('start_presentation');s.apply('scene_acknowledge')
        expected=begin_scene(9,s.catalog['story_cinema'],s.state['campaign']['rng']);date=deepcopy(s.state['date'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scene.json'
            while expected['phase']!='done':
                expected,events=tick_scene(expected,s.catalog['story_cinema'])
                self.assertEqual(s.apply('scene_tick'),events)
                self.assertEqual(s.state['campaign']['rng'],expected['controller']['rng'])
                self.assertEqual(s.state['active_scene']['playback'],expected);self.assertEqual(s.state['date'],date)
                s.save(path);s=RecoveredSession.load(s.catalog,path)
            seed=s.state['campaign']['rng'];self.assertEqual(s.apply('scene_tick'),[])
            s.apply('scene_acknowledge');self.assertEqual(s.state['campaign']['rng'],seed)

    def test_scene_four_notice_precedes_play_and_cannot_be_replayed(self):
        s=scripted();s.state['presentation_requests']=[{'kind':'scene','id':4}];s.apply('start_presentation')
        self.assertEqual(s.state['active_scene']['notice'],36)
        self.assertEqual(s.state['events'][-1]['id'],36)
        s.apply('scene_acknowledge');before=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply('scene_acknowledge')
        self.assertEqual(s.state,before);finish(s)

    def test_conversation_six_opens_only_after_tractor_scene_acknowledgement(self):
        s=scripted();s.catalog['dialogs']['6']=deepcopy(s.catalog['dialogs']['4']);s.catalog['dialogs']['6']['id']=6
        s.state['presentation_requests']=[{'kind':'dialog','id':6}];s.apply('start_presentation')
        self.assertIsNone(s.state['active_dialog']);self.assertEqual(s.state['active_scene']['dialog'],6)
        self.assertEqual(s.state['active_scene']['playback']['scene'],10)
        finish(s);self.assertEqual(s.state['active_dialog']['script'],6);self.assertIsNone(s.state['active_scene'])

    def test_mutations_and_malformed_inputs_preserve_active_scene(self):
        s=scripted();s.state['presentation_requests']=[{'kind':'scene','id':10}];s.apply('start_presentation');before=deepcopy(s.state)
        for action,args in (('advance',{'hours':1}),('scene_acknowledge',{}),('scene_tick',{'mouse':1}),('dismiss_presentation',{}),('research',{'product_id':1})):
            with self.assertRaises(GameError):s.apply(action,**args)
            self.assertEqual(s.state,before)
        s.admin_enabled=True;s.apply('admin',command='give credits 100')
        self.assertEqual(s.state['active_scene'],before['active_scene']);self.assertTrue(s.state['assisted'])

    def test_v16_migration_preserves_audio_and_rejects_smuggled_scene(self):
        from openreunion.dos.music_control import initial_audio
        s=scripted();state=deepcopy(s.state);state['schema']='recovered-strategy-v16';del state['active_scene']
        audio=initial_audio();audio.update(frames=12345,paused=True);state['audio']=audio
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.json';path.write_text(json.dumps(state),encoding='utf-8')
            loaded=RecoveredSession.load(s.catalog,path);self.assertEqual(loaded.state,s.state);self.assertEqual(loaded.audio,audio)
            state['active_scene']=None;path.write_text(json.dumps(state),encoding='utf-8')
            with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)

    def test_saved_rng_mismatch_or_missing_content_is_rejected(self):
        s=scripted();s.state['presentation_requests']=[{'kind':'scene','id':10}];s.apply('start_presentation')
        corrupt=deepcopy(s.state);corrupt['campaign']['rng']+=1
        with self.assertRaises(GameError):RecoveredSession(s.catalog,corrupt)
        catalog=deepcopy(s.catalog);del catalog['story_cinema']
        with self.assertRaises(GameError):RecoveredSession(catalog,s.state)

    def test_music_maps_cinematics_and_preserves_talk_through_conversation_prelude(self):
        from openreunion.dos.music_control import initial_audio,scene_music,campaign_scene
        audio=initial_audio()
        for scene,track in ((1,'ATV1'),(2,'ATV5'),(3,'ATV2'),(4,'ATV5'),(5,'ATV4'),(6,'ATV3')):
            selected,changed=scene_music(audio,'cinema'+str(scene));self.assertTrue(changed);self.assertEqual(selected['track'],track)
            restored,_=scene_music(selected,'main',previous_scene='cinema'+str(scene));self.assertEqual(restored['track'],'MAIN1')
        audio.update(frames=12345,paused=True)
        for scene in range(7,11):self.assertEqual(scene_music(audio,'cinema'+str(scene)),(audio,False))
        s=scripted();s.catalog['dialogs']['6']=deepcopy(s.catalog['dialogs']['4']);s.catalog['dialogs']['6']['id']=6
        s.state['presentation_requests']=[{'kind':'dialog','id':6}];s.apply('start_presentation')
        self.assertEqual(campaign_scene(s.state),'talk');finish(s);self.assertEqual(campaign_scene(s.state),'talk')

    def test_identical_queued_scenes_get_distinct_runtime_notifications(self):
        s=scripted();s.state['presentation_requests']=[{'kind':'scene','id':3}]*2;s.apply('start_presentation')
        self.assertEqual(s.scene_revision,1);finish(s);self.assertEqual(s.scene_revision,2)
        self.assertNotIn('scene_revision',s.state);finish(s);self.assertEqual(s.scene_revision,2)


if __name__=='__main__':unittest.main()
