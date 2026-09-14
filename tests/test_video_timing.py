"""Reference retrace boundaries, accumulated drift and late-frame pacing."""
from fractions import Fraction
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.video_timing import RetraceClock,graphics_misc,RETRACE_HZ


class VideoTimingTests(unittest.TestCase):
    def test_standard_reference_frequency_and_first_edge(self):
        self.assertAlmostEqual(RETRACE_HZ,70.0863028953,places=9)
        clock=RetraceClock(1_000_000_000)
        self.assertEqual(clock.next_deadline(1_000_000_000),1_014_268_124)
        self.assertEqual(clock.delay_ms(1_000_000_000),15)

    def test_exact_and_near_edge_entries_wait_for_the_next_edge(self):
        clock=RetraceClock(0);first=clock.next_deadline(0)
        self.assertEqual(clock.next_deadline(first-1),first)
        self.assertGreater(clock.next_deadline(first),first)
        self.assertEqual(clock.next_deadline(first),clock.next_deadline(first+1))

    def test_long_run_has_no_accumulated_rounding_drift(self):
        origin=4_000_000_000_000;clock=RetraceClock(origin)
        period=Fraction(800*449*1_000_000_000,25_175_000)
        for step in (1,2,17,1000,1_000_000,10_000_000):
            target=origin+(step*period).__ceil__()
            self.assertEqual(clock.next_deadline(target-1),target)
            self.assertEqual(clock.next_deadline(target),origin+((step+1)*period).__ceil__())

    def test_slow_callback_waits_next_grid_edge_without_catchup_or_phase_reset(self):
        clock=RetraceClock(0);first=clock.next_deadline(0)
        late=3*first+2_000_000
        target=clock.next_deadline(late)
        self.assertEqual(target,57_072_493)
        self.assertGreater(target-late,10_000_000)
        # The former max(previous+period,now) policy yielded a 1ms callback.
        self.assertEqual(clock.delay_ms(late),13)

    def test_millisecond_adapter_never_requests_before_reference_edge(self):
        clock=RetraceClock(1234)
        for now in range(1234,100_000_000,100003):
            delay=clock.delay_ms(now);target=clock.next_deadline(now)
            self.assertGreaterEqual(now+delay*1_000_000,target)
            self.assertLess(now+(delay-1)*1_000_000,target)
            self.assertTrue(1<=delay<=15)

    def test_invalid_time_or_register_values_are_rejected(self):
        for origin in (-1,True,1.0):
            with self.assertRaises(GameError):RetraceClock(origin)
        clock=RetraceClock(100)
        for now in (99,True,1.0,2**63):
            with self.assertRaises(GameError):clock.next_deadline(now)
        for value in (-1,256,True):
            with self.assertRaises(GameError):graphics_misc(value)
        self.assertEqual(graphics_misc(0xFF),0x7F);self.assertEqual(graphics_misc(0x63),0x63)


if __name__=='__main__':unittest.main()
