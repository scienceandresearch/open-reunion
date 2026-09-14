from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

from openreunion.core import GameError
from openreunion.dos.scene_effects import load_scene_palette,fade_updates,dac_rgb,start_input_wait,step_input_wait
from openreunion.dos.scene_playback import begin_scene,tick_scene,validate_scene
from test_story_cinema import rules


class SceneEffectsTests(unittest.TestCase):
    def test_picture_palette_quantizes_into_64_through_255(self):
        original=bytes(range(256))*3;current=bytes([17])*768
        result=load_scene_palette(original,current)
        self.assertEqual(result[:192],current[:192]);self.assertEqual(result[192:],bytes(v>>2 for v in original[:576]))

    def test_fade_uses_six_integer_levels_and_full_final_inward_write(self):
        target=bytes([63])*768;updates=fade_updates(target,start=64,end=65)
        self.assertEqual([entry[3][0] for entry in updates if entry[0]=='palette'],[0,12,25,37,50,63,63])
        self.assertEqual(updates[-1],('palette',0,255,target))
        self.assertEqual(fade_updates(target,inward=False)[-1],('palette',0,255,bytes(768)))
        self.assertEqual(dac_rgb(target),bytes([255])*768)

    def test_held_mouse_must_release_then_press(self):
        state=start_input_wait(20,mouse=True)
        state=step_input_wait(state,mouse=True);self.assertFalse(state['done'])
        state=step_input_wait(state,mouse=False);self.assertEqual(state['phase'],'press')
        state=step_input_wait(state,mouse=True);self.assertTrue(state['done']);self.assertEqual(state['elapsed'],3)

    def test_key_during_wait_finishes_immediately_in_corrected_mode(self):
        state=start_input_wait(30000)
        legacy=step_input_wait(state,key=True,legacy_keyboard=True)
        fixed=step_input_wait(state,key=True)
        self.assertFalse(legacy['done']);self.assertTrue(fixed['done']);self.assertEqual(fixed['elapsed'],1)
        self.assertTrue(start_input_wait(30000,key_seen=True)['done'])

    def test_invalid_fade_inputs_reject(self):
        for arguments in ({'steps':0},{'start':-1},{'end':256},{'inward':1}):
            with self.assertRaises(GameError):fade_updates(bytes(768),**arguments)
        with self.assertRaises(GameError):dac_rgb(bytes([64])*768)

    def test_scene_json_resume_has_identical_remaining_frames_and_rng(self):
        table=rules();state=begin_scene(9,table,1994)
        for _ in range(8):state,_=tick_scene(state,table)
        resumed=json.loads(json.dumps(state));original=deepcopy(state)
        while state['phase']!='done':
            state,events=tick_scene(state,table);resumed,again=tick_scene(resumed,table)
            self.assertEqual(events,again);self.assertEqual(state,resumed)
        self.assertNotEqual(state['controller']['rng'],original['controller']['rng'])
        self.assertEqual(tick_scene(state,table),(state,[]))

    def test_each_animation_selection_consumes_rng_once_after_fade(self):
        table=rules();state=begin_scene(10,table,1994)
        for _ in range(5):state,_=tick_scene(state,table);self.assertEqual(state['controller']['rng'],1994)
        state,events=tick_scene(state,table);self.assertIn(('select',13),events)
        seed=state['controller']['rng']
        while state['phase']!='done':state,_=tick_scene(state,table);self.assertEqual(state['controller']['rng'],seed)

    def test_corrupt_scene_snapshot_rejects_without_mutating_input(self):
        table=rules();state=begin_scene(1,table,1)
        for key,value in (('pc',1000),('ticks',True),('fade_step',6),('phase','unknown')):
            corrupt=deepcopy(state);corrupt[key]=value;before=deepcopy(corrupt)
            with self.assertRaises(GameError):tick_scene(corrupt,table)
            self.assertEqual(corrupt,before)
        state,_=tick_scene(state,table)
        validate_scene(state,table)


if __name__=='__main__':unittest.main()
