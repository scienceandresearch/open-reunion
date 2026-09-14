"""Display restoration, frame bounds and deterministic snapshot rendering."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.assets import Picture
from openreunion.dos.scene_display import begin_display,fade_display,draw_display,finish_display,render_scene
from openreunion.dos.scene_playback import begin_scene,tick_scene
from test_story_cinema import rules


class Source:
    def __init__(self):self.catalog={'story_cinema':rules()};self.calls=0
    def indexed_picture(self,name):
        self.calls+=1
        return Picture(320,256,bytes([2])*64000+bytes([191])*17920,bytes([252])*768)
    def story_animation(self,asset,frame):return Picture(3,1,bytes([frame])*3,bytes([252])*768)


class SceneDisplayTests(unittest.TestCase):
    def setUp(self):
        self.source=Source();self.screen=bytes(i%256 for i in range(64000))
        self.palette=bytes([17])*768;self.hardware=bytes([29])*768

    def display(self):return begin_display(self.source.indexed_picture(''),self.screen,self.palette,hardware=self.hardware)

    def test_only_first_200_rows_load_and_old_hardware_survives_until_fade(self):
        display=self.display()
        self.assertEqual(display.pixels,bytes([66])*64000)
        self.assertEqual(display.target,bytes([17])*192+bytes([63])*576)
        self.assertEqual(display.palette,self.hardware)
        self.assertEqual(fade_display(display,0).palette,bytes(768))

    def test_exit_restores_only_saved_strip_and_logical_palette(self):
        original=self.display();drawn=draw_display(original,Picture(320,200,bytes([7])*64000,bytes(768)))
        result=finish_display(fade_display(drawn,0))
        expected=bytearray([71])*64000;expected[0x2800:0x3D40]=self.screen[0x2800:0x3D40]
        self.assertEqual(result.pixels,bytes(expected));self.assertEqual(result.target,self.palette)
        self.assertEqual(result.palette,bytes(768));self.assertEqual(original.pixels,bytes([66])*64000)

    def test_overlay_preserves_other_pixels_and_rejects_bad_bounds_atomically(self):
        original=self.display();picture=Picture(2,2,b'\x01\x02\x03\x04',bytes(768))
        result=draw_display(original,picture,x=318,y=198)
        self.assertEqual(result.pixels[-2:],b'\x43\x44');self.assertEqual(result.pixels[-322:-320],b'\x41\x42')
        self.assertEqual(result.pixels[:198*320],original.pixels[:198*320])
        for x,y in ((319,198),(318,199),(-1,0),(True,0)):
            with self.assertRaises(GameError):draw_display(original,picture,x=x,y=y)
        with self.assertRaises(GameError):draw_display(original,Picture(1,1,b'\xc0',bytes(768)))
        self.assertEqual(original.pixels,bytes([66])*64000)

    def test_snapshot_reconstruction_matches_incremental_display_without_rng_changes(self):
        table=self.source.catalog['story_cinema'];state=begin_scene(9,table,1994);display=self.display()
        while True:
            before=deepcopy(state)
            rebuilt=render_scene(self.source,state,pixels=self.screen,palette=self.palette,hardware=self.hardware)
            self.assertEqual(rebuilt,display);self.assertEqual(state,before)
            if state['phase']=='done':break
            state,events=tick_scene(state,table)
            for event in events:
                if event[0]=='fade':display=fade_display(display,event[1])
                elif event[0]=='frame':display=draw_display(display,self.source.story_animation(event[1],event[2]))
                elif event[0]=='done':display=finish_display(display)

    def test_invalid_snapshot_is_rejected_before_reading_assets(self):
        state=begin_scene(9,self.source.catalog['story_cinema'],1);state['pc']=999
        with self.assertRaises(GameError):render_scene(self.source,state,pixels=self.screen,palette=self.palette)
        self.assertEqual(self.source.calls,0)


if __name__=='__main__':unittest.main()
