"""Original cargo click amounts and safety at changing inventory boundaries."""
from copy import deepcopy
import struct
import unittest

from test_cargo import cargo_session
from openreunion.core import GameError
from openreunion.dos.cargo_screen import CargoView


class CargoScreenTests(unittest.TestCase):
    def test_ore_clicks_clamp_to_stock_and_shared_capacity(self):
        s=cargo_session();v=CargoView(0)
        s.state['resources']['detoxin']=251
        for mouse,expected in ((1,100),(1,100),(1,51)):
            args=v.transfer(s.state,s.catalog,'ore','detoxin',True,mouse)
            self.assertEqual(args['quantity'],expected);s.apply('transfer_cargo',**args)
        self.assertIsNone(v.transfer(s.state,s.catalog,'ore','detoxin',True,3))
        args=v.transfer(s.state,s.catalog,'ore','detoxin',False,3)
        self.assertEqual(args['quantity'],-251);s.apply('transfer_cargo',**args)
        s.state['resources']['detoxin']=2000
        args=v.transfer(s.state,s.catalog,'ore','detoxin',True,3)
        self.assertEqual(args['quantity'],1000);s.apply('transfer_cargo',**args)
        self.assertIsNone(v.transfer(s.state,s.catalog,'ore','energon',True,1))

    def test_item_clicks_move_one_and_reserve_queued_inventory(self):
        s=cargo_session();v=CargoView(0)
        for mouse in (1,3):
            args=v.transfer(s.state,s.catalog,'slot',13,True,mouse)
            self.assertEqual(args['quantity'],1);s.apply('transfer_cargo',**args)
        self.assertIsNone(v.transfer(s.state,s.catalog,'slot',13,True,3))
        s.state['products'][1].update(stock=32765,queued=1)
        args=v.transfer(s.state,s.catalog,'slot',13,False,3)
        self.assertEqual(args['quantity'],-1);s.apply('transfer_cargo',**args)
        self.assertIsNone(v.transfer(s.state,s.catalog,'slot',13,False,1))

    def test_travel_and_missing_depots_do_not_offer_or_mutate_cargo(self):
        s=cargo_session();v=CargoView(0)
        original=deepcopy(s.state)
        for status in (2,3,4,5,6,7):
            s.state=deepcopy(original);s.state['fleets']['moving'][0][22]=status
            before=deepcopy(s.state)
            self.assertEqual(v.targets(s.state,s.catalog),[])
            with self.assertRaises(GameError):v.transfer(s.state,s.catalog,'ore','detoxin',True,1)
            self.assertEqual(s.state,before)
        s.state=deepcopy(original);s.state['buildings']=[b for b in s.state['buildings'] if b[0]!=12]
        with self.assertRaisesRegex(GameError,'Space Port'):v.transfer(s.state,s.catalog,'slot',13,True,1)
        s.state=deepcopy(original);s.state['products'][1]['research_state']=1
        with self.assertRaisesRegex(GameError,'changed'):v.transfer(s.state,s.catalog,'slot',13,True,1)

    def test_overfull_ore_never_reverses_a_transfer(self):
        s=cargo_session();v=CargoView(0)
        row=s.state['fleets']['moving'][0]
        row[109:113]=struct.pack('<I',2000)
        before=deepcopy(s.state)
        self.assertIsNone(v.transfer(s.state,s.catalog,'ore','detoxin',True,3))
        self.assertEqual(s.state,before)
        s.state['resources']['detoxin']=v.report(s.state,s.catalog)['storage']+1
        before=deepcopy(s.state)
        self.assertIsNone(v.transfer(s.state,s.catalog,'ore','detoxin',False,3))
        self.assertEqual(s.state,before)

    def test_remote_item_depot_uses_last_matching_record(self):
        s=cargo_session();v=CargoView(0)
        s.state['fleets']['moving'][0][19:22]=[1,5,1]
        raw=s.state['worlds']['1:5:1']['raw'];raw[0]=raw[6]=1
        s.state['buildings'][-1][1:4]=[1,5,1]
        local=[0]*161;local[0]=5;local[19:23]=[1,5,1,7];local[157:159]=struct.pack('<h',1)
        s.state['fleets']['local'] += [local.copy(),local.copy()]
        s.state['fleets']['local'][-1][157]=2
        before=deepcopy(s.state)
        s.apply('transfer_cargo',**v.transfer(s.state,s.catalog,'slot',13,True,3))
        self.assertEqual(s.state['fleets']['local'][:-1],before['fleets']['local'][:-1])
        self.assertEqual(s.state['fleets']['local'][-1][157],1)
        self.assertEqual(s.state['products'],before['products'])
        self.assertEqual(s.state['resources'],before['resources'])


if __name__=='__main__':unittest.main()
