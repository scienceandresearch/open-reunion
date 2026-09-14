"""Original-free colony deployment and automatic positioning regressions."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest

from test_surface import surface_session
from test_colony import building
from openreunion.core import GameError
from openreunion.dos.session import RecoveredSession
from openreunion.dos.surface import automatic_position,place_unpositioned,occupancy


def settlement_session():
    session=surface_session()
    session.catalog["settlement_options"]=[2,3,22,4,17,7]
    session.state["ranks"]["builder"]=2
    session.state["levels"]["builder"]=20
    session.state["products"][6]["research_state"]=5
    session.state["resources"]["credits"]=500000
    raw=session.state["worlds"]["1:5:1"]["raw"]
    raw[2]=raw[21]=1
    raw[12]=30
    session.state["fleets"]["local"]=session.state["fleets"]["local"][:1]
    return session


class SettlementTests(unittest.TestCase):
    def test_colonization_pays_bundle_and_initializes_local_defense(self):
        session=settlement_session()
        session.apply("colonize",world_id="1:5:1",options=[3,7])
        self.assertEqual(session.state["resources"]["credits"],399800)
        row=session.state["deployments"][0]
        self.assertEqual(row[:4],[0,1,5,1])
        self.assertEqual(row[4:16],[0,0,1,0,0,0,0,0,0,0,1,0])
        raw=session.state["worlds"]["1:5:1"]["raw"]
        self.assertEqual(raw[0],1)
        self.assertIn(raw[7],(1,2))
        self.assertFalse(raw[6])
        self.assertEqual(session.state["fleets"]["local"][-1][19:23],[1,5,1,7])

    def test_daily_site_completion_then_staggered_buildings(self):
        session=settlement_session()
        session.apply("colonize",world_id="1:5:1",options=[3,7])
        world=next(w for w in session.catalog["worlds"] if w["id"]=="1:5:1")
        session._settlement_day(session.state,world)
        session._settlement_day(session.state,world)
        raw=session.state["worlds"]["1:5:1"]["raw"]
        self.assertEqual(raw[6:8],[1,0])
        self.assertEqual(raw[17:20],[20,3,30])
        self.assertTrue(2000<=struct.unpack_from("<I",bytes(raw),13)[0]<=4999)
        self.assertEqual([b[0] for b in session.state["buildings"]],[1])
        self.assertNotIn(255,session.state["buildings"][0][4:6])
        for _ in range(80):
            session._deployment_hour(session.state)
        self.assertEqual([b[0] for b in session.state["buildings"]],[1,3,7])
        self.assertEqual(session.state["deployments"],[])

    def test_completing_first_entry_does_not_skip_next_entry(self):
        session=settlement_session()
        session.state["deployments"]=[[1,1,5,1]+[0]*12,[1,1,5,1,1,0]+[0]*10]
        session._deployment_hour(session.state)
        self.assertEqual(session.state["deployments"],[])
        self.assertEqual([b[0] for b in session.state["buildings"]],[2])

    def test_rejected_settlement_and_options_are_atomic(self):
        for mutate in (lambda s:s.state["ranks"].update(builder=1),
                       lambda s:s.state["products"][6].update(research_state=0),
                       lambda s:s.state["resources"].update(credits=99999),
                       lambda s:s.state["worlds"]["1:5:1"]["raw"].__setitem__(12,29),
                       lambda s:s.state["worlds"]["1:5:1"]["raw"].__setitem__(2,0)):
            session=settlement_session()
            mutate(session)
            before=deepcopy(session.state)
            with self.assertRaises(GameError):
                session.apply("colonize",world_id="1:5:1")
            self.assertEqual(session.state,before)
        session=settlement_session()
        for options in ([2,2],[1],[True],[8]):
            with self.assertRaises(GameError):
                session.apply("colonize",world_id="1:5:1",options=options)

    def test_automatic_placement_reserves_existing_buildings(self):
        session=settlement_session()
        raw=session.state["worlds"]["1:5:1"]["raw"]
        first=building(4)
        first[3:6]=[1,255,255]
        fixed=building(4)
        fixed[3:6]=[1,5,3]
        rows=[first,fixed]
        place_unpositioned(session.catalog,raw,rows,(1,5,1))
        self.assertEqual(fixed[4:6],[5,3])
        self.assertNotEqual(first[4:6],fixed[4:6])
        self.assertNotIn(255,first[4:6])

    def test_no_space_does_not_create_out_of_bounds_buildings_or_stop_time(self):
        session=settlement_session()
        definition=session.catalog["buildings"][3]
        self.assertIsNone(automatic_position(definition,50,20,[True]*1000))
        session.catalog["surface_rules"]["blocked_hex"][0]="01"+"00"*255
        session.state["deployments"]=[[1,1,5,1,1,0]+[0]*10]
        session.apply("advance",hours=1)
        self.assertEqual(session.state["buildings"][-1][4:6],[255,255])
        self.assertEqual(session.state["deployments"],[])

    def test_automatic_placement_finds_edge_and_exact_size_sites(self):
        definition=dict(settlement_session().catalog['buildings'][1],width=4,height=4)
        for width,height,position in ((22,30,(7,1)),(22,30,(19,27)),(4,4,(1,1))):
            with self.subTest(size=(width,height),position=position):
                blocked=[True]*(width*height)
                for y in range(position[1],position[1]+4):
                    for x in range(position[0],position[0]+4):blocked[(y-1)*width+x-1]=False
                before=list(blocked)
                self.assertEqual(automatic_position(definition,width,height,blocked),position)
                self.assertEqual(blocked,before)
        self.assertEqual(automatic_position(definition,22,30,[False]*660),(9,13))

    def test_saved_unpositioned_buildings_use_distinct_edge_sites(self):
        session=settlement_session();raw=session.state['worlds']['1:5:1']['raw']
        raw[0]=raw[6]=raw[21]=1;raw[22]=0
        tiles=bytearray([1])*96
        for left,top in ((11,1),(11,5)):
            for y in (top,top+1):
                for x in (left,left+1):tiles[(y-1)*12+x-1]=0
        session.catalog['surface_maps']['MAP1_0.MAP']['tiles_hex']=tiles.hex()
        session.catalog['surface_rules']['blocked_hex'][0]='00'+'01'+'00'*254
        for _ in range(2):
            row=building(4);row[3:6]=[1,255,255];session.state['buildings'].append(row)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'edge.json';session.save(path)
            loaded=RecoveredSession.load(session.catalog,path)
            loaded.apply('prepare_surface',world_id='1:5:1')
            self.assertEqual([b[4:6] for b in loaded.state['buildings']],[[11,1],[11,5]])
            loaded.save(path);resumed=RecoveredSession.load(session.catalog,path)
            resumed.apply('prepare_surface',world_id='1:5:1')
            self.assertEqual(resumed.state,loaded.state)

    def test_daily_and_hourly_settlement_continue_after_save_load(self):
        session=settlement_session()
        session.apply("colonize",world_id="1:5:1",options=[3,7])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"settlement.json"
            session.save(path)
            loaded=RecoveredSession.load(session.catalog,path)
            loaded.apply("advance",hours=120)
            session.apply("advance",hours=120)
            self.assertEqual(loaded.state,session.state)
            self.assertTrue(loaded.state["worlds"]["1:5:1"]["raw"][6])
