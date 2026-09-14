"""Original-free control selection and the battle Continue layout."""
from copy import deepcopy
import unittest
from openreunion.core import GameError
from openreunion.dos.control_layouts import select_layout,validate_layouts,result_control_enabled


def layouts():
    rows=[{'id':i,'name':'','buttons':[]} for i in range(1,39)]
    rows[0].update(name='main',buttons=list(range(1,13)));rows[29]['buttons']=[65]
    return rows


class ControlLayoutsTests(unittest.TestCase):
    def test_layout_thirty_selects_continue_and_clears_eleven_slots_and_input(self):
        rows=layouts();before=deepcopy(rows)
        self.assertEqual(select_layout(rows,30,0),{'visible':1,'buttons':[65]+[0]*11,'input':0})
        self.assertEqual(rows,before)
        self.assertEqual(select_layout(rows,1,255)['visible'],255)
        self.assertEqual(select_layout(rows,2,0)['buttons'],[0]*12)

    def test_only_result_phase_exposes_original_continue_control(self):
        catalog={'control_layouts':layouts()}
        for phase in ('setup','fighting','closed'):self.assertFalse(result_control_enabled(catalog,phase))
        self.assertTrue(result_control_enabled(catalog,'result'))
        catalog['control_layouts'][29]['buttons']=[]
        self.assertFalse(result_control_enabled(catalog,'result'))
        with self.assertRaises(GameError):result_control_enabled({},'result')

    def test_malformed_layout_cannot_overrun_the_twelve_button_records(self):
        for bad in (0,39,True):
            with self.assertRaises(GameError):select_layout(layouts(),bad)
        for buttons in ([1]*13,[True],[-1],[256]):
            rows=layouts();rows[29]['buttons']=buttons
            with self.assertRaises(GameError):validate_layouts(rows)


if __name__=='__main__':unittest.main()
