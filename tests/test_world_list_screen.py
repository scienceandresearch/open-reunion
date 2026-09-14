"""Moon identity, scroll bounds and read-only graphical list regressions."""
from copy import deepcopy
import unittest

from test_world_lists import fixture
from openreunion.dos.world_list_screen import WorldListView, list_lines


class WorldListScreenTests(unittest.TestCase):
    def test_two_line_moon_links_share_identity_and_do_not_leak_hidden_worlds(self):
        catalog, state = fixture()
        catalog['system_names'] = ['System '+str(i) for i in range(8)]
        for i,w in enumerate(catalog['worlds']):
            w['name'] = 'World '+str(i)
            state['worlds'][w['id']]['raw'][0] = state['worlds'][w['id']]['raw'][6] = 1
        before = deepcopy(state)
        rows = list_lines(state,catalog,1)
        self.assertEqual([r[0] for r in rows], ['1:1:0','1:1:1','1:1:1'])
        self.assertEqual(rows[1][2], 'System 0 system planet World 0')
        self.assertEqual(rows[2][2], 'moon World 1')
        self.assertEqual(rows[2][1], ' '*len(rows[1][1]))
        targets = WorldListView().targets(rows)
        self.assertEqual(targets[1][2],targets[2][2])
        self.assertEqual(state,before)

    def test_scroll_and_shrinking_results_never_leave_invalid_rows(self):
        rows = [('1:1:0','Colony on ','Test')]*142
        view = WorldListView()
        view.scroll_to(rows,194)
        self.assertEqual(view.offset,127)
        self.assertEqual(len(view.targets(rows)),16)
        x,y,w,h = view.scrollbar(rows)
        self.assertTrue(56 <= y < y+h <= 195)
        view.sync(rows[:2])
        self.assertEqual(view.offset,0)
        self.assertEqual(view.scrollbar([]),(311,56,3,137))
        self.assertEqual(len(view.targets([])),1)


if __name__ == '__main__':
    unittest.main()
