"""Original-free regressions for the recovered MAINA1..5 presentation model."""
from copy import deepcopy
import unittest

from openreunion.core import GameError
from openreunion.dos.bridge_animation import (
    A1_DESTINATION, A2_DESTINATION, A3_DESTINATION, A4_DESTINATION,
    A5_BLINK_PIXELS, A5_COLOR_PIXELS, A5_PRIMARY_DESTINATION,
    A5_SECONDARY_DESTINATION, BridgeAmbient, GENERIC_COMMANDER_BOUNDARY,
    transition_plan,
)
from openreunion.dos.campaign import random_bounded


def copies(plan, asset):
    return [event for event in plan if event[:2] == ("copy", asset)]


class BridgeTransitionTests(unittest.TestCase):
    def test_all_three_gated_plans_preserve_sound_frame_wait_and_commit_order(self):
        commanders = transition_plan("commanders")
        production = transition_plan("production")
        fleets_forward = transition_plan("fleets", a4_direction=0)
        fleets_reverse = transition_plan("fleets", a4_direction=1)

        self.assertEqual(commanders[:2], (("sound", "DOOR1"), ("load", "MAINA2")))
        self.assertEqual(production[:2], (("sound", "DOOR2"), ("load", "MAINA1")))
        self.assertEqual(fleets_forward[:2], (("sound", "DOOR3"), ("load", "MAINA4")))
        self.assertEqual(commanders[-1], ("destination", 2))
        self.assertEqual(production[-1], ("destination", 5))
        self.assertEqual(fleets_forward[-1], ("destination", 16))

        self.assertEqual(
            [event[2] for event in copies(commanders, "MAINA2")],
            [(18 * frame, 0, 18, 89) for frame in range(4)],
        )
        self.assertTrue(all(event[3] == A2_DESTINATION for event in copies(commanders, "MAINA2")))
        self.assertEqual(
            [event[2] for event in copies(production, "MAINA1")],
            [(47 * frame, 0, 47, 136) for frame in range(6)],
        )
        self.assertTrue(all(event[3] == A1_DESTINATION for event in copies(production, "MAINA1")))
        self.assertEqual(
            [event[2] for event in copies(fleets_forward, "MAINA4")],
            [(16 * frame, 0, 16, 91) for frame in range(6)],
        )
        self.assertEqual(
            [event[2] for event in copies(fleets_reverse, "MAINA4")],
            [(224 - 16 * frame, 0, 16, 91) for frame in range(6)],
        )
        self.assertTrue(all(event[3] == A4_DESTINATION for event in copies(fleets_forward, "MAINA4")))
        expected_a3 = [(21 * frame, 0, 21, 105) for frame in range(4)]
        for plan in (fleets_forward, fleets_reverse):
            self.assertEqual([event[2] for event in copies(plan, "MAINA3")], expected_a3)
            self.assertTrue(all(event[3] == A3_DESTINATION for event in copies(plan, "MAINA3")))

        self.assertEqual(sum(event[1] for event in commanders if event[0] == "wait"), 17)
        self.assertEqual(sum(event[1] for event in production if event[0] == "wait"), 25)
        self.assertEqual(sum(event[1] for event in fleets_forward if event[0] == "wait"), 46)

    def test_door_ambient_and_overlay_calls_remain_in_exact_order(self):
        for target, expected_calls in (("commanders", 17), ("production", 25)):
            plan = transition_plan(target)
            markers = [event for event in plan if event[0] == "ambient_step"]
            self.assertEqual(len(markers), 2 * expected_calls)
            for index, event in enumerate(plan):
                if event == ("ambient_step", "MAINA5"):
                    self.assertEqual(plan[index:index + 3], (
                        ("ambient_step", "MAINA5"), ("ambient_step", "MAINA4"), ("wait", 1)))

        commanders = transition_plan("commanders")
        for event in copies(commanders, "MAINA2"):
            index = commanders.index(event)
            self.assertEqual(commanders[index - 1], ("display_begin",))
            self.assertEqual(commanders[index + 1:index + 3], (("display_end",), ("hero_overlay",)))
        production = transition_plan("production")
        for event in copies(production, "MAINA1"):
            index = production.index(event)
            self.assertEqual(production[index - 1], ("display_begin",))
            self.assertEqual(production[index + 1:index + 3],
                             (("commander_overlay", "fighter"), ("display_end",)))
        fleets = transition_plan("fleets")
        for event in copies(fleets, "MAINA4") + copies(fleets, "MAINA3"):
            index = fleets.index(event)
            self.assertEqual(fleets[index - 1], ("display_begin",))
            self.assertEqual(fleets[index + 1:index + 3],
                             (("commander_overlay", "builder"), ("display_end",)))

    def test_bad_transition_requests_fail_closed(self):
        for target, direction in (("research", 0), ("fleets", 2), ("fleets", True)):
            with self.subTest(target=target, direction=direction), self.assertRaises(GameError):
                transition_plan(target, a4_direction=direction)


