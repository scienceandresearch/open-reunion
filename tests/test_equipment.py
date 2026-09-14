from copy import deepcopy
import struct
import unittest
from test_orbital import orbital_session
from openreunion.core import GameError
from openreunion.dos.equipment import new_fleet,equipment_step,validate_fleet_rules


def equipment_session():
    session=orbital_session()
    session.state["fleets"]["moving"]=[]
    session.state["campaign"]["capabilities"].update(transport=1,transfer=1,carrier=1)
    for product in (5,6,27):session.state["products"][product-1].update(stock=8,research_state=5)
    return session


class EquipmentTests(unittest.TestCase):
    def test_rename_preserves_moving_and_local_fleet_state_and_clears_old_name(self):
        session=equipment_session()
        session.apply("create_fleet",fleet_type=2,name="Long original")
        session.apply("equip_fleet",fleet_index=0,category=1,hull=1,quantity=3)
        session.state["fleets"]["moving"][0][22]=5
        local=session.state["fleets"]["moving"][0].copy()
        local[0]=5;local[22]=7
        session.state["fleets"]["local"]=[local]
        for bank in ("moving","local"):
            before=deepcopy(session.state)
            session.apply("rename_fleet",bank=bank,fleet_index=0,name="Ore convoy")
            row=session.state["fleets"][bank][0]
            self.assertEqual(row[1:19],[10]+list(b"Ore convoy")+[0]*7)
            before["fleets"][bank][0][1:19]=row[1:19]
            before["log"]=session.state["log"]
            self.assertEqual(session.state,before)

    def test_rename_invalid_requests_are_atomic(self):
        session=equipment_session()
        session.apply("create_fleet",fleet_type=2)
        for args in ({"name":""},{"name":"x"*18},{"name":"bad\nname"},
                     {"name":None},{"name":"caf\u00e9"},{"name":"OK","bank":"missing"},
                     {"name":"OK","fleet_index":True},{"name":"OK","fleet_index":1}):
            before=deepcopy(session.state)
            with self.assertRaises(GameError):
                session.apply("rename_fleet",**({"fleet_index":0}|args))
            self.assertEqual(session.state,before)

    def test_creation_initializes_clean_landed_fleet_and_limits_groups(self):
        session=equipment_session()
        session.apply("create_fleet",fleet_type=2,name="Apollo supplies")
        row=session.state["fleets"]["moving"][0]
        self.assertEqual(row[19:23],[1,5,0,1])
        self.assertEqual(row[29:],[0]*132)
        for kind,name in ((1,"Locked"),(True,"Bad"),(2,""),(2,"x"*18)):
            before=deepcopy(session.state)
            with self.assertRaises(GameError):session.apply("create_fleet",fleet_type=kind,name=name)
            self.assertEqual(session.state,before)
        session.state["fleets"]["moving"]=[row.copy() for _ in range(32)]
        with self.assertRaises(GameError):session.apply("create_fleet",fleet_type=2)

    def test_loading_and_unloading_conserve_hulls_and_equipment(self):
        session=equipment_session()
        session.apply("create_fleet",fleet_type=2)
        session.apply("equip_fleet",fleet_index=0,category=1,hull=1,quantity=3)
        session.apply("equip_fleet",fleet_index=0,category=1,hull=1,component=1,quantity=3)
        session.apply("equip_fleet",fleet_index=0,category=1,hull=1,quantity=-2)
        self.assertEqual(struct.unpack_from("<5h",bytes(session.state["fleets"]["moving"][0]),29),(1,1,0,0,0))
        self.assertEqual(session.state["products"][4]["stock"],7)
        self.assertEqual(session.state["products"][5]["stock"],7)

    def test_bulk_shortage_or_capacity_failure_rolls_back_entire_transfer(self):
        session=equipment_session()
        session.apply("create_fleet",fleet_type=2)
        for kwargs in ({"quantity":9},{"component":1},{"quantity":-1},{"quantity":0},{"hull":True}):
            before=deepcopy(session.state)
            arguments={"fleet_index":0,"category":1,"hull":1}|kwargs
            with self.assertRaises(GameError):session.apply("equip_fleet",**arguments)
            self.assertEqual(session.state,before)

    def test_transit_and_orbit_cannot_load_from_colony(self):
        session=equipment_session()
        session.apply("create_fleet",fleet_type=2)
        for status in (2,4,5,6):
            session.state["fleets"]["moving"][0][22]=status
            with self.assertRaises(GameError):session.apply("equip_fleet",fleet_index=0,category=1,hull=1)

    def test_carrier_shared_capacity_is_restored_when_hull_is_removed(self):
        session=equipment_session()
        session.apply("create_fleet",fleet_type=4)
        for component,quantity in ((0,2),(1,1),(2,1),(0,-1)):
            session.apply("equip_fleet",fleet_index=0,category=1,hull=1,component=component,quantity=quantity)
        self.assertEqual(struct.unpack_from("<5h",bytes(session.state["fleets"]["moving"][0]),29),(1,1,0,0,0))
        self.assertEqual(session.state["products"][26]["stock"],8)

    def test_local_depot_aliases_accumulate_without_touching_home_stock(self):
        session=equipment_session()
        cat=session.catalog["fleet_rules"][4]["categories"][0]
        cat["components"][1]["local_slot"]=2
        row=[0]*161
        row[0]=5;row[19:23]=[1,5,1,7]
        row[29:39]=struct.pack("<5h",1,1,1,0,0)
        row[133:137]=struct.pack("<hh",2,3)
        session.state["fleets"]["local"]=[row]
        raw=session.state["worlds"]["1:5:1"]["raw"]
        raw[0]=raw[6]=1
        products=deepcopy(session.state["products"])
        session.apply("equip_fleet",fleet_index=0,bank="local",category=1,hull=1,quantity=-1)
        actual=session.state["fleets"]["local"][0]
        self.assertEqual(struct.unpack_from("<hh",bytes(actual),133),(3,5))
        self.assertEqual(session.state["products"],products)

    def test_created_and_loaded_station_can_deploy_without_prepared_fleet_records(self):
        session=equipment_session()
        cat=session.catalog["fleet_rules"][1]["categories"][0]
        mine=cat["components"][0]
        cat["components"]=[{"product":p,"local_slot":i,"name":"Weapon"} for i,p in enumerate((11,13,22),9)]+[mine]
        cat["hulls"][0]["limits"]=[0,0,0,1]
        session.apply("create_fleet",fleet_type=2)
        session.apply("equip_fleet",fleet_index=0,category=1,hull=1)
        session.apply("equip_fleet",fleet_index=0,category=1,hull=1,component=4)
        session.apply("deploy_station",world_id="1:5:1")
        self.assertEqual(session.state["worlds"]["1:5:1"]["raw"][10],1)
        self.assertEqual(session.state["fleets"]["moving"][0][37],0)

    def test_catalog_rejects_overlapping_banks_and_invalid_descriptor_ids(self):
        for change in (lambda rules:rules[0]["categories"].append(deepcopy(rules[0]["categories"][0])),
                       lambda rules:rules[0]["categories"][0]["hulls"][0].update(product=36)):
            rules=deepcopy(equipment_session().catalog["fleet_rules"])
            change(rules)
            with self.assertRaises(GameError):validate_fleet_rules(rules)


if __name__=="__main__":unittest.main()
