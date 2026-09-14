"""Headless regressions for inline New Fleet name editing and click focus."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openreunion.core import GameError
from openreunion.dos import original_ui
from openreunion.dos.original_ui import OriginalApp


class FakeClock:
    def __init__(self):
        self.pauses = 0

    def pause(self):
        self.pauses += 1


class FakeEntry:
    instances = []

    def __init__(self, parent, **kwargs):
        self.value = ""
        self.bindings = {}
        self.destroyed = False
        self.configured = {}
        self.__class__.instances.append(self)

    def insert(self, index, value):
        self.value = value

    def get(self):
        return self.value

    def selection_range(self, start, end):
        pass

    def register(self, callback):
        return callback

    def configure(self, **kwargs):
        self.configured.update(kwargs)

    def bind(self, event, callback):
        self.bindings[event] = callback

    def focus_set(self):
        pass

    def destroy(self):
        self.destroyed = True


class FakeCanvas:
    def __init__(self):
        self.deleted = []
        self.focuses = 0
        self.focus_owner = self
        self.windows = []

    def create_window(self, *args, **kwargs):
        self.windows.append((args, kwargs))
        return len(self.windows)

    def delete(self, item):
        self.deleted.append(item)

    def focus_set(self):
        self.focuses += 1
        self.focus_owner = self

    def focus_get(self):
        return self.focus_owner


class FakePointer:
    def __init__(self):
        self.presses = []
        self.cancels = []

    def press(self, button, slot, enabled):
        self.presses.append((button, slot, enabled))

    def cancel(self, **kwargs):
        self.cancels.append(kwargs)


class NameEditorClickTests(unittest.TestCase):
    def setUp(self):
        FakeEntry.instances.clear()
        self.app = object.__new__(OriginalApp)
        self.app.equipment_editor = None
        self.app.equipment_editor_item = None
        self.app.name_editor_submit = None
        self.app.name_editor_position = (24, 56)
        self.app.original = FakeCanvas()
        self.app.clock_panel = Mock(clock=FakeClock())
        self.app.render_original = Mock()
        self.app.guard = lambda callback: callback()
        self.app.pointer = FakePointer()
        self.app.scene_view = Mock()
        self.app.surface_drag = False
        self.app.disk_pressed = 0
        self.app.screen = "new_fleet"
        self.app.new_fleet_view = SimpleNamespace(kind=2, name="Transfer fleet")
        self.app.original_slot = Mock(return_value=22)
        self.app.action = Mock(return_value=("Change type", ("fleet_type",)))

    def begin(self, commit):
        with patch("openreunion.dos.original_ui.tk.Entry", FakeEntry):
            self.app.begin_name_entry("Transfer fleet", commit, 24, 56)
        return FakeEntry.instances[-1]

    def press_outside_editor(self):
        event = Mock(x=200, y=120, num=1)
        self.app.original_press(event)

    def test_valid_outside_click_commits_once_and_arms_fleet_type(self):
        committed = []

        def commit(value):
            if not value:
                raise GameError("Enter a fleet name.")
            self.app.new_fleet_view.name = value
            committed.append(value)

        entry = self.begin(commit)
        entry.value = "Custom Group"

        self.press_outside_editor()

        self.assertEqual(committed, ["Custom Group"])
        self.assertEqual(self.app.new_fleet_view.name, "Custom Group")
        self.assertIsNone(self.app.equipment_editor)
        self.assertIsNone(self.app.name_editor_submit)
        self.assertEqual(self.app.pointer.presses, [(1, 22, True)])
        self.app.action.assert_called_once_with(22)

    def test_invalid_submit_keeps_editor_and_does_not_arm_pointer(self):
        committed = []
        original_draft = self.app.new_fleet_view.name

        def commit(value):
            if not value.strip():
                raise GameError("Fleet name is required.")
            committed.append(value)

        entry = self.begin(commit)
        entry.value = ""

        with self.assertRaises(GameError):
            self.press_outside_editor()

        self.assertEqual(committed, [])
        self.assertEqual(self.app.new_fleet_view.name, original_draft)
        self.assertIs(self.app.equipment_editor, entry)
        self.assertIsNotNone(self.app.name_editor_submit)
        self.assertEqual(self.app.pointer.presses, [])
        self.app.action.assert_not_called()

    def test_enter_commits_and_escape_cancels_callback_and_editor(self):
        committed = []
        entry = self.begin(committed.append)
        entry.value = "Entered Group"

        entry.bindings["<Return>"](Mock(keysym="Return"))
        self.assertEqual(committed, ["Entered Group"])
        self.assertIsNone(self.app.equipment_editor)
        self.assertIsNone(self.app.name_editor_submit)

        entry = self.begin(committed.append)
        entry.bindings["<Escape>"](Mock(keysym="Escape"))
        self.assertIsNone(self.app.equipment_editor)
        self.assertIsNone(self.app.name_editor_submit)
        self.assertTrue(entry.destroyed)
        self.assertEqual(committed, ["Entered Group"])

    def test_queued_focusout_after_editor_submit_preserves_armed_click(self):
        entry = self.begin(lambda value: None)
        entry.value = "Custom Group"
        self.press_outside_editor()
        self.app.original.focus_owner = self.app.original

        self.app.cancel_original_pointer(
            SimpleNamespace(type=original_ui.tk.EventType.FocusOut)
        )

        self.assertEqual(self.app.pointer.presses, [(1, 22, True)])
        self.assertEqual(self.app.pointer.cancels, [])

    def test_external_focusout_and_unmap_still_cancel_pointer(self):
        for event_type in (original_ui.tk.EventType.FocusOut, original_ui.tk.EventType.Unmap):
            with self.subTest(event_type=event_type):
                self.app.pointer.presses = [(1, 22, True)]
                self.app.pointer.cancels = []
                self.app.original.focus_owner = object()

                self.app.cancel_original_pointer(SimpleNamespace(type=event_type))

                self.assertEqual(self.app.pointer.cancels, [{"reset": True}])


if __name__ == "__main__":
    unittest.main()
