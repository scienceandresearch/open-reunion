"""Original-free regression cases for staffing, power and demographic rules."""
from copy import deepcopy
import struct
from pathlib import Path
import tempfile
import unittest

from test_campaign import session_fixture
from openreunion.core import GameError
from openreunion.dos.colony import allocate_colony,building_counts,daily_tax,population_capacity,population_step,colony_day,clear_colony,industrial_output
from openreunion.dos.session import RecoveredSession


def definition(kind,*,category=0,workers=10,power=150,output=0,priority=1):
    raw=bytearray(24)
    raw[2]=category
    struct.pack_into("<hih",raw,16,workers,power,output)
    return {"id":kind,"unclassified_fields_hex":raw.hex(),"unclassified_43_44":[priority,0]}


def building(kind):
    return [kind,1,5,0,10,20,0,100,1,0,0,0,0,100]


def world(population=1000,morale=50):
    raw=[0]*65
    raw[13:17]=struct.pack("<i",population)
    raw[19]=morale
    return raw


class ColonyTests(unittest.TestCase):
    def test_daily_tax_and_population_are_applied_in_the_session(self):
        session=session_fixture()
        session.state["date"][3]=23
        credits=session.state["resources"]["credits"]
        session.apply("advance",hours=1)
        self.assertEqual(session.state["resources"]["credits"],credits+270)
        self.assertGreater(struct.unpack_from("<I",bytes(session.state["worlds"]["1:5:0"]["raw"]),13)[0],10000)

    def test_meteor_droid_correction_only_touches_the_affected_colony(self):
        session=session_fixture()
        raw=world(5000)
        raw[0]=raw[6]=raw[10]=1
        raw[17:21]=[20,3,50,100]
        session.state["worlds"]["1:5:0"]["raw"]=raw
        session.state["worlds"]["1:2:0"]["raw"][10]=9
        other=deepcopy(session.state["worlds"]["1:2:0"])
        rows=[building(4),building(4)]
        rows[1][2]=2
        session.state["buildings"]=rows
        session.state["campaign"]["rng"]=0
        session.state["products"][27]["research_state"]=0
        session.state["date"][3]=23
        session.apply("advance",hours=1)
        self.assertEqual(session.state["worlds"]["1:5:0"]["raw"][10],0)
        self.assertEqual(session.state["worlds"]["1:2:0"],other)
        self.assertEqual(len(session.state["buildings"]),1)
        self.assertEqual(session.state["buildings"][0][2],2)
        self.assertGreaterEqual(session.state["campaign"]["idea_timers"][27],250)

    def test_clear_colony_preserves_surface_and_survey_bytes(self):
        raw=list(range(65))
        rows=[building(4),building(5)]
        rows[1][2]=2
        clear_colony(raw,rows,(1,5,0))
        self.assertEqual(raw[8:10],[8,9])
        self.assertEqual(raw[12],12)
        self.assertEqual(raw[20:27],list(range(20,27)))
        self.assertEqual(raw[59:],list(range(59,65)))
        self.assertEqual(raw[27:59],[0]*32)
        self.assertEqual(len(rows),1)

    def test_home_loss_stops_time_and_survives_save_load(self):
        session=session_fixture()
        session.state["date"][3]=23
        session.state["worlds"]["1:5:0"]["raw"][13:17]=struct.pack("<I",500)
        session.apply("advance",hours=24)
        self.assertTrue(session.defeated())
        self.assertEqual(session.state["date"][3],0)
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("advance",hours=1)
        self.assertEqual(session.state,before)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"lost.json"
            session.save(path)
            self.assertTrue(RecoveredSession.load(session.catalog,path).defeated())

    def test_colony_random_sequence_survives_mid_campaign_save(self):
        session=session_fixture()
        session.apply("advance",hours=72)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"colony.json"
            session.save(path)
            loaded=RecoveredSession.load(session.catalog,path)
            loaded.apply("advance",hours=240)
            session.apply("advance",hours=240)
            self.assertEqual(loaded.state,session.state)

    def test_shortage_disables_last_tied_priority_and_retains_previous_assignment(self):
        definitions=[definition(1,category=1,power=0,output=100,priority=255),definition(2),definition(3)]
        buildings=[building(1),building(2),building(3)]
        buildings[2][9:14]=[7,0,8,0,90]
        result=allocate_colony(world(),buildings,definitions,(1,5,0))
        self.assertEqual(result["disabled_types"],[3])
        self.assertEqual((result["power_supply"],result["power_demand"]),(100,150))
        self.assertEqual(buildings[1][13],66)
        self.assertEqual(buildings[2][8:14],[0,7,0,8,0,90])
        self.assertEqual(building_counts(buildings,(1,5,0))[0][2],1)

    def test_empty_and_zero_population_colonies_do_not_divide_by_zero(self):
        result=allocate_colony(world(0),[],[],(1,5,0))
        self.assertEqual((result["population"],result["worker_demand"],result["power_supply"],result["power_demand"]),(1,1,1,1))

    def test_incomplete_and_other_world_buildings_are_untouched(self):
        rows=[building(2),building(2)]
        rows[0][6]=20
        rows[1][2]=2
        before=deepcopy(rows)
        allocate_colony(world(),rows,[definition(2)],(1,5,0))
        self.assertEqual(rows,before)
        self.assertEqual(sum(map(sum,building_counts(rows,(1,5,0)))),0)

    def test_builder_plant_output_uses_condition_and_performance(self):
        rows=[building(22)]
        rows[0][7]=50
        raw=world()
        raw[11]=1
        result=allocate_colony(raw,rows,[definition(22,power=100,output=300)],(1,5,0))
        self.assertEqual(result["industrial_output"],150)
        self.assertEqual(raw[4:6],[150,0])

    def test_real_builder_plant_capacity_increases_across_word_overflow(self):
        definitions=[definition(22,power=0,output=780)]
        outputs=[]
        for condition in (40,41,42,43,50,84,85,100,119):
            row=building(22);row[7]=condition
            result=allocate_colony(world(),[row],definitions,(1,5,0))
            outputs.append(result['industrial_output'])
        self.assertEqual(outputs,sorted(outputs))
        self.assertEqual(outputs[-2],780)

    def test_large_industry_retains_full_capacity_beyond_legacy_cache(self):
        definitions=[definition(22,power=0,output=780,workers=0)]
        rows=[building(22) for _ in range(200)];raw=world()
        result=allocate_colony(raw,rows,definitions,(1,5,0))
        self.assertEqual(result['industrial_output'],156000)
        self.assertEqual(raw[4:6],[255,255])
        self.assertEqual(industrial_output(rows,definitions,(1,5,0)),156000)
        rows[0][6]=1;rows[1][8]=0;rows[2][3]=1
        self.assertEqual(industrial_output(rows,definitions,(1,5,0)),153660)

    def test_daily_session_updates_owned_colony_allocation_only_at_midnight(self):
        session=session_fixture()
        session.catalog["buildings"]=[definition(2)]
        session.state["buildings"]=[building(2)]
        session.state["date"][3]=22
        session.apply("advance",hours=1)
        self.assertEqual(session.state["buildings"][0][8],1)
        session.apply("advance",hours=1)
        self.assertEqual(session.state["buildings"][0][8],0)
        self.assertGreater(struct.unpack_from("<I",bytes(session.state["worlds"]["1:5:0"]["raw"]),13)[0],10000)

    def test_population_decline_truncates_toward_zero_and_morale_moves_in_steps(self):
        raw=population_step(world(15000,50),10000,30)
        self.assertEqual(struct.unpack_from("<i",bytes(raw),13)[0],14667)
        self.assertEqual(raw[19],45)
        self.assertEqual(population_step(world(500,0),500,0)[19],0)

    def test_capacity_retains_morale_and_university_thresholds(self):
        self.assertEqual(population_capacity(100000,30,100000,100000,200000,1,1),100000)
        self.assertEqual(population_capacity(100000,30,100000,100000,200000,1,0),80000)
        self.assertEqual(population_capacity(100000,9,100000,100000,200000,1,1),500)
        self.assertEqual(population_capacity(100000,50,100000,100000,20000,2,1),15000)

    def test_tax_rounds_half_away_from_zero_without_float_drift(self):
        raw=world(250,0)
        raw[17],raw[18]=10,1
        self.assertEqual(daily_tax(raw),1)
        raw[13:17]=struct.pack("<i",-250)
        self.assertEqual(daily_tax(raw),-1)
        raw[18]=0
        self.assertEqual(daily_tax(raw),0)

    def test_invalid_building_data_rolls_back_daily_advance(self):
        session=session_fixture()
        session.state["buildings"]=[building(99)]
        session.state["date"][3]=23
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("advance",hours=1)
        self.assertEqual(session.state,before)
