"""Headless controller tests for the original control-room presentation."""
import unittest

from openreunion.dos.assets import Picture
from openreunion.dos.bridge_cinema import BridgeCinema
from openreunion.dos.original_screen import ScreenPixels


def picture(width, height, value=1):
    palette = b"".join(bytes((i, i, i)) for i in range(256))
    return Picture(width, height, bytes((value,)) * (width * height), palette)


class FakeRoot:
    def __init__(self):
        self.callbacks = {}
        self.next_id = 1

    def after(self, _delay, callback):
        identity = self.next_id
        self.next_id += 1
        self.callbacks[identity] = callback
        return identity

    def after_cancel(self, identity):
        self.callbacks.pop(identity, None)

    def fire(self):
        identity = min(self.callbacks)
        callback = self.callbacks.pop(identity)
        callback()


class FakeCanvas:
    mapped = True

    def winfo_ismapped(self):
        return self.mapped


class FakeNavigation:
    def __init__(self, app):
        self.app = app
        self.owner = None
        self.destination = None
        self.starts = []
        self.cancels = 0

    def start(self, name, destination):
        self.starts.append((name, destination))
        self.owner = self.app.session
        self.destination = destination
        return True

    def cancel(self):
        self.cancels += 1
        self.owner = self.destination = None


class FakeRenderer:
    def __init__(self):
        self.bridge_calls = 0
        self.frame_calls = 0
        self.assets = {
            "MAINA1": picture(282, 136, 11),
            "MAINA2": picture(72, 89, 12),
            "MAINA3": picture(84, 105, 13),
            "MAINA4": picture(240, 91, 14),
            "MAINA5": picture(320, 95, 15),
            "MAINFACE": picture(320, 200, 16),
            "HEROES": picture(320, 200, 17),
        }

    def bridge(self, _state, _page, _caption, _hero):
        self.bridge_calls += 1
        target = ScreenPixels()
        target.fill((0, 49, 320, 151), (10, 20, 30))
        return target

    def frame(self, _state, _background, _layout, _page, _caption):
        self.frame_calls += 1
        target = ScreenPixels()
        target.fill((0, 0, 320, 49), (self.frame_calls, 0, 0))
        return target

    def asset(self, name):
        return self.assets[name]


class FakeContent:
    def __init__(self):
        self.calls = []

    def bridge_animation(self, asset, frame):
        self.calls.append((asset, frame))
        return picture(44, 66, asset * 10 + frame)


class Session:
    def __init__(self):
        self.state = {
            "ranks": {"pilot": 1, "builder": 1, "fighter": 1, "developer": 1},
            "campaign": {"training_role": 0, "research_block_remaining": 0},
        }


class Pointer:
    def __init__(self):
        self.buttons = set()


class FakeApp:
    def __init__(self):
        self.root = FakeRoot()
        self.original = FakeCanvas()
        self.screen_renderer = FakeRenderer()
        self.content = FakeContent()
        self.session = Session()
        self.catalog = {"story_cinema": [
            {"frames": frames, "width": 44, "height": 66, "x": 83, "y": 49}
            for frames in (9, 30, 13, 18, 28, 13)
        ]}
        self.screen = "bridge"
        self.startup = None
        self.menu_page = 0
        self.caption = ""
        self.hero = 2
        self.pointer = Pointer()
        self.navigation_sound = FakeNavigation(self)
        self.rendered = []
        self.destinations = []
        self.cinema = None

    def guard(self, callback):
        callback()

    def render_original(self):
        if self.screen == "bridge":
            self.rendered.append(self.cinema.draw(
                self.session.state, self.menu_page,
                self.caption or "CONTROL ROOM", self.hero))

    def show_original(self, destination):
        self.destinations.append(destination)
        self.screen = destination

    def open_fleets(self):
        self.destinations.append("fleets")
        self.screen = "fleets"


def fixture(cinema_class=BridgeCinema):
    app = FakeApp()
    cinema = cinema_class(app)
    app.cinema = cinema
    return app, cinema


