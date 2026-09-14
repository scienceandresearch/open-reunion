"""Intro compatibility must preserve later rows and general strict validation."""
from fractions import Fraction
import unittest

from openreunion.core import GameError
from openreunion.dos.intro_music import decode_intro_module, cue_clock
from openreunion.dos.victory_cinema import module_rows


def module():
    data = bytearray(1084 + 1024)
    data[950] = 1
    data[1080:1084] = b'M.K.'
    return data


class IntroMusicTests(unittest.TestCase):
    def test_zero_speed_preserves_following_rows_and_current_speed(self):
        data = module()
        data[1086:1088] = b'\x0f\x03'
        data[1084 + 16 + 2:1084 + 16 + 4] = b'\x0f\0'
        song = decode_intro_module(bytes(data))
        rows, duration = cue_clock(song)
        self.assertEqual(rows[0, 2], Fraction(12, 100))
        self.assertEqual(duration, Fraction(64 * 6, 100))
        with self.assertRaises(GameError):
            module_rows(song)

    def test_unknown_truncation_is_not_padded(self):
        data = module()
        data[43] = 101
        with self.assertRaises(GameError):
            decode_intro_module(bytes(data))

    def test_valid_module_is_byte_identical(self):
        data = bytes(module())
        self.assertEqual(decode_intro_module(data).data, data)


if __name__ == '__main__':
    unittest.main()
