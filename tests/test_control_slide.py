"""Slide endpoint safety and reference timing around inactive scanlines."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.control_slide import slide_rows,validate_steps,PageClock

STEPS=[1,1,1,1,1,2,2,2,2,2,3,2,2,2,2,2,1,1,1,1,1]


class ControlSlideTests(unittest.TestCase):
    def test_directional_copy_order_and_endpoints(self):
        self.assertEqual(slide_rows(STEPS,0),(1,2,3,4,5,6,8,10,12,14,16,19,21,23,25,27,29,30,31,32,33))
        self.assertEqual(slide_rows(STEPS,1),(32,31,30,29,28,26,24,22,20,18,15,13,11,9,7,5,4,3,2,1,0))
        self.assertNotEqual(slide_rows(STEPS,0),slide_rows(STEPS,1)[::-1])

    def test_invalid_table_cannot_crop_outside_the_panel(self):
        for steps in (None,STEPS[:-1],[1]*21,[True]+STEPS[1:],[0]+STEPS[1:],STEPS[:-1]+[2]):
            with self.assertRaises(GameError):validate_steps(steps)
        for page in (-1,2,True):
            with self.assertRaises(GameError):slide_rows(STEPS,page)

    def test_display_cycles_skip_vertical_inactive_interval(self):
        c=PageClock(1234)
        self.assertEqual(c.display_deadline(1234),c.stamp(39*800+640))
        self.assertEqual(c.display_deadline(c.stamp(640)),c.stamp(40*800+640))
        self.assertEqual(c.display_deadline(c.stamp(399*800)),c.stamp((449+38)*800+640))
        for row in (400,412,448):
            self.assertEqual(c.display_deadline(c.stamp(row*800)),c.stamp((449+39)*800+640))

    def test_retrace_strictly_follows_entry_and_keeps_long_run_phase(self):
        c=PageClock(100)
        for frame in (0,1,12345,1000000):
            edge=c.stamp((frame*449+412)*800)
            self.assertEqual(c.retrace_deadline(edge-1),edge)
            self.assertEqual(c.retrace_deadline(edge),c.stamp(((frame+1)*449+412)*800))
        for now in (99,True,2**63):
            with self.assertRaises(GameError):c.display_deadline(now)
            with self.assertRaises(GameError):c.retrace_deadline(now)


if __name__=='__main__':unittest.main()
