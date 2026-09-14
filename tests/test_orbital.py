"""Orbital cargo conservation, discovery gates and atomic deployment tests."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest

from test_surface import surface_session
from openreunion.core import GameError
from openreunion.dos.fleets import payload_count,consume_payload
from openreunion.dos.orbital import establish_station
from openreunion.dos.session import RecoveredSession


def fleet(kind=2,identity=(1,5,0),status=2,stock=2,offset=37):
    row=[0]*161
    row[0]=kind
    row[19:23]=[*identity,status]
    row[offset:offset+2]=struct.pack("<h",stock)
    return row


def orbital_session():
    session=surface_session()
    raw=session.state["worlds"]["1:5:1"]["raw"]
    raw[2]=raw[3]=raw[21]=1
    raw[12]=10
    session.state["products"][6]["research_state"]=0
    session.state["campaign"]["idea_timers"][6]=-1
    session.state["fleets"]["moving"]=[fleet(),fleet(4)]
    return session


class OrbitalTests(unittest.TestCase):
    def test_payload_is_shared_with_moons_but_excludes_wrong_orbit_type_and_status(self):
        fleets={"moving":[fleet(),fleet(identity=(1,5,8),offset=67),fleet(identity=(1,6,0)),
                          fleet(identity=(2,5,0)),fleet(status=4),fleet(4)],"local":[fleet()]}
        self.assertEqual(payload_count(fleets,(1,5,1),"miner_station"),4)
        consume_payload(fleets,(1,5,1),"miner_station",3)
        self.assertEqual(fleets["moving"][0][37:39],[0,0])
        self.assertEqual(fleets["moving"][1][67:69],[1,0])
        self.assertEqual(payload_count(fleets,(1,5,1),"miner_station"),1)
        self.assertEqual(payload_count(fleets,(1,5,1),"solar_satellite"),2)

    def test_preferred_fleet_is_consumed_first_then_remaining_records(self):
        fleets={"moving":[fleet(stock=5),fleet(stock=2)],"local":[]}
        consume_payload(fleets,(1,5,7),"miner_station",4,preferred=1)
        self.assertEqual([r[37] for r in fleets["moving"]],[3,0])

    def test_bad_cargo_shortages_and_indexes_are_rejected_without_writes(self):
        for stock,quantity,preferred in ((-2,1,None),(1,2,None),(5,0,None),(5,1,True),(5,1,8)):
            fleets={"moving":[fleet(stock=stock)],"local":[]}
            before=deepcopy(fleets)
            with self.assertRaises(GameError):
                consume_payload(fleets,(1,5,1),"miner_station",quantity,preferred)
            self.assertEqual(fleets,before)

    def test_station_claims_world_supplies_droid_and_schedules_control_centre(self):
        session=orbital_session()
        products=deepcopy(session.state["products"])
        credits=session.state["resources"]["credits"]
        session.apply("deploy_station",world_id="1:5:1")
        raw=session.state["worlds"]["1:5:1"]["raw"]
        self.assertEqual((raw[0],raw[6],raw[10],raw[12]),(1,0,1,30))
        self.assertEqual(session.state["fleets"]["moving"][0][37:39],[1,0])
        self.assertEqual(session.state["products"],products)
        self.assertEqual(session.state["resources"]["credits"],credits)
        self.assertTrue(20<=session.state["campaign"]["idea_timers"][6]<60)
        self.assertEqual(session.state["events"][-1]["id"],4)
        row=session.state["buildings"][-1]
        self.assertEqual(row[:4],[25,1,5,1])
        self.assertNotIn(255,row[4:6])
        self.assertTrue(100<=row[6]<160)
        self.assertFalse(session.state["assisted"])

    def test_station_research_is_scheduled_only_once_and_keeps_original_survey_increment(self):
        for state,timer,suitable,editable in ((0,-1,1,1),(0,20,1,1),(5,-1,1,1),(0,-1,0,1),(0,-1,1,0)):
            session=orbital_session()
            raw=session.state["worlds"]["1:5:1"]["raw"]
            raw[12]=60
            raw[2]=suitable
            session.catalog["surface_rules"]["editable"][0]=editable
            campaign=session.state["campaign"]
            campaign["idea_timers"][6]=timer
            session.state["products"][6]["research_state"]=state
            seed=campaign["rng"]
            raw,messages=establish_station(raw,campaign,session.state["products"],session.catalog["surface_rules"])
            scheduled=state==0 and timer==-1 and suitable and editable
            self.assertEqual(raw[12],70 if scheduled else 60)
            self.assertEqual(messages,[4] if scheduled else [])
            if not scheduled:
                self.assertEqual(campaign["rng"],seed)

    def test_station_rejections_preserve_cargo_world_and_rng(self):
        for at,value in ((0,1),(3,0),(6,1),(7,1),(10,1),(12,9),(12,128),(21,2)):
            session=orbital_session()
            session.state["worlds"]["1:5:1"]["raw"][at]=value
            before=deepcopy(session.state)
            with self.assertRaises(GameError):
                session.apply("deploy_station",world_id="1:5:1")
            self.assertEqual(session.state,before)
        session=orbital_session()
        session.state["fleets"]["moving"][0][22]=4
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("deploy_station",world_id="1:5:1")
        self.assertEqual(session.state,before)

    def test_station_building_limit_does_not_consume_cargo_or_claim_world(self):
        session=orbital_session()
        session.state["buildings"]=[[4,1,5,0,1,1,0,100,0,0,0,0,0,0] for _ in range(1000)]
        before=deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("deploy_station",world_id="1:5:1")
        self.assertEqual(session.state,before)

    def test_solar_deployment_has_five_satellite_limit_and_uses_only_carrier_cargo(self):
        session=orbital_session()
        raw=session.state["worlds"]["1:5:0"]["raw"]
        raw[11]=4
        campaign=deepcopy(session.state["campaign"])
        session.apply("deploy_solar_satellite",world_id="1:5:0",fleet_index=1)
        self.assertEqual(session.state["worlds"]["1:5:0"]["raw"][11],5)
        self.assertEqual(session.state["fleets"]["moving"][0][37],2)
        self.assertEqual(session.state["fleets"]["moving"][1][37],1)
        self.assertEqual(session.state["campaign"],campaign)
        before=deepcopy(session.state)
        for world_id in ("1:5:0","1:5:1","8:1:0"):
            with self.assertRaises(GameError):
                session.apply("deploy_solar_satellite",world_id=world_id)
            self.assertEqual(session.state,before)

    def test_discovery_survey_and_construction_continue_after_save_reload(self):
        session=orbital_session()
        session.apply("deploy_station",world_id="1:5:1")
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"orbital.json"
            session.save(path)
            loaded=RecoveredSession.load(session.catalog,path)
            loaded.apply("advance",hours=72)
            session.apply("advance",hours=72)
            self.assertEqual(loaded.state,session.state)
            self.assertEqual(session.state["products"][6]["research_state"],1)
            self.assertGreater(session.state["worlds"]["1:5:1"]["raw"][12],30)


if __name__=="__main__":
    unittest.main()
