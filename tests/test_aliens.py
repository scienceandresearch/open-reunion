"""Alien world/fleet invariants and regressions for original pointer defects."""
from copy import deepcopy
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.core import GameError
from openreunion.dos.aliens import (fleet_at,store_fleet,validate_civilizations,route_fleet,attack_order,
    reset_world,settle_world,unload_fleet,destroy_civilization,system_disaster)
from openreunion.dos.campaign import random_bounded


class AlienHelpersTests(unittest.TestCase):
    def test_dormant_fleet_slots_preserved_independently_of_count(self):
        civilizations=[[0]*228 for _ in range(11)];race=civilizations[5];race[38]=4
        row=list(range(27));store_fleet(race,7,row)
        validate_civilizations(civilizations)
        self.assertEqual(fleet_at(race,7),row);self.assertEqual(race[38],4)
        for index in (0,8,True):
            with self.assertRaises(GameError):fleet_at(race,index)
        race[38]=8
        with self.assertRaises(GameError):validate_civilizations(civilizations)

    def test_same_destination_retains_route_but_new_attack_gets_delay(self):
        row=[0]*27;row[8:11]=[1,7,0];row[2:8]=[1,3,0,19,0,2]
        original=deepcopy(row)
        self.assertEqual(route_fleet(row,(1,7,0),1994),(row,1994))
        ordered,seed=attack_order(row,(1,7,0),70,3,1994,force_kind=True)
        expected,roll=random_bounded(1994,30)
        self.assertEqual(seed,expected);self.assertEqual(ordered[5:7],list(struct.pack("<H",5+roll)))
        self.assertEqual((ordered[0],ordered[7]),(3,3));self.assertEqual(row,original)

    def test_reset_preserves_terrain_and_optional_population(self):
        raw=[55]*65
        minimal=reset_world(raw,erase_population=False);full=reset_world(raw)
        self.assertEqual(minimal[13:20],raw[13:20]);self.assertEqual(full[13:20],[0]*7)
        self.assertEqual(full[21:27],raw[21:27]);self.assertEqual(full[59:],raw[59:])
        self.assertFalse(any(full[27:59]));self.assertEqual(raw,[55]*65)

    def test_all_eight_undorling_and_earth_stocks_are_distinct(self):
        rules={key+suffix:(list(range(1,9)) if suffix=="_base" else [0]*8)
               for key in ("undorling","earth") for suffix in ("_base","_spread")}
        for owner in (8,12):
            raw=[0]*65;raw[25:27]=[71,82]
            result,seed=settle_world(raw,owner,1994,rules)
            self.assertEqual(struct.unpack("<8I",bytes(result[27:59])),tuple(range(1,9)))
            self.assertEqual(result[25:27],raw[25:27]);self.assertEqual(result[0],owner)
            expected,_=random_bounded(1994,3000)
            for _ in range(8):expected,_=random_bounded(expected,0)
            self.assertEqual(seed,expected)

    def test_unload_conserves_owned_stocks_and_rejects_overflow(self):
        row=[0]*27;row[2]=1;row[11:27]=struct.pack("<8H",*range(1,9))
        world=[0]*65;world[0]=3;world[27:59]=struct.pack("<8I",*[100]*8)
        moved,updated=unload_fleet(row,world,3)
        self.assertEqual(struct.unpack("<8I",bytes(updated[27:59])),tuple(range(101,109)))
        self.assertEqual(moved[2],0);self.assertEqual(moved[11:27],row[11:27])
        self.assertEqual(unload_fleet(row,world,4)[1],world)
        world[27:31]=struct.pack("<I",2**32-1);before=deepcopy(world)
        with self.assertRaises(GameError):unload_fleet(row,world,3)
        self.assertEqual(world,before);self.assertEqual(row[2],1)

    def test_civilization_destruction_targets_owned_worlds_and_counted_slots(self):
        civilizations=[[0]*228 for _ in range(11)];race=civilizations[1];race[38]=2
        for index in (1,2,7):store_fleet(race,index,[3]*27)
        worlds={key:{"raw":[0]*65} for key in ("1:7:0","1:7:1","2:1:0")}
        for key in worlds:worlds[key]["raw"][0]=3 if key.startswith("1:") else 1
        before=deepcopy((civilizations,worlds));c,w=destroy_civilization(civilizations,worlds,3)
        self.assertEqual(c[1][27],255);self.assertEqual(c[1][38],0)
        self.assertFalse(any(fleet_at(c[1],1)));self.assertFalse(any(fleet_at(c[1],2)))
        self.assertEqual(fleet_at(c[1],7),[3]*27)
        self.assertEqual([w[k]["raw"][0] for k in worlds],[0,0,1])
        self.assertEqual((civilizations,worlds),before)

    def test_catastrophe_removes_only_doomed_records_in_both_banks(self):
        civilizations=[[0]*228 for _ in range(11)];worlds={"4:2:0":{"raw":[0]*65},"1:5:0":{"raw":[0]*65}}
        fleets={"moving":[],"local":[]}
        for key in fleets:
            for system in (4,4,1,4,2):
                row=[0]*161;row[0]=2;row[19:23]=[system,2,0,1];fleets[key].append(row)
        buildings=[[1,system,2,0]+[0]*10 for system in (4,1,4,4,2)]
        _,_,b,f,seed=system_disaster(civilizations,worlds,buildings,fleets,1994)
        self.assertEqual([row[1] for row in b],[1,2])
        for key in fleets:self.assertEqual([row[19] for row in f[key]],[1,2])
        self.assertEqual(seed,1994);self.assertEqual(len(fleets["moving"]),5)

    def test_catastrophe_recalls_incoming_fleets_and_preserves_other_routes(self):
        civilizations=[[0]*228 for _ in range(11)];civilizations[0][38]=1
        alien=[0]*27;alien[8]=4;store_fleet(civilizations[0],1,alien)
        incoming=[0]*161;incoming[19:23]=[4,2,0,4]
        other=[0]*161;other[19:23]=[3,2,0,4]
        result=system_disaster(civilizations,{},[],{"moving":[incoming,other],"local":[]},1994)
        self.assertFalse(any(fleet_at(result[0][0],1)))
        self.assertEqual(result[3]["moving"][0][19:23],[1,5,0,6])
        self.assertEqual(result[3]["moving"][1],other)
        self.assertNotEqual(result[4],1994)


if __name__=="__main__":unittest.main()