class BridgeCinemaTests(unittest.TestCase):
    def test_draw_reuses_incremental_body_but_builds_a_fresh_header(self):
        app, cinema = fixture()
        first = cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        second = cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        self.assertEqual(app.screen_renderer.bridge_calls, 1)
        self.assertEqual(app.screen_renderer.frame_calls, 2)
        self.assertNotEqual(first.rgb[:3], second.rgb[:3])
        self.assertEqual(first.rgb[49 * 320 * 3:], second.rgb[49 * 320 * 3:])

        app.session.state["ranks"]["builder"] = 2
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        self.assertEqual(app.screen_renderer.bridge_calls, 2)
        app.session.state["campaign"]["research_block_remaining"] = 12
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        self.assertEqual(app.screen_renderer.bridge_calls, 3)
        app.session.state["campaign"]["research_block_remaining"] = 11
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        self.assertEqual(app.screen_renderer.bridge_calls, 3)

    def test_all_gated_exits_commit_after_the_exact_retrace_count(self):
        for target, sound, retraces in (
                ("commanders", "DOOR1", 17),
                ("production", "DOOR2", 25),
                ("fleets", "DOOR3", 46)):
            with self.subTest(target=target):
                app, cinema = fixture()
                cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
                self.assertTrue(cinema.start(target))
                self.assertEqual(app.navigation_sound.starts, [(sound, "bridge")])
                self.assertTrue(cinema.running)
                for _ in range(retraces - 1):
                    app.root.fire()
                    self.assertEqual(app.screen, "bridge")
                app.root.fire()
                self.assertEqual(app.screen, target)
                self.assertEqual(app.destinations, [target])
                self.assertFalse(cinema.running)
                self.assertEqual(app.navigation_sound.destination, target)

    def test_hidden_startup_and_held_pointer_pause_without_losing_transition(self):
        app, cinema = fixture()
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        cinema.start("commanders")
        initial_wait = cinema.wait
        app.pointer.buttons.add(1)
        app.root.fire()
        self.assertEqual(cinema.wait, initial_wait)
        self.assertTrue(cinema.running)

        app.pointer.buttons.clear()
        app.startup = object()
        app.root.fire()
        self.assertEqual(cinema.wait, initial_wait)
        self.assertTrue(cinema.running)
        self.assertFalse(app.root.callbacks)

        app.startup = None
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        self.assertTrue(app.root.callbacks)
        remaining = len(cinema.events)
        app.root.fire()
        self.assertLess(len(cinema.events), remaining)

    def test_session_replacement_cancels_door_and_restarts_private_ambient(self):
        app, cinema = fixture()
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        old_ambient = cinema.ambient
        cinema.start("production")
        app.session = Session()
        cinema.sync()
        self.assertFalse(cinema.running)
        self.assertIsNot(cinema.ambient, old_ambient)
        self.assertIs(cinema.owner, app.session)
        self.assertEqual(app.navigation_sound.cancels, 1)
        self.assertIsNone(cinema.body)

    def test_ordinary_leave_preserves_ambient_but_reapplies_bridge_entry_write(self):
        app, cinema = fixture()
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        ambient = cinema.ambient
        ambient.a4_idle = 23
        ambient.generic_delay = 41
        ambient.a5_primary_frame = 19
        cinema.leave()
        app.screen = "bridge"
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        self.assertIs(cinema.ambient, ambient)
        self.assertEqual((ambient.a4_idle, ambient.generic_delay), (23, 41))
        self.assertEqual(ambient.a5_primary_frame, 1)

    def test_generic_tick_draws_frame_between_fighter_and_pilot_restores(self):
        overlays = []

        class RecordingCinema(BridgeCinema):
            def _commander_overlay(self, role):
                overlays.append(role)
                super()._commander_overlay(role)

        app, cinema = fixture(RecordingCinema)
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        cinema.ambient.a4_cadence = 1
        cinema.ambient.a4_idle = 17
        cinema.ambient.generic_asset = 1
        cinema.ambient.generic_frame = 1
        cinema.ambient.generic_delay = 0
        cinema._apply(("ambient_step", "MAINA4"))
        self.assertEqual(app.content.calls, [(1, 2)])
        self.assertEqual(overlays, ["builder", "fighter", "pilot"])

    def test_ordinary_outer_loop_advances_maina5_then_maina4_and_generic(self):
        app, cinema = fixture()
        cinema.draw(app.session.state, 0, "CONTROL ROOM", 2)
        generic_delay = cinema.ambient.generic_delay
        app.root.fire()
        self.assertEqual(cinema.ambient.a5_primary_cadence, 5)
        self.assertEqual(cinema.ambient.a4_cadence, 4)
        self.assertEqual(cinema.ambient.generic_delay, generic_delay - 1)


if __name__ == "__main__":
    unittest.main()
