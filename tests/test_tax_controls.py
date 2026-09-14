"""Tax selection transactions and their real daily/save consequences."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from test_orbital import orbital_session
from openreunion.core import GameError
from openreunion.dos.colony import set_tax_level
from openreunion.dos.session import RecoveredSession


class TaxControlTests(unittest.TestCase):
    def test_selection_changes_only_world_tax_and_log_without_immediate_income(self):
        for level in range(8):
            s=orbital_session();before=deepcopy(s.state)
            s.apply('set_tax',world_id='1:5:0',level=level)
            before['worlds']['1:5:0']['raw'][18]=level
            self.assertEqual(s.state['log'][:-1],before['log']);before['log']=s.state['log']
            self.assertEqual(s.state,before)

    def test_invalid_levels_are_atomic(self):
        for level in (-1,8,255,True,1.5,'3',None):
            s=orbital_session();before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply('set_tax',world_id='1:5:0',level=level)
            self.assertEqual(s.state,before)

    def test_only_owned_active_discovered_colonies_are_eligible(self):
        for owner,colony in ((0,0),(0,1),(1,0),(2,1),(255,1)):
            s=orbital_session();raw=s.state['worlds']['1:5:0']['raw'];raw[0]=owner;raw[6]=colony;before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply('set_tax',world_id='1:5:0',level=4)
            self.assertEqual(s.state,before)
        for hidden in ('world','system','missing'):
            s=orbital_session()
            if hidden=='world':s.state['campaign']['navigation']['planet_visibility'][4]=254
            if hidden=='system':s.state['known_systems'][0]=0
            before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply('set_tax',world_id='9:9:9' if hidden=='missing' else '1:5:0',level=4)
            self.assertEqual(s.state,before)

    def test_first_midnight_uses_selected_tax_and_later_morale_responds(self):
        low=orbital_session();high=orbital_session()
        low.apply('set_tax',world_id='1:5:0',level=0);high.apply('set_tax',world_id='1:5:0',level=7)
        self.assertEqual(low.state['resources'],high.state['resources'])
        for s in (low,high):s.state['date'][3]=23;s.apply('advance',hours=1)
        self.assertGreater(high.state['resources']['credits'],low.state['resources']['credits'])
        for s in (low,high):s.apply('advance',hours=48)
        self.assertLess(high.state['worlds']['1:5:0']['raw'][19],low.state['worlds']['1:5:0']['raw'][19])

    def test_saved_tax_continues_income_population_and_rng(self):
        s=orbital_session();s.apply('set_tax',world_id='1:5:0',level=4)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'tax.json';s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            for current in (s,loaded):current.apply('advance',hours=72)
            self.assertEqual(s.state,loaded.state)

    def test_helper_retains_other_fields_and_accepts_zero_without_mutating_input(self):
        raw=[0]*65;raw[0]=raw[6]=1;raw[18]=7;raw[19]=55
        updated=set_tax_level(raw,0)
        self.assertEqual((raw[18],updated[18],updated[19]),(7,0,55))
