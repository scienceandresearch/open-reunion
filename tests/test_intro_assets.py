"""Intro regressions for base redraw, cumulative deltas and large clips."""
import struct
import unittest
from unittest.mock import patch

from openreunion.core import GameError
from openreunion.dos.assets import Picture
from openreunion.dos.intro_assets import (animation_frames,clip_frames,frame_plan,
    high_resolution_picture,converted_animation,decode_converted_animation)


def record(payload):
    return struct.pack('<H', len(payload)) + b'SpidyAnim' + struct.pack('<HH', 320, 200) + payload


def sample(count):
    base = record(b'\xc0' + struct.pack('<H', 64000) + b'\1')
    first = record(b'\2\x80' + struct.pack('<H', 63999))
    second = record(b'\x81\3\x80' + struct.pack('<H', 63998))
    return base + first + second + b'\0\0' * (count - 3)


class IntroAssetTests(unittest.TestCase):
    def test_cumulative_delta_preserves_the_preceding_frame(self):
        frames = list(clip_frames(sample(6), 1, bytes(64000)))
        self.assertEqual(frames[2][1][:3], b'\2\3\1')

    def test_anim7_redraws_base_before_each_delta(self):
        frames = list(clip_frames(sample(31), 7, bytes(64000)))
        self.assertEqual(frames[2][1][:3], b'\1\3\1')

    def test_large_intro_clip_is_not_limited_by_main_game_frame_count(self):
        frames, tail = animation_frames(sample(187) + b'retained tail', 13)
        self.assertEqual(len(frames), 187)
        self.assertEqual(tail, b'retained tail')

    def test_invalid_asset_and_incompatible_background_are_rejected(self):
        for asset in (True, 0, 2, 17, 25, '1'):
            with self.subTest(asset=asset), self.assertRaises(GameError):
                frame_plan(asset)
        with self.assertRaises(GameError):
            list(clip_frames(sample(6), 1, bytes(10)))

    def test_truncated_payload_is_rejected(self):
        with self.assertRaises(GameError):
            animation_frames(sample(6)[:-1], 1)

    def test_converted_animation_is_versioned_and_bound_to_its_asset(self):
        data=sample(6)
        converted=converted_animation(data,1)
        self.assertEqual(decode_converted_animation(converted,1),animation_frames(data,1)[0])
        for malformed,asset in ((converted,3),(b'bad'+converted,1),(converted[:-1],1)):
            with self.subTest(asset=asset),self.assertRaises(GameError):
                decode_converted_animation(malformed,asset)

    def test_high_resolution_uses_low_four_bits_and_pads_known_short_strip(self):
        pictures = [Picture(640, 100, bytes([239]) * 64000, bytes(768)) for _ in range(4)]
        pictures.append(Picture(636, 80, bytes(636 * 80), bytes(768)))
        with patch('openreunion.dos.intro_assets.read_picture', side_effect=pictures):
            result = high_resolution_picture('.', '19x')
        self.assertEqual((result.width, result.height), (640, 480))
        self.assertEqual(result.pixels[:640 * 400], bytes([15]) * (640 * 400))
        self.assertEqual(result.pixels[640 * 400:], bytes(640 * 80))

    def test_high_resolution_rejects_unexpected_short_strip_and_path(self):
        pictures = [Picture(636, 100, bytes(63600), bytes(768))] * 5
        with patch('openreunion.dos.intro_assets.read_picture', side_effect=pictures):
            with self.assertRaises(GameError):
                high_resolution_picture('.', '1x')
        with self.assertRaises(GameError):
            high_resolution_picture('.', '../1x')


if __name__ == '__main__':
    unittest.main()