class BridgeAmbientTests(unittest.TestCase):
    def test_bridge_entry_resets_only_the_original_primary_frame_field(self):
        ambient = BridgeAmbient(seed=77, a4_direction=1, a4_idle=23, a4_cadence=3,
                                a5_primary_frame=19, a5_primary_cadence=4,
                                a5_secondary_frame=8, a5_secondary_cadence=6,
                                a5_blinks=[9] * 8)
        ambient.enter_bridge()
        self.assertEqual(ambient.a5_primary_frame, 1)
        self.assertEqual((ambient.seed, ambient.a4_direction, ambient.a4_idle, ambient.a4_cadence,
                          ambient.a5_primary_cadence, ambient.a5_secondary_frame,
                          ambient.a5_secondary_cadence, ambient.a5_blinks),
                         (77, 1, 23, 3, 4, 8, 6, [9] * 8))

    def test_a4_full_forward_reverse_cycles_and_four_call_cadence(self):
        for direction, start, expected in (
            (0, 17, [(16 * frame, 0, 16, 91) for frame in range(16)]),
            (1, 17, [(16 * frame, 0, 16, 91) for frame in range(15, -1, -1)]),
        ):
            ambient = BridgeAmbient(a4_direction=direction, a4_idle=start, a4_cadence=1)
            actual = []
            for frame in range(16):
                events = ambient.advance_a4()
                actual.append(next(event[2] for event in events if event[:2] == ("copy", "MAINA4")))
                self.assertEqual(events[-1], ("generic_commander_tick",))
                if frame != 15:
                    self.assertEqual(ambient.advance_a4(), ())
                    self.assertEqual(ambient.advance_a4(), ())
                    self.assertEqual(ambient.advance_a4(), ())
            self.assertEqual(actual, expected)

    def test_a4_idle_reset_uses_private_rng_and_exposes_generic_boundary(self):
        campaign = {"rng": 0x12345678}
        before = deepcopy(campaign)
        ambient = BridgeAmbient(seed=1994)
        expected_seed, roll = random_bounded(1994, 250)
        events = ambient.advance_a4()
        self.assertEqual(events, (("generic_commander_tick",),))
        self.assertEqual((ambient.seed, ambient.a4_idle, ambient.a4_direction),
                         (expected_seed, 70 + roll, 1))
        self.assertEqual(campaign, before)
        self.assertIn("30320", GENERIC_COMMANDER_BOUNDARY)

        ambient = BridgeAmbient(a4_idle=17, a4_cadence=1,
                                generic_asset=1, generic_frame=1, generic_delay=0)
        events = ambient.advance_a4(builder_visible=True)
        self.assertEqual(events, (
            ("display_begin",),
            ("copy", "MAINA4", (0, 0, 16, 91), A4_DESTINATION),
            ("commander_overlay", "builder"),
            ("display_end",),
            ("generic_commander_tick",),
            ("commander_overlay", "pilot"),
        ))

    def test_generic_initial_selection_delay_frames_and_rollover_use_private_rng(self):
        rules = [dict(frames=count, width=44, height=66, x=83, y=49)
                 for count in (9, 30, 13, 18, 28, 13)]
        ambient = BridgeAmbient(seed=1994)
        expected_seed, selected = random_bounded(1994, 6)
        expected_seed, delay = random_bounded(expected_seed, 200)
        ambient.initialize_generic(rules)
        self.assertEqual((ambient.seed, ambient.generic_asset, ambient.generic_frame, ambient.generic_delay),
                         (expected_seed, selected + 1, 1, delay + 100))
        ambient.generic_asset, ambient.generic_frame, ambient.generic_delay = 1, 1, 1
        self.assertEqual(ambient.advance_generic(rules), ())
        self.assertEqual(ambient.generic_delay, 0)
        self.assertEqual(ambient.advance_generic(rules, fighter_visible=True), (
            ("display_begin",),
            ("generic_frame", 1, 2, (1, 1, 42, 64), (83, 49, 42, 64)),
            ("commander_overlay", "fighter"),
            ("display_end",),
        ))
        ambient.generic_frame = rules[0]["frames"]
        seed = ambient.seed
        next_seed, next_asset = random_bounded(seed, 6)
        next_seed, next_delay = random_bounded(next_seed, 200)
        self.assertEqual(ambient.advance_generic(rules), ())
        self.assertEqual((ambient.seed, ambient.generic_asset, ambient.generic_frame, ambient.generic_delay),
                         (next_seed, next_asset + 1, 1, next_delay + 100))

    def test_a5_all_primary_and_secondary_atlas_rectangles(self):
        for frame in range(38):
            ambient = BridgeAmbient(a5_primary_frame=(frame - 1) % 38,
                                    a5_primary_cadence=1, a5_secondary_cadence=2,
                                    a5_blinks=[2] * 8)
            event = next(event for event in ambient.advance_a5() if event[:2] == ("copy", "MAINA5"))
            self.assertEqual(event, (
                "copy", "MAINA5", (19 * (frame % 16), 1 + 22 * (frame // 16), 19, 21),
                A5_PRIMARY_DESTINATION,
            ))
        for frame in range(10):
            ambient = BridgeAmbient(a5_primary_cadence=2,
                                    a5_secondary_frame=(frame - 1) % 10,
                                    a5_secondary_cadence=1, a5_blinks=[2] * 8)
            event = next(event for event in ambient.advance_a5() if event[:2] == ("copy", "MAINA5"))
            self.assertEqual(event, (
                "copy", "MAINA5", (115 + 13 * frame, 45, 12, 14),
                A5_SECONDARY_DESTINATION,
            ))

    def test_a5_initial_lamps_and_blink_thresholds_follow_original_call_order(self):
        ambient = BridgeAmbient(seed=1994)
        events = ambient.advance_a5()
        self.assertEqual(events[:2], (
            ("copy", "MAINA5", (38, 1, 19, 21), A5_PRIMARY_DESTINATION),
            ("copy", "MAINA5", (141, 45, 12, 14), A5_SECONDARY_DESTINATION),
        ))
        pixels = [event for event in events if event[0] == "pixel"]
        self.assertEqual([event[1] for event in pixels[:11]], list(A5_COLOR_PIXELS))
        self.assertTrue(all(64 <= event[2] <= 239 for event in pixels[:11]))
        self.assertEqual(pixels[11:], [("pixel", destination, 0x70) for destination in A5_BLINK_PIXELS])

        expected_seed = 1994
        for _ in range(11):
            expected_seed, _ = random_bounded(expected_seed, 176)
        expected_blinks = []
        for _ in range(8):
            expected_seed, roll = random_bounded(expected_seed, 5)
            expected_blinks.append(102 + roll)
        self.assertEqual(ambient.seed, expected_seed)
        self.assertEqual(ambient.a5_blinks, expected_blinks)

        ambient = BridgeAmbient(a5_primary_cadence=2, a5_secondary_cadence=2,
                                a5_blinks=[101] + [2] * 7)
        events = ambient.advance_a5()
        self.assertIn(("pixel", A5_BLINK_PIXELS[0], 0x82), events)
        self.assertTrue(5 <= ambient.a5_blinks[0] <= 12)

    def test_pair_runs_a5_before_a4_and_rejects_bad_state(self):
        ambient = BridgeAmbient(a4_idle=17, a4_cadence=1,
                                a5_primary_cadence=2, a5_secondary_cadence=2,
                                a5_blinks=[2] * 8)
        events = ambient.advance_pair()
        first_a4 = events.index(("display_begin",))
        self.assertTrue(all(event[0] == "pixel" for event in events[:first_a4]))
        self.assertEqual(events[-1], ("generic_commander_tick",))
        with self.assertRaises(GameError):
            BridgeAmbient(a5_blinks=[1] * 7)
        with self.assertRaises(GameError):
            ambient.advance_a4(builder_visible=1)


if __name__ == "__main__":
    unittest.main()
