"""Map visibility and presentation isolation with synthetic data."""
from copy import deepcopy
import unittest

from test_recovered import fixture
from openreunion.dos.map_screen import MapView, system_choices


class MapTests(unittest.TestCase):
    def test_antares_story_concealment_hides_the_primary_target(self):
        catalog, state = fixture()
        state['known_systems'][3] = 1
        state['campaign']['flags']['5d90'] = 1
        catalog['worlds'] = [dict(id='4:1:0', system=4, planet=1, moon=0, index=1,
                                  name='Test', orbital_display_bytes=[10, 50, 30])]
        view = MapView(system=4, planet=1)
        self.assertEqual(view.bodies(state, catalog), [])
        self.assertEqual(view.targets(state, catalog, []), [])

    def test_system_switches_require_research_and_coordinates(self):
        _, state = fixture()
        state['products'][13]['research_state'] = 3
        state['products'][14]['research_state'] = 3
        self.assertEqual(system_choices(state), [])
        state['products'][14]['research_state'] = 5
        self.assertEqual(system_choices(state), [1, 2])

    def test_hidden_primaries_and_unvisited_moons_do_not_get_targets(self):
        catalog, state = fixture()
        catalog['worlds'] = [dict(id=f'1:1:{moon}', system=1, planet=1, moon=moon, index=moon+1,
                                  name='Primary' if not moon else 'Moon', orbital_display_bytes=[10, 50, 30]) for moon in (0, 1)]
        visibility = state['campaign']['navigation']['planet_visibility']
        visibility[0] = 255
        self.assertEqual(MapView().bodies(state, catalog), [])
        visibility[0] = 0
        self.assertEqual(len(MapView().bodies(state, catalog)), 1)
        self.assertEqual(MapView(planet=1).bodies(state, catalog), [])
        visibility[0] = 1
        before = deepcopy(state)
        first = MapView(planet=1).bodies(state, catalog)
        later = MapView(planet=1, ticks=100).bodies(state, catalog)
        self.assertEqual(first[0]['world']['id'], '1:1:1')
        self.assertNotEqual(first[0]['rect'], later[0]['rect'])
        self.assertEqual(state, before)
