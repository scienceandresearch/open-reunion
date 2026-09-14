"""Navigation transactions, first contact, discovery and saved continuation."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest
from test_cargo import cargo_session
from openreunion.core import GameError
from openreunion.dos.navigation import depart,travel_hour,remaining_hours,arrival,advance_fleet,orbit_toggle,validate_navigation
from openreunion.dos.session import RecoveredSession
from openreunion.dos.strategy import navigation_view


class NavigationTests(unittest.TestCase):
    def test_launch_route_arrive_land_and_return_preserve_cargo(self):
        s=cargo_session();s.state["levels"]["pilot"]=10;s.state["ranks"]["pilot"]=1
        s.apply("transfer_cargo",fleet_index=0,ore="detoxin",quantity=100)
        s.apply("orbit",fleet_index=0);s.apply("travel",fleet_index=0,destination=[1,5,1])
        row=s.state["fleets"]["moving"][0];hours=remaining_hours(row,10)
        self.assertEqual(row[19:23],[1,5,1,4])
        for _ in range(hours-1):s._fleet_hour(s.state)
        self.assertEqual(s.state["fleets"]["moving"][0][22],4)
        s._fleet_hour(s.state);self.assertEqual(s.state["fleets"]["moving"][0][22],2)
        s.apply("orbit",fleet_index=0)
        self.assertEqual(s.state["fleets"]["moving"][0][22],1)
        self.assertEqual(struct.unpack_from("<I",bytes(s.state["fleets"]["moving"][0]),109)[0],100)
        self.assertFalse(s.state["assisted"])

    def test_illegal_routes_and_landing_leave_state_unchanged(self):
        for mutation,action,arguments in (
            (lambda s:None,"travel",{"destination":[1,5,1]}),
            (lambda s:s.state["fleets"]["moving"][0].__setitem__(22,2),"travel",{"destination":[1,5,1]}),
            (lambda s:s.state["fleets"]["moving"][0].__setitem__(22,4),"orbit",{}),
            (lambda s:s.state["worlds"]["1:5:0"]["raw"].__setitem__(21,2),"orbit",{}),
            (lambda s:s.state["fleets"]["moving"][0].__setitem__(slice(29,109),[0]*80),"orbit",{})):
            s=cargo_session();mutation(s);before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply(action,fleet_index=0,**arguments)
            self.assertEqual(s.state,before)
        s=cargo_session();s.state["levels"]["pilot"]=10;s.apply("orbit",fleet_index=0)
        for dest in ([True,5,0],[1,0,1],[2,1,0],[8,0,0],[1,8,8],[1,5]):
            before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply("travel",fleet_index=0,destination=dest)
            self.assertEqual(s.state,before)

    def test_same_destination_preserves_rng_and_current_travel(self):
        row=cargo_session().state["fleets"]["moving"][0]
        row,seed=depart(row,[1,5,1],1994)
        self.assertEqual(depart(row,[1,5,1],seed),(row,seed))

    def test_two_legs_round_independently_and_middle_leg_takes_an_hour(self):
        row=cargo_session().state["fleets"]["moving"][0]
        row[22]=6;row[23:29]=struct.pack("<3h",201,1,201)
        self.assertEqual(remaining_hours(row,10),39)
        for elapsed in range(39):
            self.assertEqual(remaining_hours(row,10),39-elapsed)
            row,arrived=travel_hour(row,10)
        self.assertTrue(arrived);self.assertEqual(row[22],2)

    def test_first_hyperspace_notice_fires_once(self):
        s=cargo_session();c=navigation_view(s.state["campaign"]);row=s.state["fleets"]["moving"][0]
        row[22]=5;row[23:29]=struct.pack("<3h",0,1,200)
        args=(c,s.state["products"],s.state["known_systems"],s.state["worlds"],10)
        _,events=advance_fleet(row,*args);self.assertEqual(events,[("message",34),("scene",2)])
        _,events=advance_fleet(row,*args);self.assertEqual(events,[])

    def test_pirate_discovery_uses_arriving_fleet_destination(self):
        s=cargo_session();c=navigation_view(s.state["campaign"]);c["navigation"]["flags"]["5d71"]=1
        s.state["products"][18]["research_state"]=0
        row=s.state["fleets"]["moving"][0];row[22]=2
        _,events=arrival(row,c,s.state["products"],s.state["known_systems"],s.state["worlds"])
        self.assertEqual(events,[]);self.assertEqual(c["navigation"]["flags"]["5d71"],1)
        row[19:22]=[2,1,0]
        _,events=arrival(row,c,s.state["products"],s.state["known_systems"],s.state["worlds"])
        self.assertEqual(events,[("message",18),("dialog",6)])
        self.assertEqual(s.state["products"][18]["research_state"],3)

    def test_first_contact_schedules_consequences_without_repeating(self):
        s=cargo_session();c=navigation_view(s.state["campaign"]);products=s.state["products"];products[7]["research_state"]=0
        row=s.state["fleets"]["moving"][0];row[22]=2
        s.state["worlds"]["1:5:0"]["raw"][0]=2
        _,events=arrival(row,c,products,s.state["known_systems"],s.state["worlds"])
        self.assertEqual(c["alien_status"][0],4);self.assertIn(("message",5),events)
        self.assertGreater(c["idea_timers"][7],0)
        self.assertGreater(c["navigation"]["timers"]["5d5c"],c["navigation"]["timers"]["5d4e"])
        before=deepcopy(c);_,events=arrival(row,c,products,s.state["known_systems"],s.state["worlds"])
        self.assertEqual(c,before);self.assertEqual(events,[])

    def test_special_landing_unlocks_technology_once(self):
        s=cargo_session();products=s.state["products"]
        products[21]["research_state"]=products[22]["research_state"]=0
        row=s.state["fleets"]["moving"][0];row[19:23]=[3,2,1,2]
        row,raw,events=orbit_toggle(row,[0]*65,s.state["campaign"],products)
        self.assertEqual((row[22],raw[12]),(1,6));self.assertEqual(events,[("message",21),("scene",4)])
        self.assertEqual([products[i]["research_state"] for i in (21,22)],[3,3])
        _,_,events=orbit_toggle(row,raw,s.state["campaign"],products);self.assertEqual(events,[])

    def test_navigation_save_preserves_transit_and_contact_state(self):
        s=cargo_session();s.state["levels"]["pilot"]=10;s.apply("orbit",fleet_index=0)
        s.apply("travel",fleet_index=0,destination=[1,5,1]);s.apply("advance",hours=2)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"travel.json";s.save(p);loaded=RecoveredSession.load(s.catalog,p)
            s.apply("advance",hours=24);loaded.apply("advance",hours=24)
            self.assertEqual(s.state,loaded.state)

    def test_navigation_records_are_validated(self):
        for mutation in (lambda n:n["flags"].pop("5d48"),lambda n:n["planet_visibility"].pop(),
                         lambda n:n["alien_fleets"][0].append([0]*26),lambda n:n["timers"].update({"5d40":True})):
            nav=navigation_view(cargo_session().state["campaign"])["navigation"]
            from openreunion.dos.navigation import FLAGS,TIMERS
            nav["flags"]={f"{a:x}":nav["flags"][f"{a:x}"] for a in FLAGS}
            nav["timers"]={f"{a:x}":nav["timers"][f"{a:x}"] for a in TIMERS}
            mutation(nav)
            with self.assertRaises(GameError):validate_navigation(nav)
