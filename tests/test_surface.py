"""Original-free construction transactions and surface boundary regressions."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest

from test_industry import industry_session
from test_colony import definition,building
from openreunion.core import GameError
from openreunion.dos.session import RecoveredSession
from openreunion.dos.surface import occupancy,placement_fits,footprint,building_available


def surface_session():
    session=industry_session()
    session.catalog["buildings"]=[]
    for kind in range(1,26):
        item=definition(kind,workers=0,power=0)
        fields=bytearray.fromhex(item["unclassified_fields_hex"])
        fields[5]=1
        item.update(name=f"Structure {kind}",price=100,width=2,height=2,tile_ids=[0]*16,unclassified_fields_hex=fields.hex())
        session.catalog["buildings"].append(item)
    session.catalog["surface_rules"]={"groups":list(range(1,12)),"editable":[1]*11,"blocked_hex":["00"*256]*11}
    session.catalog["surface_maps"]={"MAP1_0.MAP":{"width":12,"height":8,"tiles_hex":"00"*96}}
    session.state["buildings"]=[]
    session.state["levels"]["builder"]=10
    session.state["ranks"]["builder"]=1
    raw=session.state["worlds"]["1:5:0"]["raw"]
    raw[3]=raw[21]=1
    return session


class SurfaceTests(unittest.TestCase):
    def test_new_building_charges_once_and_progresses_to_completion(self):
        session=surface_session()
        credits=session.state["resources"]["credits"]
        session.apply("build",world_id="1:5:0",building_id=4,x=2,y=3)
        row=session.state["buildings"][-1]
        self.assertEqual(row[:6],[4,1,5,0,2,3])
        self.assertTrue(100<=row[6]<=159)
        self.assertEqual(session.state["resources"]["credits"],credits-100)
        # Run the same construction entry that the hourly dispatcher calls.
        for _ in range(160):
            session._industry_hour(session.state)
        self.assertEqual(session.state["buildings"][-1][6],0)

    def test_overlap_terrain_edges_and_invalid_coordinates_reject_atomically(self):
        session=surface_session()
        session.apply("build",world_id="1:5:0",building_id=4,x=2,y=3)
        for x,y in ((2,3),(0,1),(12,8),(-1,5),(True,1)):
            before=deepcopy(session.state)
            with self.assertRaises(GameError):
                session.apply("build",world_id="1:5:0",building_id=4,x=x,y=y)
            self.assertEqual(session.state,before)
        session.catalog["surface_rules"]["blocked_hex"][0]="01"+"00"*255
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("build",world_id="1:5:0",building_id=4,x=7,y=3)
        self.assertEqual(session.state,before)
        session.catalog["surface_rules"]["blocked_hex"][0]="00"*256
        session.catalog["buildings"][3].update(width=1,height=1)
        session.apply("build",world_id="1:5:0",building_id=4,x=12,y=8)
        self.assertEqual(session.state["buildings"][-1][4:6],[12,8])

    def test_transparent_footprint_hole_can_overlap_terrain(self):
        item=surface_session().catalog["buildings"][0]
        item["tile_ids"][0]=255
        self.assertNotIn((1,1),footprint(item,1,1))
        self.assertTrue(placement_fits(item,1,1,2,2,[True,False,False,False]))
        self.assertFalse(placement_fits(item,2,1,2,2,[False]*4))

    def test_prerequisites_distinguish_research_rank_and_operating_plants(self):
        session=surface_session()
        definition=session.catalog["buildings"][7]
        fields=bytearray.fromhex(definition["unclassified_fields_hex"])
        fields[0:5]=bytes([1,2,0,1,1])
        definition["unclassified_fields_hex"]=fields.hex()
        session.state["products"][0]["research_state"]=0
        for step in range(4):
            with self.assertRaises(GameError):
                session.apply("build",world_id="1:5:0",building_id=8,x=1,y=1)
            if step==0:
                session.state["products"][0]["research_state"]=5
            elif step==1:
                session.state["ranks"]["builder"]=2
            else:
                plant=building(22 if step==2 else 23)
                plant[4:6]=[6,5] if step==2 else [9,5]
                session.state["buildings"].append(plant)
        session.apply("build",world_id="1:5:0",building_id=8,x=1,y=1)

    def test_living_quarters_add_settlers_at_purchase(self):
        session=surface_session()
        before=struct.unpack_from("<I",bytes(session.state["worlds"]["1:5:0"]["raw"]),13)[0]
        session.apply("build",world_id="1:5:0",building_id=7,x=1,y=1)
        after=struct.unpack_from("<I",bytes(session.state["worlds"]["1:5:0"]["raw"]),13)[0]
        self.assertTrue(800<=after-before<=1299)

    def test_demolition_cost_restrictions_and_map_reuse(self):
        session=surface_session()
        row=building(4)
        row[4:6]=[2,3]
        session.state["buildings"]=[row]
        before=session.state["resources"]["credits"]
        session.apply("demolish",world_id="1:5:0",building_index=0)
        self.assertEqual(session.state["resources"]["credits"],before-2000)
        session.apply("build",world_id="1:5:0",building_id=4,x=2,y=3)
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("demolish",world_id="1:5:0",building_index=0)
        self.assertEqual(session.state,before)
        session.state["buildings"][0][0:7]=[1,1,5,0,2,3,0]
        with self.assertRaises(GameError):
            session.apply("demolish",world_id="1:5:0",building_index=0)

    def test_building_limit_and_credit_underflow_preserve_state(self):
        session=surface_session()
        session.state["buildings"]=[building(4)]*1000
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("build",world_id="1:5:0",building_id=4,x=1,y=1)
        self.assertEqual(session.state,before)
        session.state["buildings"]=[building(4)]
        session.state["resources"]["credits"]=1000
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("demolish",world_id="1:5:0",building_index=0)
        self.assertEqual(session.state,before)

    def test_new_construction_save_continuation(self):
        session=surface_session()
        session.apply("build",world_id="1:5:0",building_id=7,x=1,y=1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"surface.json"
            session.save(path)
            loaded=RecoveredSession.load(session.catalog,path)
            loaded.apply("advance",hours=20)
            session.apply("advance",hours=20)
            self.assertEqual(loaded.state,session.state)
