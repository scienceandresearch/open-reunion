"""Cargo conservation, depot isolation and original bug regressions."""
from copy import deepcopy
import struct
import unittest
from test_equipment import equipment_session
from openreunion.core import GameError
from openreunion.dos.cargo import cargo_capacity,cargo_used,validate_cargo_rules,transfer_item
from openreunion.dos.catalog import ORE_KEYS
from openreunion.dos.fleets import storage_limit
from openreunion.dos.industry import world_stocks,set_world_stocks


def cargo_session():
    session=equipment_session()
    session.catalog["cargo_rules"]={"hull_capacity":[500,2000,1000,8000],
        "items":[{"slot":i,"product":2 if i==13 else None,"weight":500 if i==13 else 0} for i in range(1,14)]}
    session.catalog["fleet_rules"][1]["categories"][0]["id"]=2
    session.apply("create_fleet",fleet_type=2)
    session.apply("equip_fleet",fleet_index=0,category=2,hull=1,quantity=2)
    session.state["products"][1].update(stock=5,research_state=5)
    session.state["buildings"].append([12,1,5,0,1,1,0,100,0,0,0,0,0,0])
    return session


class CargoTests(unittest.TestCase):
    def test_maximum_cargo_uses_shared_weight_and_conserves_contents(self):
        s=cargo_session();before=deepcopy(s.state)
        s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=21)
        s.apply("transfer_cargo",fleet_index=0,slot=13,quantity=1,maximum=True)
        self.assertEqual(cargo_used(s.state["fleets"]["moving"][0],s.catalog["cargo_rules"]),521)
        s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=1,maximum=True)
        self.assertEqual(cargo_used(s.state["fleets"]["moving"][0],s.catalog["cargo_rules"]),1000)
        for args in ({"ore":ORE_KEYS[0]},{"slot":13}):
            s.apply("transfer_cargo",fleet_index=0,quantity=-1,maximum=True,**args)
        for key in ("resources","products","fleets"):
            self.assertEqual(s.state[key],before[key])

    def test_maximum_unload_reserves_home_inventory_for_pending_production(self):
        s=cargo_session()
        s.apply("transfer_cargo",fleet_index=0,slot=13,quantity=1,maximum=True)
        s.state["products"][1].update(stock=32764,queued=2)
        s.apply("transfer_cargo",fleet_index=0,slot=13,quantity=-1,maximum=True)
        self.assertEqual(s.state["products"][1]["stock"],32765)
        self.assertEqual(struct.unpack_from("<h",bytes(s.state["fleets"]["moving"][0]),157)[0],1)
        before=deepcopy(s.state)
        with self.assertRaises(GameError):
            s.apply("transfer_cargo",fleet_index=0,slot=13,quantity=-1,maximum=True)
        self.assertEqual(s.state,before)

    def test_maximum_remote_transfer_honors_local_stock_and_storage(self):
        s=cargo_session();row=s.state["fleets"]["moving"][0];row[19:22]=[1,5,1]
        raw=s.state["worlds"]["1:5:1"]["raw"];raw[0]=raw[6]=1
        set_world_stocks(raw,[9900]*6)
        local=[0]*161;local[0]=5;local[19:23]=[1,5,1,7];local[159:161]=struct.pack("<H",10)
        local[157:159]=struct.pack("<h",1)
        s.state["fleets"]["local"].append(local)
        s.state["buildings"][-1][1:4]=[1,5,1]
        row[109:113]=struct.pack("<I",300)
        original_home=deepcopy((s.state["resources"],s.state["products"]))
        s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=-1,maximum=True)
        self.assertEqual(world_stocks(s.state["worlds"]["1:5:1"]["raw"])[0],10000)
        self.assertEqual(struct.unpack_from("<I",bytes(s.state["fleets"]["moving"][0]),109)[0],200)
        s.apply("transfer_cargo",fleet_index=0,slot=13,quantity=1,maximum=True)
        self.assertEqual(s.state["fleets"]["local"][-1][157],0)
        s.apply("transfer_cargo",fleet_index=0,slot=13,quantity=-1,maximum=True)
        self.assertEqual(s.state["fleets"]["local"][-1][157],1)
        self.assertEqual((s.state["resources"],s.state["products"]),original_home)

    def test_maximum_zero_capacity_or_invalid_direction_rejects_atomically(self):
        s=cargo_session()
        for args in ({"maximum":1},{"maximum":True,"quantity":2},{"maximum":True,"quantity":-2},
                     {"maximum":True,"slot":13,"quantity":-1}):
            before=deepcopy(s.state)
            with self.assertRaises(GameError):
                s.apply("transfer_cargo",**({"fleet_index":0,"quantity":1,"slot":13}|args))
            self.assertEqual(s.state,before)
        s.state["fleets"]["moving"][0][22]=2
        before=deepcopy(s.state)
        with self.assertRaises(GameError):
            s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=1,maximum=True)
        self.assertEqual(s.state,before)

    def test_ore_and_items_share_capacity_and_conserve_stock(self):
        s=cargo_session();before=deepcopy(s.state)
        s.apply("transfer_cargo",fleet_index=0,slot=13,quantity=1)
        s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=500)
        self.assertEqual(cargo_used(s.state["fleets"]["moving"][0],s.catalog["cargo_rules"]),1000)
        full=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[1],quantity=1)
        self.assertEqual(s.state,full)
        for kwargs in ({"slot":13,"quantity":-1},{"ore":ORE_KEYS[0],"quantity":-500}):
            s.apply("transfer_cargo",fleet_index=0,**kwargs)
        for key in ("resources","products","fleets"):
            self.assertEqual(s.state[key],before[key])

    def test_hulls_cannot_be_removed_while_cargo_would_be_overloaded(self):
        s=cargo_session()
        s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=501)
        before=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply("equip_fleet",fleet_index=0,category=2,hull=1,quantity=-1)
        self.assertEqual(s.state,before)
        s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=-1)
        s.apply("equip_fleet",fleet_index=0,category=2,hull=1,quantity=-1)

    def test_remote_ore_and_items_use_only_local_depot(self):
        s=cargo_session();row=s.state["fleets"]["moving"][0];row[19:22]=[1,5,1]
        raw=s.state["worlds"]["1:5:1"]["raw"];raw[0]=raw[6]=1
        set_world_stocks(raw,[200]*6)
        local=[0]*161;local[0]=5;local[19:23]=[1,5,1,7];local[159:161]=struct.pack("<H",10)
        local[157:159]=struct.pack("<h",2)
        s.state["fleets"]["local"].append(local)
        s.state["buildings"][-1][1:4]=[1,5,1]
        resources=deepcopy(s.state["resources"]);products=deepcopy(s.state["products"])
        s.apply("transfer_cargo",fleet_index=0,slot=13,quantity=1)
        s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[2],quantity=100)
        self.assertEqual(world_stocks(s.state["worlds"]["1:5:1"]["raw"])[2],100)
        self.assertEqual(s.state["fleets"]["local"][-1][157],1)
        self.assertEqual(s.state["resources"],resources);self.assertEqual(s.state["products"],products)

    def test_gates_reject_atomically(self):
        for mutation in (lambda s:s.state["fleets"]["moving"][0].__setitem__(22,2),
                         lambda s:s.state["worlds"]["1:5:0"]["raw"].__setitem__(0,0),
                         lambda s:s.state["buildings"][-1].__setitem__(6,1),
                         lambda s:s.state["products"][1].update(research_state=2)):
            s=cargo_session();mutation(s);before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply("transfer_cargo",fleet_index=0,slot=13,quantity=1)
            self.assertEqual(s.state,before)
        for kwargs in ({"ore":ORE_KEYS[0],"quantity":0},{"slot":True,"quantity":1},
                       {"slot":2,"quantity":1},{"ore":ORE_KEYS[0],"slot":13,"quantity":1},
                       {"ore":ORE_KEYS[0],"quantity":True}):
            s=cargo_session();before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply("transfer_cargo",fleet_index=0,**kwargs)
            self.assertEqual(s.state,before)

    def test_pirate_capacity_uses_trade_hulls_in_second_bank(self):
        s=cargo_session();row=s.state["fleets"]["moving"][0];row[0]=3
        s.catalog["fleet_rules"][2]["categories"].append({"id":2,"bank":2})
        row[69:71]=struct.pack("<h",3)
        self.assertEqual(cargo_capacity(row,s.catalog),1500)

    def test_overfull_depots_and_ship_never_reverse_transfer(self):
        s=cargo_session();s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=1)
        s.state["resources"][ORE_KEYS[0]]=100000000
        before=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=-1)
        self.assertEqual(s.state,before)
        s.state["fleets"]["moving"][0][109:113]=struct.pack("<I",2000)
        before=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=1)
        self.assertEqual(s.state,before)

    def test_outpost_capacity_uses_completed_buildings_when_no_local_record(self):
        s=cargo_session();identity=(1,5,1)
        s.state["fleets"]["local"]=[]
        buildings=[[25,1,5,1,1,1,1,100,0,0,0,0,0,0]]
        self.assertEqual(storage_limit(s.state["fleets"],identity,buildings),0)
        buildings[0][6]=0
        self.assertEqual(storage_limit(s.state["fleets"],identity,buildings),10000)
        row=s.state["fleets"]["moving"][0];row[19:22]=list(identity)
        raw=s.state["worlds"]["1:5:1"]["raw"];raw[0]=raw[10]=1
        set_world_stocks(raw,[100]*6);s.state["buildings"]=buildings
        s.apply("transfer_cargo",fleet_index=0,ore=ORE_KEYS[0],quantity=100)
        self.assertEqual(world_stocks(s.state["worlds"]["1:5:1"]["raw"])[0],0)

    def test_signed_item_overflow_rejected(self):
        row=[0]*161;row[157:159]=struct.pack("<h",32767)
        with self.assertRaises(GameError):transfer_item(row,13,1,1,0,0,0)
        row[157:159]=struct.pack("<h",1)
        with self.assertRaises(GameError):transfer_item(row,13,32767,-1,0,0,0)

    def test_catalog_weights_are_validated(self):
        s=cargo_session();s.catalog["fleet_rules"][1]["categories"][0]["id"]=1
        with self.assertRaises(GameError):cargo_capacity(s.state["fleets"]["moving"][0],s.catalog)
        for mutate in (lambda r:r["hull_capacity"].pop(),lambda r:r["items"][0].update(weight=-1),
                       lambda r:r["items"][0].update(slot=True),lambda r:r["items"][0].update(product=0)):
            rules=deepcopy(cargo_session().catalog["cargo_rules"]);mutate(rules)
            with self.assertRaises(GameError):validate_cargo_rules(rules)
