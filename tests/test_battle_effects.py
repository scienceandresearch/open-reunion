"""Combat effects preserve simulation, saved cursors and legacy validation."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from test_space_session import prepared
from test_space_cinema import rules
from test_strategy_session import battle_session
from openreunion.core import GameError
from openreunion.dos.battle_samples import battle_effect_requests,battle_sample,sample_folder,EFFECT_SAMPLES
from openreunion.dos.effect_control import initial_effects
from openreunion.dos.session import RecoveredSession


class BattleEffectsTests(unittest.TestCase):
    def space(self):
        s=prepared();s.state['space_encounter']=None;s.catalog['space_cinema']=rules()
        s.begin_space_battle((1,5,1),player_attacking=True,ground_requested=True,conquering_owner=3)
        return s

    def test_ordered_combat_and_control_names_are_separate_from_other_events(self):
        self.assertEqual(battle_effect_requests('space_tick',[{'kind':'sound','id':45},{'kind':'space_frame'},
            {'kind':'sound','id':1}]),[('sound','WARSND45'),('sound','WARSND1')])
        self.assertEqual(battle_effect_requests('ground_tick',[{'kind':'ground_sound','id':11}]),[('sound','GRSND11')])
        self.assertEqual(battle_effect_requests('ground_command',[{'kind':'ground_cursor','id':5},
            {'kind':'ground_notice','id':30}]),[('sound','GRSND30')])
        self.assertEqual(battle_effect_requests('advance',[{'kind':'sound','id':1}]),[])
        self.assertEqual(len(set(EFFECT_SAMPLES)),68)
        for family,number in (('space',True),('space',46),('ground',12),('ground',0),('bad',1)):
            with self.assertRaises(GameError):battle_sample(family,number)
        with self.assertRaises(GameError):sample_folder('../WARSND1')

    def test_enabled_and_muted_space_combat_have_identical_events_and_rng(self):
        s=self.space();muted=RecoveredSession(s.catalog,deepcopy(s.state))
        muted.effects=initial_effects();muted.effects['enabled']=False
        seen=[]
        for _ in range(8):
            events=s.apply('space_tick');self.assertEqual(events,muted.apply('space_tick'))
            self.assertEqual(s.state,muted.state)
            for e in events:
                if e['kind']=='sound':seen.append(e['id']);self.assertEqual(s.effects['sample'],'WARSND'+str(e['id']))
        self.assertTrue(seen);self.assertIsNone(muted.effects['sample'])
        before=deepcopy(s.state),deepcopy(s.effects),s.effect_revision
        with self.assertRaises(GameError):s.apply('space_tick',frames=0)
        self.assertEqual((s.state,s.effects,s.effect_revision),before)

    def test_ground_frames_and_controls_use_same_committed_effect_channel(self):
        s=battle_session();s.apply('ground_start');seen=False
        # Invalid attack selection emits the recovered rejection sample, rather
        # than changing the selected group or consuming a random draw.
        seed=s.state['campaign']['rng'];s.apply('ground_command',command='attack')
        self.assertEqual(s.effects['sample'],'GRSND22');self.assertEqual(s.state['campaign']['rng'],seed)
        for _ in range(30):
            events=s.apply('ground_tick',frames=120)
            sounds=[e['id'] for e in events if e['kind']=='ground_sound']
            if sounds:
                self.assertEqual(s.effects['sample'],'GRSND'+str(sounds[-1]));seen=True;break
        self.assertTrue(seen)
        s.effects.update(frames=71,paused=True);before=deepcopy(s.effects),s.effect_revision
        with self.assertRaises(GameError):s.apply('ground_command',command='unknown')
        self.assertEqual((s.effects,s.effect_revision),before)

    def test_battle_cursor_roundtrip_does_not_replay_a_random_draw(self):
        s=self.space();s.apply('space_tick');s.effects.update(frames=777,paused=True)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'battle.json';s.save(path);restored=RecoveredSession.load(s.catalog,path)
            self.assertEqual(restored.effects,s.effects);self.assertEqual(restored.state,s.state)
            self.assertEqual(restored.effect_revision,0)
            self.assertEqual(restored.apply('space_tick',frames=3),s.apply('space_tick',frames=3))
            self.assertEqual(restored.state,s.state);self.assertEqual(restored.effects,s.effects)

    def test_v18_keeps_cinematic_effects_and_rejects_new_names(self):
        s=self.space();payload=deepcopy(s.state);payload.update(schema='recovered-strategy-v18',audio=None,effects=initial_effects())
        payload['effects'].update(sample='TRACTOR',frames=15,paused=True)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'v18.json';path.write_text(json.dumps(payload))
            restored=RecoveredSession.load(s.catalog,path)
            self.assertEqual(restored.state,s.state);self.assertEqual(restored.effects,payload['effects'])
            for name in ('WARSND1','GRSND22'):
                payload['effects']['sample']=name;path.write_text(json.dumps(payload))
                with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)

    def test_v19_preserves_battle_cursors_and_rejects_later_lifecycle_names(self):
        s=self.space();payload=deepcopy(s.state);payload.update(schema='recovered-strategy-v19',audio=None,effects=initial_effects())
        payload['effects'].update(sample='WARSND4',frames=78,paused=True)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'v19.json';path.write_text(json.dumps(payload))
            restored=RecoveredSession.load(s.catalog,path)
            self.assertEqual(restored.state,s.state);self.assertEqual(restored.effects,payload['effects'])
            for name in ('RETREAT','ENDBATTL'):
                payload['effects']['sample']=name;path.write_text(json.dumps(payload))
                with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)

    def test_retreat_and_exit_stage_named_sounds_once_without_changing_outcomes(self):
        for family in ('space','ground'):
            s=self.space() if family=='space' else battle_session()
            if family=='ground':s.apply('ground_start')
            s.effects=dict(initial_effects(),sample='WARSND4' if family=='space' else 'GRSND5',frames=71)
            action,args=('space_retreat',{}) if family=='space' else ('ground_command',{'command':'retreat'})
            events=s.apply(action,**args)
            self.assertEqual(battle_effect_requests(action,events),[('stop_sound',),('sound','RETREAT')])
            self.assertEqual(s.effects,dict(initial_effects(),sample='RETREAT'))
            self.assertEqual(s.effect_revision,2)
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'retreat.json';s.effects.update(frames=123,paused=True);s.save(path)
                restored=RecoveredSession.load(s.catalog,path)
                self.assertEqual(restored.effects,s.effects)
            state=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply(action,**args)
            self.assertEqual(s.state,state);self.assertEqual(s.effect_revision,2)
            s.apply(family+'_acknowledge')
            self.assertEqual(s.effects,dict(initial_effects(),sample='ENDBATTL'));self.assertEqual(s.effect_revision,4)
            state=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply(family+'_acknowledge')
            self.assertEqual(s.state,state);self.assertEqual(s.effect_revision,4)


if __name__=='__main__':unittest.main()
