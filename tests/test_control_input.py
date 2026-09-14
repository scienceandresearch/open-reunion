import unittest
from openreunion.dos.control_input import PanelPress


class PanelPressTests(unittest.TestCase):
    def test_drag_cancel_and_return_to_original_target(self):
        p=PanelPress();p.press(1,1,True)
        self.assertEqual(p.release(1,2,True),0)
        p.press(1,1,True)
        self.assertEqual(p.release(1,1,True),1)
        self.assertEqual(p.release(1,1,True),0)

    def test_chord_waits_for_both_buttons_and_cannot_retarget(self):
        p=PanelPress();p.press(1,1,True);p.press(3,2,True)
        self.assertEqual(p.release(1,1,True),0)
        self.assertEqual(p.release(3,1,True),1)
        p.press(3,13,True)
        self.assertEqual(p.release(3,13,True),13)

    def test_blocked_press_and_interrupted_layout_do_not_leak(self):
        p=PanelPress();p.press(1,1,False)
        self.assertEqual(p.release(1,1,True),0)
        p.press(1,1,True);p.cancel();p.press(3,1,True)
        self.assertEqual(p.release(1,1,True),0)
        self.assertEqual(p.release(3,1,True),0)
        p.press(1,1,True)
        self.assertEqual(p.release(1,1,False),0)

    def test_focus_reset_and_blank_press_never_dispatch(self):
        p=PanelPress();p.press(1,1,True);p.cancel(reset=True)
        self.assertFalse(p.buttons)
        self.assertEqual(p.release(1,1,True),0)
        p.press(1,0,False)
        self.assertEqual(p.release(1,1,True),0)
