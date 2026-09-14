"""Saved sound effects follow committed scene events, outside campaign RNG."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from test_story_session import scripted
from openreunion.core import GameError
from openreunion.dos.effect_control import initial_effects,scene_effects,validate_effects
from openreunion.dos.session import RecoveredSession,SCHEMA
from openreunion.dos.content import ContentSource


class EffectSessionTests(unittest.TestCase):
    def scene(self,number):
        s=scripted()
        for asset,frames in ((8,34),(9,41),(13,41)):s.catalog['story_cinema'][asset-1]['frames']=frames
        s.state['presentation_requests']=[{'kind':'scene','id':number}];s.apply('start_presentation')
        if s.state['active_scene']['notice'] is not None:s.apply('scene_acknowledge')
        return s

    def test_all_scene_sound_requests_commit_and_survive_file_roundtrip(self):
        for number,names in ((9,['SATROBB1','SATROBB2','SATROBB3']),(10,['TRACTOR',None])):
            s=self.scene(number);seen=[];date=deepcopy(s.state['date'])
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'effect.json'
                while s.state['active_scene']['playback']['phase']!='done':
                    events=s.apply('scene_tick')
                    for event in events:
                        if event[0] not in ('sound','stop_sound'):continue
                        seen.append(s.effects['sample']);self.assertEqual(s.effects['frames'],0)
                        if event[0]=='sound':s.effects.update(frames=123,paused=True)
                        s.save(path);restored=RecoveredSession.load(s.catalog,path)
                        self.assertEqual(restored.effects,s.effects);self.assertEqual(restored.state,s.state)
                        s=restored
                self.assertEqual(seen,names);self.assertEqual(s.state['date'],date)
                last=deepcopy(s.effects);s.apply('scene_acknowledge');self.assertEqual(s.effects,last)
                self.assertNotIn('effects',s.state)

    def test_failed_scene_action_preserves_effect_and_runtime_revision(self):
        s=self.scene(10);s.effects=initial_effects();s.effects.update(sample='TRACTOR',frames=71,paused=True)
        before=deepcopy(s.state),deepcopy(s.effects),s.effect_revision
        for action,args in (('scene_tick',{'key':1}),('scene_acknowledge',{}),('advance',{'hours':1})):
            with self.assertRaises(GameError):s.apply(action,**args)
            self.assertEqual((s.state,s.effects,s.effect_revision),before)

    def test_repeated_requests_restart_and_disabled_requests_stay_silent(self):
        value=initial_effects();value.update(sample='TRACTOR',frames=55,paused=True)
        result,revision=scene_effects(value,[('sound','tractor'),('sound','tractor')])
        self.assertEqual(revision,2);self.assertEqual(result['frames'],0);self.assertFalse(result['paused'])
        self.assertEqual(value['frames'],55)
        value=initial_effects();value['enabled']=False
        result,revision=scene_effects(value,[('sound','tractor')]);self.assertEqual(result,value);self.assertEqual(revision,1)
        result,_=scene_effects(None,[('sound','tractor'),('stop_sound',)])
        self.assertEqual(result,initial_effects())

    def test_v17_migration_keeps_scene_and_music_without_inventing_effects(self):
        s=self.scene(10);s.apply('scene_tick');state=deepcopy(s.state);state['schema']='recovered-strategy-v17';state['audio']=None
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.json';path.write_text(json.dumps(state))
            restored=RecoveredSession.load(s.catalog,path)
            self.assertEqual(restored.state,s.state);self.assertIsNone(restored.effects)
            state['effects']=initial_effects();path.write_text(json.dumps(state))
            with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)

    def test_bad_effect_fields_preserve_existing_save(self):
        s=scripted()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'safe.json';s.save(path);original=path.read_bytes()
            for key,value in (('frames',-1),('frames',True),('version',True),('sample','../BAD'),('paused',1),('enabled',1)):
                s.effects=initial_effects();s.effects[key]=value
                with self.assertRaises(GameError):s.save(path)
                self.assertEqual(path.read_bytes(),original)
            for update in ({'frames':1},{'paused':True},{'enabled':False,'sample':'TRACTOR'}):
                value=initial_effects();value.update(update)
                with self.assertRaises(GameError):validate_effects(value)

    def test_original_content_adapter_can_resume_modern_json(self):
        s=scripted();s.effects=initial_effects();s.effects.update(sample='TRACTOR',frames=99,paused=True)
        content=ContentSource.__new__(ContentSource);content.catalog=s.catalog;content.bundled=False
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'resume.json';s.save(path);restored=content.initial_session(path)
        self.assertEqual(restored.state,s.state);self.assertEqual(restored.effects,s.effects)


if __name__=='__main__':unittest.main()
