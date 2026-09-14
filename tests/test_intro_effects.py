"""Boundary checks for the intro's two-picture scrolling transition."""
import unittest
from openreunion.core import GameError
from openreunion.dos.intro_effects import scroll_frame, fade_levels, flight_frame, shake_frame, white_flash_dac, shake_plan


class IntroEffectsTests(unittest.TestCase):
    def test_intro_random_plan_empty_and_invalid_requests(self):
        self.assertEqual(shake_plan(1994, 0), (1994, ()))
        for seed, repeats, amplitude in ((-1, 1, 3), (2**32, 1, 3), (1994, -1, 3),
                                         (1994, 32768, 3), (1994, 1, 0)):
            with self.subTest(seed=seed,repeats=repeats,amplitude=amplitude),self.assertRaises(GameError):
                shake_plan(seed, repeats, amplitude)

    def test_shake_preserves_asymmetric_original_border(self):
        picture = b''.join(bytes([row]) * 320 for row in range(200))
        previous = bytes([240]) * 64000
        result = shake_frame(previous, picture, 3, 2, 0)
        self.assertEqual(result[:320], previous[:320])
        self.assertEqual(result[320:640], bytes([240]) + bytes(317) + bytes([240, 240]))
        self.assertEqual(result[198 * 320:], previous[198 * 320:])
        self.assertEqual(previous, bytes([240]) * 64000)
        with self.assertRaises(GameError):
            shake_frame(previous, picture, 3, 3, 0)

    def test_white_flash_preserves_other_colors_and_reaches_both_endpoints(self):
        current, palette = bytes([7]) * 768, bytes([23]) * 768
        white = white_flash_dac(current, palette, 0, first=1, last=254)
        self.assertEqual(white, bytes([7]) * 3 + bytes([63]) * 762 + bytes([7]) * 3)
        self.assertEqual(white_flash_dac(current, palette, 5), palette)
        self.assertEqual(white_flash_dac(current, palette, 2), bytes([47]) * 768)
        for bad in (0, 521):
            with self.assertRaises(GameError):
                white_flash_dac(current, palette, 0, divisor=bad)
        with self.assertRaises(GameError):
            white_flash_dac(current, bytes([64]) * 768, 1)

    def test_flight_ship_overlay_preserves_transparent_pixels(self):
        stars = bytes([17]) * 64000
        planet = bytes([3]) * 64000
        ship = bytearray(64000)
        ship[319] = 9
        result = flight_frame(stars, planet, bytes(ship), 89)
        self.assertEqual(result[:5], bytes([3, 3, 3, 9, 3]))
        self.assertEqual(flight_frame(stars, planet, None, 89)[:5], bytes([3]) * 5)

    def test_flight_rejects_frame_overrun(self):
        with self.assertRaises(GameError):
            flight_frame(bytes(64000), bytes(64000), None, 168)

    def test_odd_half_white_fade_reaches_original_floor_endpoint(self):
        self.assertEqual(fade_levels(5, 'to_half_white'), (5, 4, 3, 2))
        self.assertEqual(fade_levels(5, 'from_half_white'), (2, 3, 4, 5))
        with self.assertRaises(GameError):
            fade_levels(0, 'in')

    def test_transition_starts_with_incoming_bottom_row_and_finishes_complete(self):
        old = bytes([17]) * 64000
        new = b''.join(bytes([row]) * 320 for row in range(200))
        self.assertEqual(scroll_frame(old, new, 200), old)
        self.assertEqual(scroll_frame(old, new, 199), bytes([199]) * 320 + old[:199 * 320])
        self.assertEqual(scroll_frame(old, new, 0), new)

    def test_bad_geometry_and_positions_are_rejected(self):
        for position in (-1, 201, True):
            with self.subTest(position=position), self.assertRaises(GameError):
                scroll_frame(bytes(64000), bytes(64000), position)
        with self.assertRaises(GameError):
            scroll_frame(bytes(63999), bytes(64000), 1)


if __name__ == '__main__':
    unittest.main()
