"""Original-free tests of hourly construction, mining and local storage."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest

from test_campaign import session_fixture
from test_colony import building,definition
from openreunion.core import GameError
from openreunion.dos.fleets import storage_limit,validate_fleets
from openreunion.dos.industry import construction_step,derrick_step,mine_step,world_stocks
from openreunion.dos.session import RecoveredSession


def local_fleet(identity,capacity=100,droids=0):
    row=[0]*161
    row[19:22]=identity
    row[157:161]=struct.pack("<HH",droids,capacity)
    return row


def industry_session():
    session=session_fixture()
    session.catalog["buildings"]=[dict(definition(kind),name=f"Building {kind}") for kind in (4,5,7)]
    session.state["fleets"]["local"]=[local_fleet((1,5,0)),local_fleet((1,5,1),droids=2)]
    session.state["worlds"]["1:5:0"]["raw"][59:65]=[70,30,20,30,0,0]
    session.state["products"][1]["stock"]=2
    session.state["buildings"]=[building(4),building(4)]
    return session


class IndustryTests(unittest.TestCase):
    def test_assignment_consumes_one_droid_and_rejects_full_mines_atomically(self):
        session=industry_session()
        session.apply("assign_droid",world_id="1:5:0")
        self.assertEqual(session.state["products"][1]["stock"],1)
        session.apply("assign_droid",world_id="1:5:0")
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("assign_droid",world_id="1:5:0")
        self.assertEqual(session.state,before)

    def test_remote_assignment_uses_local_stock_instead_of_home_stock(self):
        session=industry_session()
        moon=session.state["worlds"]["1:5:1"]["raw"]
        moon[0]=moon[6]=1
        row=building(4)
        row[3]=1
        session.state["buildings"].append(row)
        session.apply("assign_droid",world_id="1:5:1")
        self.assertEqual(session.state["products"][1]["stock"],2)
        self.assertEqual(session.state["fleets"]["local"][1][157:159],[1,0])
        self.assertEqual(session.state["worlds"]["1:5:1"]["raw"][10],1)

    def test_mining_updates_home_global_ores_and_preserves_local_bytes(self):
        session=industry_session()
        session.apply("assign_droid",world_id="1:5:0")
        initial=deepcopy(session.state["resources"])
        local=world_stocks(session.state["worlds"]["1:5:0"]["raw"])
        session.apply("advance",hours=1)
        self.assertEqual(session.state["resources"]["energon"],initial["energon"]+3)
        self.assertEqual(session.state["resources"]["kremir"],initial["kremir"]+2)
        self.assertEqual(world_stocks(session.state["worlds"]["1:5:0"]["raw"]),local)

    def test_mining_uses_each_world_and_its_own_storage(self):
        session=industry_session()
        session.apply("assign_droid",world_id="1:5:0")
        moon=session.state["worlds"]["1:5:1"]["raw"]
        moon[0]=moon[6]=moon[10]=1
        moon[59:65]=[0,90,0,0,0,0]
        home_before=session.state["resources"]["energon"]
        session.apply("advance",hours=1)
        self.assertEqual(session.state["resources"]["energon"],home_before+3)
        self.assertEqual(world_stocks(session.state["worlds"]["1:5:1"]["raw"])[1],9)

    def test_storage_boundary_preserves_original_one_batch_overshoot(self):
        raw=[0]*65
        raw[0]=raw[6]=1
        raw[10]=1
        raw[60]=90
        stocks,seed=mine_step(raw,[0,999,1000,1000,1000,1000],1000,1994)
        self.assertEqual(stocks[1],1008)
        self.assertEqual(seed,1994)
        self.assertEqual(mine_step(raw,stocks,1000,seed),(stocks,seed))
        self.assertEqual(derrick_step(1000,1000,70,1994),(1000,1994))

    def test_construction_uses_moon_industry_not_parent_industry(self):
        session=industry_session()
        row=building(7)
        row[3],row[6]=1,50
        plant=building(22);plant[3]=1
        session.catalog['buildings'].append(dict(definition(22,output=11000),name='Builder Plant'))
        session.state['buildings'].append(plant)
        session.state["buildings"].append(row)
        # An old wrapped world cache must not override the moon's actual plant.
        session.state["worlds"]["1:5:1"]["raw"][4:6]=struct.pack("<H",65500)
        session.apply("advance",hours=1)
        self.assertEqual(session.state["buildings"][-1][6],40)

    def test_more_industry_never_reverses_construction_progress(self):
        capacities=(0,780,28000,28767,28768,32768,65535,156000)
        remaining=[construction_step(100,output,0,0,0,0)[0] for output in capacities]
        self.assertEqual(remaining,sorted(remaining,reverse=True))
        self.assertEqual(remaining[-1],0)
        seeds={construction_step(100,output,0,0,0,0)[1] for output in capacities}
        self.assertEqual(len(seeds),1)

    def test_construction_completion_recalculates_capacity(self):
        session=industry_session()
        session.state["buildings"][0][6]=1
        session.apply("advance",hours=1)
        self.assertEqual(session.state["buildings"][0][6],0)
        self.assertEqual(storage_limit(session.state["fleets"],(1,5,0)),20000)
        self.assertTrue(any("Construction complete" in line for line in session.state["log"]))

    def test_rank_modifiers_and_stage_thresholds(self):
        self.assertEqual(construction_step(81,2000,0,1,0,0)[0],79)
        self.assertTrue(construction_step(81,2000,0,1,0,0)[2])
        self.assertEqual(construction_step(81,2000,0,3,0,0)[0],73)
        self.assertFalse(construction_step(50,0,0,0,0,0)[2])

    def test_fleet_validation_and_missing_storage(self):
        self.assertEqual(storage_limit({"moving":[],"local":[]},(1,5,0)),0)
        with self.assertRaises(GameError):
            validate_fleets({"moving":[],"local":[[0]*160]})
        with self.assertRaises(GameError):
            validate_fleets({"moving":[],"local":[[True]+[0]*160]})

    def test_hourly_progress_and_fleet_bytes_survive_save_load(self):
        session=industry_session()
        session.apply("assign_droid",world_id="1:5:0")
        session.state["buildings"][1][6]=80
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"industry.json"
            session.save(path)
            loaded=RecoveredSession.load(session.catalog,path)
            loaded.apply("advance",hours=72)
            session.apply("advance",hours=72)
            self.assertEqual(loaded.state,session.state)
