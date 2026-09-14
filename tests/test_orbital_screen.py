"""Visibility, overflow and discovery regressions for the graphical fleet panel."""
import unittest
from copy import deepcopy

from test_recovered import fixture
from openreunion.dos.orbital_screen import orbital_entries, orbital_targets
from openreunion.dos.equipment import new_fleet


def orbit_fixture():
    catalog, state = fixture()
    catalog['worlds'] = [dict(id='1:5:0',system=1,planet=5,moon=0)]
    catalog['alien_names'] = ['Race '+str(i) for i in range(11)]
    state['worlds']['1:5:0'] = {'raw':[0]*65}
    alien = state['campaign']['civilizations'][0]
    alien[38] = 1
    alien[39:66] = [2,0,1,0,0,0,0,0,1,5,1]+[0]*16
    return catalog, state


class OrbitalScreenTests(unittest.TestCase):
    def test_enemy_fleets_require_monitoring_and_show_no_inventory(self):
        catalog, state = orbit_fixture()
        self.assertEqual(orbital_entries(state,catalog,1,5), [])
        state['worlds']['1:5:0']['raw'][9] = 1
        result = orbital_entries(state,catalog,1,5)
        self.assertEqual(result[0]['key'], ('alien',2,0))
        self.assertEqual(set(result[0]), {'key','icon','moon','label','status'})
        state['campaign']['navigation']['planet_visibility'][4] = 255
        self.assertEqual(orbital_entries(state,catalog,1,5), [])

    def test_stationary_fleets_across_moons_and_overflow_are_retained(self):
        catalog, state = orbit_fixture()
        for i in range(20):
            row = new_fleet(2, 'Fleet '+str(i))
            row[21], row[22] = i%2, 1 if i%2 else 2
            state['fleets']['moving'].append(row)
        before = deepcopy(state)
        result = orbital_entries(state,catalog,1,5)
        self.assertEqual(len(result),21)
        self.assertEqual(len(orbital_targets(result,0)),18)
        self.assertEqual(len(orbital_targets(result,1)),3)
        self.assertEqual(result[20]['key'],('alien',2,0))
        self.assertEqual(state,before)
        state['fleets']['moving'][0][22] = 4
        self.assertNotIn(('player',0),[e['key'] for e in orbital_entries(state,catalog,1,5) if e])

    def test_ally_presence_reveals_other_fleets_without_owned_colony(self):
        catalog, state = orbit_fixture()
        state['campaign']['civilizations'][0][27] = 6
        self.assertEqual(len(orbital_entries(state,catalog,1,5)),1)
