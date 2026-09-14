"""Preserved destination rows, retrace boundaries and exact final reveal."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.assets import Picture
from openreunion.dos.control_wipe import wipe_steps,wipe_pictures


class ControlWipeTests(unittest.TestCase):
    def test_forward_and_backward_reveal_preserve_untouched_rows(self):
        source=b''.join(bytes([y+90])*320 for y in range(32));previous=bytes([17])*(320*32)
        steps=wipe_steps(source,previous)
        self.assertEqual(len(steps),32)
        self.assertEqual(steps[0][0],source[:320]+bytes([64])*320+previous[640:])
        self.assertEqual(steps[15][0],b''.join(source[y*320:y*320+320] if y%2==0 else bytes([64])*320 for y in range(32)))
        self.assertEqual(steps[16][0][-320:],source[-320:])
        self.assertEqual(steps[-2][0][320:640],bytes([64])*320)
        self.assertEqual(steps[-1][0],source)
        self.assertEqual([wait for _,wait in steps],[True,False]*16)
        self.assertEqual(source,b''.join(bytes([y+90])*320 for y in range(32)))

    def test_wait_visible_frames_include_the_cross_pass_boundary(self):
        source=b''.join(bytes([y])*320 for y in range(32));steps=wipe_steps(source,bytes([255])*10240)
        visible=[pixels for pixels,wait in steps if wait]+[steps[-1][0]]
        self.assertEqual(len(visible),17)
        self.assertEqual(visible[7][28*320:30*320],bytes([28])*320+bytes([64])*320)
        self.assertEqual(visible[7][-640:],bytes([255])*640)
        self.assertEqual(visible[8][-640:],source[-640:])

    def test_picture_palette_and_input_bounds(self):
        source=Picture(320,32,bytes(10240),bytes(range(256))*3)
        pictures=wipe_pictures(source,bytes([42])*10240)
        self.assertTrue(all(p.palette==source.palette and (p.width,p.height)==(320,32) for p,_ in pictures))
        for bad in (bytes(10239),bytes(10241),bytearray(10240),None):
            with self.assertRaises(GameError):wipe_steps(source.pixels,bad)
            with self.assertRaises(GameError):wipe_steps(bad,source.pixels)
        with self.assertRaises(GameError):wipe_pictures(Picture(320,31,bytes(9920),bytes(768)),bytes(10240))


if __name__=='__main__':unittest.main()
