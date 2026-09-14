"""Focused tests for the pure research-disc animation plans."""
import unittest

from openreunion.core import GameError
from openreunion.dos.research_animation import (
    SpinnerGuard, SPINNER_CYCLE, cell_destination, static_copy, spinner_frame,
    transition_plan,
)


def guard(product, *, developer=1, block=0, training=0, remaining=20000,
          threshold=10000, paused=False):
    return SpinnerGuard(product, developer, block, training, remaining, threshold, paused)


class ResearchAnimationTests(unittest.TestCase):
    def test_static_disc_endpoints_and_cells(self):
        expected = {0: None, 1: (10, 0x1400, 0x4240),
                    2: (19, 0x1520, 0x4240), 3: (30, 0x3C00, 0x4240),
                    4: (39, 0x3D20, 0x4240), 5: (0, 0, 0x4240)}
        for state, result in expected.items():
            actual = static_copy(state, 1)
            self.assertIsNone(actual) if result is None else self.assertEqual(
                (actual.source_frame_argument, actual.source_offset,
                 actual.destination_offset), result)
        self.assertEqual(static_copy(1, 2).destination_offset, 0x4260)
        self.assertEqual(static_copy(1, 6).destination_offset, 0x5640)

    def test_spinner_offsets_repeats_and_wraps(self):
        for counter, argument in ((0, 40), (4, 40), (5, 41), (43, 48), (44, 48)):
            frame = spinner_frame(counter, 1, guard(1))
            self.assertEqual(frame.copy.source_frame_argument, argument)
            self.assertEqual(frame.counter_after, (counter + 1) % SPINNER_CYCLE)
        self.assertEqual(spinner_frame(44, 1, guard(1)).counter_after, 0)

    def test_spinner_guards_do_not_mutate_counter_or_copy(self):
        for kwargs in (
            {"developer": 0}, {"block": 1}, {"training": 4},
            {"remaining": 10000},
        ):
            self.assertIsNone(spinner_frame(7, 1, guard(1, **kwargs)))
        self.assertIsNone(spinner_frame(7, 0, guard(0)))
        self.assertIsNone(spinner_frame(7, 1, guard(1, paused=True)))
        with self.assertRaises(GameError):
            spinner_frame(45, 1, guard(1))

    def test_reverse_transition_has_three_spinner_calls_per_iteration(self):
        plan = transition_plan("22DEA", 2, 17, 3, 0, spinner_guard=guard(3))
        self.assertEqual([step.transition.source_frame_argument for step in plan.steps],
                         [19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 10])
        self.assertEqual(plan.spinner_invocations, 33)
        self.assertEqual(plan.retrace_calls, 33)
        self.assertEqual(plan.spinner_copies, 33)
        self.assertEqual(plan.counter_after, 33)
        self.assertEqual(plan.steps[0].transition.destination_offset, cell_destination(17))
        self.assertEqual(plan.steps[0].spinner_frames[0].copy.destination_offset, cell_destination(3))

    def test_matching_target_skips_calls_and_blocked_spinner_keeps_retrace(self):
        same = transition_plan("22EBB", 4, 17, 17, 12, spinner_guard=guard(17))
        self.assertEqual([step.transition.source_frame_argument for step in same.steps],
                         [30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 39])
        self.assertEqual(same.spinner_invocations, 0)
        self.assertEqual(same.retrace_calls, 33)
        self.assertEqual(same.counter_after, 12)

        blocked = transition_plan("22EBB", 4, 17, 3, 12,
                                  spinner_guard=guard(3, developer=0))
        self.assertEqual(blocked.spinner_invocations, 33)
        self.assertEqual(blocked.retrace_calls, 33)
        self.assertEqual(blocked.spinner_copies, 0)
        self.assertEqual(blocked.counter_after, 12)

        inactive = transition_plan("22EBB", 4, 17, 0, 12,
                                   spinner_guard=guard(0))
        self.assertEqual(inactive.spinner_invocations, 33)
        self.assertEqual(inactive.retrace_calls, 33)
        self.assertEqual(inactive.spinner_copies, 0)
        self.assertEqual(inactive.counter_after, 12)


if __name__ == '__main__':
    unittest.main()
