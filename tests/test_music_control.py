from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from test_recovered import fixture
from openreunion.core import GameError
from openreunion.dos.session import RecoveredSession,SCHEMA
from openreunion.dos.music_control import (initial_audio,validate_audio,scene_music,
                                        select_music,main_music,restore_main,
                                        cinematic_track,screen_entry_music,screen_exit_music)
from openreunion.dos.fm_audio import FmRenderer
from test_fm_audio import FakeSynth
from test_fm_music import fixture as song_fixture,pack
from openreunion.dos.fm_music import decode_music


class MusicControlTests(unittest.TestCase):
    def test_cinematic_mapping_uses_original_scene_choices(self):
        self.assertEqual([cinematic_track(i) for i in range(1,7)],
                         ['atv1','atv5','atv2','atv5','atv4','atv3'])
        self.assertIsNone(cinematic_track(9))

    def test_requested_dialog_reloads_talk_but_ordinary_refresh_does_not(self):
        self.assertEqual(screen_entry_music(34,False,True,0,1,False),
                         (False,[('stop',1),('play',1,'talk')]))
        self.assertEqual(screen_entry_music(34,False,False,0,1,False),(False,[]))
        self.assertEqual(screen_entry_music(34,True,True,0,1,False),(False,[]))

    def test_exit_guards_distinguish_battle_handoff_from_main_return(self):
        self.assertEqual(screen_exit_music(29,32,True,1,False,2),(False,[]))
        self.assertEqual(screen_exit_music(29,7,True,1,True,2),
                         (True,[('stop',1),('play',1,'main2')]))
        self.assertEqual(screen_exit_music(34,34,True,1,False,2),(False,[]))
        self.assertEqual(screen_exit_music(34,7,False,1,False,2),(False,[]))

    def test_consecutive_dialog_revision_advances_only_after_valid_commit(self):
        from test_story_session import scripted
        session=scripted()
        session.state['presentation_requests'].append({'kind':'dialog','id':2})
        session.state['presentation_requests'].append({'kind':'dialog','id':2})
        session.apply('advance',hours=1)
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply('dialog_acknowledge')
        self.assertEqual(session.state,before);self.assertEqual(session.dialog_revision,0)
        session.apply('dialog_answer',question=5)
        self.assertEqual(session.dialog_revision,0)
        session.apply('dialog_acknowledge')
        self.assertEqual(session.dialog_revision,1)
        self.assertEqual(session.state['active_dialog']['script'],2)
        self.assertFalse(session.state['active_dialog']['closed'])
        self.assertNotIn('dialog_revision',session.state)

    def test_main_override_restarts_on_battle_exit_but_survives_dialog_exit(self):
        audio=initial_audio();audio.update(frames=54321,paused=True)
        battle,changed=scene_music(audio,'main',previous_scene='space')
        self.assertTrue(changed);self.assertEqual(battle['frames'],0);self.assertFalse(battle['paused'])
        talk,changed=scene_music(audio,'main',previous_scene='talk')
        self.assertFalse(changed);self.assertEqual(talk,audio)

    def test_off_main_still_allows_special_music_and_restores_stop(self):
        audio=initial_audio();audio['main']=0
        audio,_=scene_music(audio,'space');self.assertEqual(audio['track'],'SPACE')
        audio,_=scene_music(audio,'main');self.assertIsNone(audio['track'])
        self.assertEqual(main_music(1,False,0),(False,[('stop',1)]))
        self.assertEqual(restore_main(1,False,0),(True,[('stop',1)]))

    def test_restoration_does_not_restart_main_already_playing(self):
        audio=initial_audio();audio['frames']=12345
        next_audio,changed=scene_music(audio,'main')
        self.assertFalse(changed);self.assertEqual(next_audio,audio)
        self.assertEqual(restore_main(1,True,2),(True,[]))

    def test_backend_two_silence_and_case_sensitive_main_classification(self):
        self.assertEqual(main_music(2,False,0),(True,[('stop',2),('play',2,'no')]))
        self.assertFalse(select_music(1,True,'MAIN1')[0])

    def test_scene_change_resets_sample_clock_without_mutating_input(self):
        audio=initial_audio();audio.update(main=2,frames=5555,paused=True)
        before=deepcopy(audio);next_audio,_=scene_music(audio,'ground')
        self.assertEqual((next_audio['track'],next_audio['frames'],next_audio['paused']),('EARTH',0,False))
        self.assertEqual(audio,before)
        restored,_=scene_music(next_audio,'main');self.assertEqual(restored['track'],'MAIN2')

    def test_audio_roundtrip_is_in_same_json_but_outside_gameplay_state(self):
        catalog,state=fixture();session=RecoveredSession(catalog,state);session.audio=initial_audio()
        session.audio.update(track='TALK',scene='talk',frames=456789,paused=True)
        before=deepcopy(session.state)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'music.json';session.save(path)
            payload=json.loads(path.read_text());self.assertEqual(payload['audio'],session.audio)
            restored=RecoveredSession.load(catalog,path)
        self.assertEqual(restored.audio,session.audio);self.assertEqual(restored.state,before)
        self.assertNotIn('audio',restored.state)

    def test_v15_migrates_without_inventing_a_playback_position(self):
        catalog,state=fixture();state['schema']='recovered-strategy-v15';del state['active_scene']
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.json';path.write_text(json.dumps(state))
            restored=RecoveredSession.load(catalog,path)
        self.assertEqual(restored.state['schema'],SCHEMA);self.assertIsNone(restored.audio)

    def test_corrupt_audio_rejects_without_overwriting_existing_save(self):
        catalog,state=fixture();session=RecoveredSession(catalog,state)
        for field,value in (('frames',-1),('frames',True),('paused',1),('main',3),('track','../escape')):
            audio=initial_audio();audio[field]=value
            with self.assertRaises(GameError):validate_audio(audio)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'safe.json';session.save(path);before=path.read_bytes()
            session.audio=initial_audio();session.audio['frames']=-1
            with self.assertRaises(GameError):session.save(path)
            self.assertEqual(path.read_bytes(),before)

    def test_seek_can_be_cancelled_without_generating_rest_of_recording(self):
        renderer=FmRenderer(decode_music(pack(song_fixture())),synth=FakeSynth())
        self.assertFalse(renderer.seek(2**40,lambda:True));self.assertEqual(renderer.frames,0)
        self.assertTrue(renderer.seek(12345));self.assertEqual(renderer.frames,12345)
        with self.assertRaises(GameError):renderer.seek(12344)


if __name__=='__main__':unittest.main()
