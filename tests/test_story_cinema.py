"""Story deltas, script timing and original shared-controller semantics."""
from copy import deepcopy
import struct
import unittest

from openreunion.core import GameError
from openreunion.dos.story_cinema import (read_main_animation,draw_frame,validate_rules,
    initial_controller,select_animation,advance_animation,scene_script)
from openreunion.dos.campaign import random_bounded


def rules():
    return [dict(frames=3,width=3,height=1,x=0,y=0,rate=5,repeats=2) for _ in range(17)]


def frame(payload):
    return struct.pack('<H',len(payload))+b'SpidyAnim'+struct.pack('<HH',3,1)+payload


class StoryCinemaTests(unittest.TestCase):
    def test_delta_draw_preserves_previous_changes_instead_of_frame_one(self):
        data=frame(bytes([1,2,3]))+frame(bytes([0x81,9,0x81]))+frame(bytes([0x82,8]))
        frames,tail=read_main_animation(data,rules()[0]);self.assertEqual(tail,b'')
        first=draw_frame(frames,1,b'\0'*3);second=draw_frame(frames,2,first)
        self.assertEqual(draw_frame(frames,3,second),bytes([1,9,8]))
        self.assertEqual(draw_frame(frames,3,first),bytes([1,2,8]))

    def test_zero_frame_is_no_draw_and_unused_data_is_retained(self):
        data=frame(bytes([1,2,3]))+b'\0\0'+frame(bytes([0x83]))+b'unused'
        frames,tail=read_main_animation(data,rules()[0])
        self.assertIsNone(frames[1]);self.assertEqual(tail,b'unused')
        self.assertEqual(draw_frame(frames,2,b'abc'),b'abc')
        self.assertEqual(draw_frame(frames,3,b'xyz'),b'xyz')

    def test_malformed_frames_and_dimension_mismatch_reject(self):
        row=rules()[0]
        for data in (b'',frame(b'\xc0\0\0\x01'),frame(b'\x84'),frame(bytes([1,2,3]))[:-1]):
            with self.assertRaises(GameError):read_main_animation(data,row)
        wrong=frame(bytes([1,2,3])).replace(b'\x03\0\x01\0',b'\x01\0\x03\0',1)
        with self.assertRaises(GameError):read_main_animation(wrong+b'\0\0\0\0',row)

    def test_animation_selection_consumes_one_shared_rng_draw(self):
        before=initial_controller(1994);snapshot=deepcopy(before)
        after=select_animation(before,rules(),10);seed,roll=random_bounded(1994,200)
        self.assertEqual(after,dict(asset=10,frame=1,delay=100+roll,interval=1,repeats=2,rate=5,rng=seed))
        self.assertEqual(before,snapshot)

    def test_frame_driver_wraps_without_randomness_or_delay_consumption(self):
        state=select_animation(initial_controller(2),rules(),10);state['frame']=3
        updated=advance_animation(state,rules());self.assertEqual(updated,dict(state,frame=1))
        state['asset']=0;self.assertEqual(advance_animation(state,rules()),state)

    def test_satellite_script_sound_order_and_late_retrace_waits(self):
        table=rules();table[7]['frames']=6;table[8]['frames']=30
        script=scene_script(9,table)
        self.assertEqual([op for op in script if op[0]=='sound'],[('sound','satrobb1'),('sound','satrobb2'),('sound','satrobb3')])
        self.assertEqual(script.count(('wait',2)),6)
        self.assertEqual(script.count(('retrace',)),30)
        self.assertEqual(script.count(('wait',4)),2)
        self.assertEqual(script.count(('advance',)),36)

    def test_static_scene_waits_and_interactive_scene_retains_mouse_cycle(self):
        self.assertEqual(scene_script(3,rules()),[('input_wait',30000)])
        self.assertEqual(scene_script(1,rules()),[('init',),('select',10),('click_cycle',10),('close',)])
        self.assertEqual(scene_script(2,rules()).count(('advance',)),2)
        for scene in (0,11,True):
            with self.assertRaises(GameError):scene_script(scene,rules())

    def test_bad_table_types_and_offscreen_geometry_reject(self):
        validate_rules(rules())
        for field,value in (('frames',True),('width',321),('x',319),('repeats',-1)):
            table=rules();table[0][field]=value
            with self.assertRaises(GameError):validate_rules(table)
        with self.assertRaises(GameError):validate_rules(rules()[:-1])


if __name__=='__main__':unittest.main()
