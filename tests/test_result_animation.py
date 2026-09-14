"""Atomic presentation cursors, migration and exact result continuation."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from test_strategy_session import battle_session
from openreunion.core import GameError
from openreunion.dos.session import RecoveredSession
from openreunion.dos.result_animation import validate_animation


def defeat():
    session=battle_session();session.apply('ground_start');session.apply('ground_command',command='retreat');return session


class ResultAnimationTests(unittest.TestCase):
    def test_cursor_advances_outside_gameplay_and_roundtrips_mid_cycle(self):
        s=defeat();state=deepcopy(s.state)
        for _ in range(18):s.tick_result_animation()
        self.assertEqual((s.result_animation['shown'],s.result_animation['counter']),(2,6))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.json';s.save(path);restored=RecoveredSession.load(s.catalog,path)
            self.assertTrue(restored.result_animation['paused']);restored.pause_result_animation(False)
            self.assertEqual(restored.result_animation,s.result_animation)
            for _ in range(81):
                self.assertEqual(restored.tick_result_animation(),s.tick_result_animation())
                self.assertEqual(restored.result_animation,s.result_animation)
        self.assertEqual(s.state,state);self.assertNotIn('result_animation',s.state)

    def test_pause_and_closed_results_never_advance_or_commit_twice(self):
        s=defeat();s.pause_result_animation();before=deepcopy(s.result_animation)
        for _ in range(20):self.assertFalse(s.tick_result_animation())
        self.assertEqual(s.result_animation,before)
        s.apply('ground_acknowledge');self.assertTrue(s.result_animation['paused'])
        with self.assertRaises(GameError):s.pause_result_animation(False)
        state=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply('ground_acknowledge')
        self.assertEqual(s.state,state);self.assertEqual(s.result_animation,before)

    def test_failed_gameplay_command_preserves_active_cursor_and_sound(self):
        s=defeat();s.tick_result_animation();before=deepcopy((s.state,s.result_animation,s.effects))
        with self.assertRaises(GameError):s.apply('ground_command',command='move')
        self.assertEqual((s.state,s.result_animation,s.effects),before)

    def test_invalid_metadata_cannot_replace_existing_save(self):
        s=defeat();value=deepcopy(s.result_animation)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'safe.json';s.save(path);before=path.read_bytes()
            for key,bad in (('version',True),('frame',0),('counter',14),('shown',2),('paused',1)):
                s.result_animation=dict(value);s.result_animation[key]=bad
                with self.assertRaises(GameError):s.save(path)
                self.assertEqual(path.read_bytes(),before)

    def test_v20_migrates_defeat_to_paused_initial_cursor_and_preserves_retreat_sound(self):
        s=defeat()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.json';s.save(path);payload=json.loads(path.read_text())
            payload.pop('result_animation');payload.pop('hero');payload['schema']='recovered-strategy-v20';path.write_text(json.dumps(payload))
            restored=RecoveredSession.load(s.catalog,path)
            self.assertEqual(restored.state,s.state);self.assertEqual(restored.effects,s.effects)
            self.assertEqual(restored.result_animation,dict(s.result_animation,paused=True))
            payload['schema']='recovered-strategy-v19';path.write_text(json.dumps(payload))
            with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)

    def test_animation_requires_matching_defeat_and_consistent_displayed_frame(self):
        s=defeat();value=s.result_animation;state=deepcopy(s.state)
        state['ground_encounter']['battle']['player_won']=True
        with self.assertRaises(GameError):validate_animation(value,state)
        state['ground_encounter']=None
        with self.assertRaises(GameError):validate_animation(value,state)

    def test_new_battle_dispatch_clears_previous_result_cursor(self):
        s=defeat();s.apply('ground_acknowledge');self.assertIsNotNone(s.result_animation)
        s.begin_ground_battle((1,5,1),player_attacking=True,conquering_owner=3)
        self.assertIsNone(s.result_animation)
        s.apply('ground_start');s.apply('ground_command',command='retreat')
        self.assertEqual(s.result_animation,{'version':1,'frame':2,'counter':1,'shown':1,'paused':False})
