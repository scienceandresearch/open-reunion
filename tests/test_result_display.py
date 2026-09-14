"""Logical/device separation and reserved colors during the result fade."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.assets import Picture
from openreunion.dos.result_display import load_result_palette,fade_result_palette,begin_result_display,advance_result_display
from openreunion.dos.battle_results import result_palette


class ResultDisplayTests(unittest.TestCase):
    def test_result_viewport_fades_in_six_bit_space(self):
        picture=Picture(320,151,bytes(320*151),bytes([171])*768)
        for step in range(6):
            palette=result_palette(picture,step)
            self.assertEqual(palette[:3],bytes([(42*step//5)*255//63])*3)
            self.assertEqual(palette[186*3:187*3],bytes((v*step//5)*255//63 for v in (45,42,0)))
        self.assertEqual(result_palette(picture),result_palette(picture,5))

    def test_partial_picture_merge_preserves_reserved_and_low_colors(self):
        old=bytes((i*7+3)%64 for i in range(768));picture=bytes(range(256))*3
        merged=load_result_palette(picture,old)
        self.assertEqual(merged[:192],old[:192]);self.assertEqual(merged[723:],old[723:])
        self.assertEqual(merged[192:723],bytes(v>>2 for v in picture[:531]))

    def test_fade_preserves_hardware_outside_range_until_final_upload(self):
        target=bytes(i%64 for i in range(768));old=bytes([47])*768;hardware=old
        for step in range(5):
            hardware=fade_result_palette(target,hardware,step)
            self.assertEqual(hardware[:192],old[:192]);self.assertEqual(hardware[765:],old[765:])
            self.assertEqual(hardware[192:765],bytes(v*step//5 for v in target[192:765]))
        self.assertEqual(fade_result_palette(target,hardware,5),target)

    def test_display_has_six_updates_without_pixel_or_target_mutation(self):
        picture=Picture(320,151,bytes([186])*(320*151),bytes(768))
        target=bytes(i%64 for i in range(768));hardware=bytes([17])*768
        initial=begin_result_display(picture,target,hardware);display=initial
        for step in range(6):
            display=advance_result_display(display)
            self.assertEqual(display.step,step);self.assertEqual(display.pixels,bytes([250])*(320*151))
            self.assertEqual(display.target,target)
        self.assertEqual(initial.hardware,hardware);self.assertEqual(initial.step,-1)
        self.assertIs(advance_result_display(display),display)
        self.assertEqual(display.picture().rgb()[:3],bytes(v*255//63 for v in target[750:753]))

    def test_invalid_palette_and_step_rejected(self):
        for palette in (b'',bytes(767),bytes([64])*768,None):
            with self.assertRaises(GameError):load_result_palette(bytes(768),palette)
            with self.assertRaises(GameError):fade_result_palette(bytes(768),palette,1)
        for step in (-1,6,True):
            with self.assertRaises(GameError):fade_result_palette(bytes(768),bytes(768),step)


if __name__=='__main__':unittest.main()
