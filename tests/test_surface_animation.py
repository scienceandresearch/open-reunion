"""FANIM strip boundaries, pacing and graphical disclosure regressions."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from test_surface import surface_session
from openreunion.dos.original_screen import OriginalScreens, ScreenPixels
from openreunion.dos.surface_animation import SurfaceAnimation
from openreunion.dos.surface_screen import SurfaceView
from openreunion.dos.video_timing import PERIOD_NUMERATOR_NS, PIXEL_CLOCK_HZ


def deadline(step):
    return (step * 10 * PERIOD_NUMERATOR_NS + PIXEL_CLOCK_HZ - 1) // PIXEL_CLOCK_HZ


class SurfaceAnimationTests(unittest.TestCase):
    def test_initial_frame_cycle_and_exact_deadlines(self):
        animation = SurfaceAnimation()
        self.assertEqual(animation.frame, 3)
        animation.advance(0)
        for step, frame in ((1, 1), (2, 2), (3, 3), (4, 1)):
            self.assertFalse(animation.advance(deadline(step) - 1))
            self.assertTrue(animation.advance(deadline(step)))
            self.assertEqual(animation.frame, frame)

    def test_pause_discards_hidden_time_and_views_are_independent(self):
        first, second = SurfaceView(), SurfaceView()
        first.animation.advance(0)
        first.animation.advance(deadline(1))
        first.animation.advance(deadline(2), enabled=False)
        first.animation.advance(deadline(100))
        self.assertEqual(first.animation.frame, 1)
        first.animation.advance(deadline(100) + deadline(1))
        self.assertEqual(first.animation.frame, 2)
        self.assertEqual(second.animation.frame, 3)

    def test_delayed_callback_preserves_phase_without_repeated_catchup(self):
        animation = SurfaceAnimation()
        animation.advance(0)
        animation.advance(deadline(1000))
        self.assertEqual(animation.frame, 1)
        self.assertFalse(animation.advance(deadline(1000)))

    def test_all_animated_strip_boundaries_match_original_byte_offsets(self):
        for group, count in ((1, 80), (5, 20), (10, 80)):
            for frame in (1, 2, 3):
                animation = SurfaceAnimation(frame=frame)
                for tile in (0, count - 1):
                    actual = animation.tile(group, tile)
                    source_byte = actual // 20 * 5120 + actual % 20 * 16
                    expected = (frame - 1) * count * 256 + tile // 20 * 5120 + tile % 20 * 16
                    self.assertEqual(source_byte, expected)

    def test_renderer_changes_animated_tiles_without_state_changes_or_disclosure(self):
        session = surface_session()
        raw = session.state['worlds']['1:5:0']['raw']
        raw[0], raw[6] = 1, 1
        # One static tile followed by the first animated tile.
        session.catalog['surface_maps']['MAP1_0.MAP']['tiles_hex'] = '0014' + '00' * 94
        palette = bytes(v for i in range(256) for v in (i, i, i))
        ground = SimpleNamespace(width=320, height=16, palette=palette, pixels=bytes([10]) * 5120)
        animated = SimpleNamespace(width=320, height=192, palette=palette,
            pixels=b''.join(bytes([v]) * (320 * 64) for v in (20, 30, 40)))
        buildings = SimpleNamespace(width=320, height=192, palette=palette, pixels=bytes(320 * 192))
        renderer = OriginalScreens.__new__(OriginalScreens)
        renderer.content = SimpleNamespace(catalog=session.catalog)
        renderer.frame = lambda *a, **kw: ScreenPixels()
        renderer.path_asset = lambda name: animated if 'FANIM' in name else ground if 'FELSZ' in name else buildings
        renderer.text = lambda *a, **kw: None
        view = SurfaceView()
        before = deepcopy(session.state)
        samples = []
        for frame in (3, 1, 2):
            view.animation.frame = frame
            target = renderer.surface(session.state, view)
            samples.append(target.rgb[((53 * 320) + 109) * 3])
            self.assertEqual(target.rgb[((53 * 320) + 93) * 3], 10)
        self.assertEqual(samples, [40, 20, 30])
        self.assertEqual(session.state, before)
        raw[0] = raw[6] = raw[8] = raw[9] = raw[10] = 0
        for frame in (1, 2, 3):
            view.animation.frame = frame
            target = renderer.surface(session.state, view)
            self.assertEqual(target.rgb[((53 * 320) + 109) * 3], 0)


if __name__ == '__main__':
    unittest.main()
