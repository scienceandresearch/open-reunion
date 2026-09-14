from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_cargo import cargo_session
from openreunion.core import GameError
from openreunion.dos.exploration import discover_planet
from openreunion.dos.session import RecoveredSession


class ExplorationTests(unittest.TestCase):
    def test_discovery_cap_keeps_original_random_draws(self):
        with patch('openreunion.dos.exploration.random_bounded',side_effect=lambda seed,bound:(seed+1,1)) as random:
            self.assertEqual(discover_planet(254,1,1,0,1,0,[],10,True),(254,12,True,None))
            self.assertEqual([call.args[1] for call in random.call_args_list],[50,5])

    def test_fleets_only_find_their_discovery_class_while_traveling(self):
        row=[0]*161;row[0]=2;row[19]=1;row[22]=4
        with patch('openreunion.dos.exploration.random_bounded',side_effect=lambda seed,bound:(seed+1,1)):
            self.assertEqual(discover_planet(254,1,1,0,0,0,[row],10,False),(0,11,True,'fleet'))
            self.assertEqual(discover_planet(253,1,1,0,0,0,[row],10,False),(253,10,False,None))
            row[22]=2
            self.assertEqual(discover_planet(254,1,1,0,0,0,[row],10,False),(254,11,False,None))

    def test_moons_and_unknown_systems_do_not_consume_discovery_rng(self):
        for moon,known in ((1,1),(0,0),(0,255)):
            with patch('openreunion.dos.exploration.random_bounded') as random:
                self.assertEqual(discover_planet(252,known,1,moon,2,5,[],10,False),(252,10,False,None))
                random.assert_not_called()

    def test_daily_discovery_unlocks_a_real_route_once_per_day(self):
        s=cargo_session();s.state['date'][3]=23;s.state['levels']['pilot']=10
        s.state['campaign']['navigation']['planet_visibility'][:8]=[253]*8
        s.state['campaign']['system_observatories'][0]=1
        s.apply('orbit',fleet_index=0)
        before=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply('travel',fleet_index=0,destination=[1,2,0])
        self.assertEqual(s.state,before)
        with patch('openreunion.dos.exploration.random_bounded',side_effect=lambda seed,bound:(seed+1,1)):
            s.apply('advance',hours=1)
        self.assertEqual(s.state['campaign']['navigation']['planet_visibility'][:8],[253,0]+[253]*6)
        s.apply('travel',fleet_index=0,destination=[1,2,0])
        self.assertEqual(s.state['fleets']['moving'][0][19:23],[1,2,0,4])
        self.assertTrue(any('discovered by observatory' in line for line in s.state['log']))

    def test_discovery_save_continuation_keeps_exact_rng_and_visibility(self):
        s=cargo_session();s.state['date'][3]=23
        s.state['campaign']['navigation']['planet_visibility'][:8]=[253]*8
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'discovery.json';s.save(path)
            loaded=RecoveredSession.load(s.catalog,path)
            s.apply('advance',hours=48);loaded.apply('advance',hours=48)
            self.assertEqual(s.state,loaded.state)
