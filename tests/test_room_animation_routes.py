"""Only the three original bridge room hotspots play door transitions."""
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

from openreunion.dos.original_ui import OriginalApp


class RoomAnimationRoutes(unittest.TestCase):
    def release(self, slot, action, screen='bridge'):
        app = SimpleNamespace(screen=screen, surface_drag=False, disk_pressed=0,
            commander_rank=3, pointer=SimpleNamespace(release=lambda *args:slot),
            original_slot=lambda event:slot, action=lambda value:('',action),
            bridge_cinema=SimpleNamespace(start=Mock()), dispatch=Mock())
        OriginalApp.original_release(app, SimpleNamespace(num=1,state=0))
        return app

    def test_original_1b_1c_1f_hotspots_start_their_named_transition(self):
        for slot, action, destination in ((27,14,'commanders'),(28,23,'production'),(31,13,'fleets')):
            app = self.release(slot, action)
            app.bridge_cinema.start.assert_called_once_with(destination)
            app.dispatch.assert_not_called()
            self.assertEqual(app.commander_rank, None if slot == 27 else 3)

    def test_same_commands_from_header_keep_the_direct_navigation_path(self):
        for action in (14,23,13):
            app = self.release(2, action)
            app.bridge_cinema.start.assert_not_called()
            app.dispatch.assert_called_once_with(action, 1)

    def test_other_rooms_and_released_off_target_do_not_start_bridge_effects(self):
        app = self.release(27, ('research',3), screen='research')
        app.bridge_cinema.start.assert_not_called()
        app.dispatch.assert_called_once_with(('research',3),1)
        app = self.release(0, 14)
        app.bridge_cinema.start.assert_not_called()
        app.dispatch.assert_not_called()


if __name__ == '__main__':unittest.main()
