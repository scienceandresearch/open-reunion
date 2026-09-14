"""Synthetic regression fixtures: no original executables or assets required."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.core import GameError
from openreunion.legacy import LegacySave, RESOURCE_OFFSETS, SAVE_SIZE
from openreunion.dos.assets import decode_picture
from openreunion.dos.catalog import ORE_KEYS, SUBJECTS, SUPPORTED_HASHES, load_catalog, read_products
from openreunion.dos.content import ContentSource
from openreunion.dos.rules import calendar_tick, production_tick, research_tick
from openreunion.dos.session import PRODUCT_FIELDS, ROLES, SCHEMA, RecoveredSession
from openreunion.dos.text import decode_line, decode_text
from openreunion.dos.worlds import COUNTS, DETAIL_BASES, NAME_BASES
from openreunion.dos.colony import MESSAGE_OFFSETS


def fixture():
    products = []
    for i in range(35):
        products.append({"id":i+1,"name":f"Synthetic {i+1}","price":100,"ore_costs":dict.fromkeys(ORE_KEYS,2),
                         "requirements":dict.fromkeys(SUBJECTS,1),"research_duration":200,
                         "base_work":15,"manufacturable":1,"special_ship":0})
    catalog = {"sha256":"a"*64,"products":products,"commanders":[],"buildings":[]}
    catalog["training_rules"]={"level_caps":[30,70,90]*4,"skill_caps":[[4]*4+[7]*4+[9]*4 for _ in range(6)],
        "course_gains":[[2,1,0,0],[0,2,1,0],[1,0,2,0],[0,0,0,2]],"level_gain":105,"completion_text":"Advisor returned"}
    catalog["fleet_rules"]=[{"id":kind,"name":"Fleet","default_name":"Test fleet","categories":[
        {"id":1,"bank":1,"hulls":[{"product":6,"local_slot":1,"name":"Hull","limits":[1,1]}],
         "components":[{"product":5,"local_slot":2,"name":"Mine"},{"product":27,"local_slot":3,"name":"Solar"}]}]} for kind in range(1,6)]
    for role in ROLES:
        for rank in range(1,4):
            catalog["commanders"].append({"role":role,"rank":rank,"name":f"Test {role} {rank}",
                                          "hire_price":rank*100,"level":rank*10,"skills":dict.fromkeys(SUBJECTS,rank) if role=="developer" else {}})
    state = {"schema":SCHEMA,"executable_sha256":catalog["sha256"],"source_save_sha256":"b"*64,
             "date":[2927,8,14,8],"resources":dict.fromkeys(RESOURCE_OFFSETS,10000),
             "products":[dict(zip(PRODUCT_FIELDS,(5,0,0,0,0))) for _ in products],
             "levels":dict.fromkeys(ROLES,0),"ranks":dict.fromkeys(ROLES,0),"skills":dict.fromkeys(SUBJECTS,0),
             "workforce":10,"research_paused":False,"assisted":False,"log":[],"worlds":{},"buildings":[],"deployments":[],
             "known_systems":[1,0,255,255,255,255,255,255],"events":[],"fleets":{"moving":[],"local":[]},
             "campaign":{"rng":1994,"idea_timers":[-1]*35,"research_block_remaining":0,"training_remaining":0,
                         "commander_levels":[10,20,30]*4,"developer_skill_choices":[1]*4+[2]*4+[3]*4,
                         "training_role":0,"carrier_failure_remaining":0,"carrier_failure_reported":False,
                         "training":{"course":0,"phase":1,"quote":None},
                         "hyperspace_allowed":False,"capabilities":dict.fromkeys(("transport","hunter","transfer","pirate","carrier"),0),
                         "civilizations":[[0]*228 for _ in range(11)]}}
    from openreunion.dos.strategy import FLAGS,TIMERS
    state["campaign"].update(flags={key:0 for key in FLAGS},timers={key:0 for key in TIMERS})
    state["campaign"]["navigation"]={"planet_visibility":[1]*64,"encounter":[0,0,0],"ending":1}
    state.update(ground_encounter=None,space_encounter=None,campaign_phase="starmap",presentation_requests=[],battle_requests=[],active_dialog=None,active_scene=None)
    catalog['story_cinema']=[dict(frames=3,width=320,height=200,x=0,y=0,rate=5,repeats=2) for _ in range(17)]
    state["campaign"]["system_observatories"]=[0]*8
    state["campaign"]["bar"]=None
    return catalog,state


class RecoveredRulesTests(unittest.TestCase):
    def test_production_discards_excess_work_and_finishes_one_unit(self):
        result = production_tick(0,3,7,3,10)
        self.assertEqual((result.stock,result.queued,result.work_remaining),(1,2,7))
        self.assertEqual(production_tick(0,3,7,3,10,buying=True).stock,0)

    def test_raw_reference_retains_signed_overflow(self):
        self.assertEqual(production_tick(32767,1,70,1,10).stock,-32768)

    def test_research_threshold_overshoot_stalls_and_skills_resume(self):
        first = research_tick(2,10000,200,[0,1,1,0],[0,0,0,0],30)
        self.assertEqual((first.threshold,first.decrement,first.remaining),(6667,1500,8500))
        stalled = research_tick(2,5500,200,[0,1,1,0],[0,0,0,0],30)
        self.assertEqual(stalled.remaining,5500)
        self.assertEqual(research_tick(2,5500,200,[0,1,1,0],[0,1,1,0],30).remaining,4000)
        self.assertEqual(research_tick(2,500,200,[0,1,1,0],[0,1,1,0],30).state,5)
        self.assertEqual(research_tick(2,10000,200,[0]*4,[0]*4,30,blocked=True).remaining,10000)

    def test_thirty_day_calendar(self):
        self.assertEqual(calendar_tick([2927,2,28,23]),[2927,2,29,0])
        self.assertEqual(calendar_tick([2927,2,30,23]),[2927,3,1,0])
        self.assertEqual(calendar_tick([2927,12,30,23]),[2928,1,1,0])


class RecoveredFormatTests(unittest.TestCase):
    def test_actual_ore_order_and_distinct_edits(self):
        data = bytearray(SAVE_SIZE)
        data[:5] = b"\x04Test"
        for i in range(7):
            struct.pack_into("<I",data,0x388C+4*i,100+i)
        saved = LegacySave(bytes(data))
        self.assertEqual(saved.resources(),dict(zip(("credits","detoxin","energon","kremir","lepitium","raenium","texon"),range(100,107))))
        for key,value in saved.resources().items():
            changed = saved.with_resources({key:999})
            expected = dict(saved.resources(),**{key:999})
            self.assertEqual(LegacySave(changed).resources(),expected)

    def test_product_layout_has_35_slots_and_independent_signed_work(self):
        data = bytearray(35*53)
        for i in range(35):
            name = ("Nuclear gen" if i==0 else "Miner droid" if i==1 else "Energy shield" if i==34 else "Test").encode()
            at = i*53
            data[at:at+1+len(name)] = bytes([len(name)])+name
            struct.pack_into("<HhhIhhhh",data,at+17,3,200,10000,3150,1,2,70,25)
        rows = read_products(data,0)
        self.assertEqual(len(rows),35)
        self.assertEqual((rows[1].price,rows[1].research_duration,rows[1].base_work,rows[1].work_remaining),(3150,200,70,25))
        with self.assertRaises(GameError):
            read_products(data[:-1],0)

    def test_picture_rle_palette_and_malformed_bounds(self):
        palette = bytes(range(256))*3
        header = b"SpidyGfx"+struct.pack("<HH",3,2)
        data = header+b"\x01\xc3\x02\xc1\xc1\x03"+b"\x0c"+palette
        picture = decode_picture(data)
        self.assertEqual(picture.pixels,bytes([1,2,2,2,193,3]))
        self.assertTrue(picture.png().startswith(b"\x89PNG"))
        self.assertEqual(len(picture.rgb()),18)
        for payload in (b"\xc0\x02",b"\xc7\x02",b"\xc1",b"\x01"):
            with self.assertRaises(GameError):
                decode_picture(header+payload+b"\x0c"+palette)

    def test_text_records_are_independent_and_layout_is_preserved(self):
        # Independent inverse fixture, including maximum Pascal length.
        encode = lambda line: bytes(32+((byte+79*i)%224) for i,byte in enumerate(line,1))
        lines = [b"A|B",b"",b"01 -main",b"A"*255]
        cipher = b"\r\n".join(encode(line) for line in lines)+b"\r\n"
        self.assertEqual(decode_text(cipher),[line.decode() for line in lines]+[""])
        self.assertEqual(len(decode_line(bytes(range(255)))),255)
        with self.assertRaises(GameError):
            decode_line(b"A"*256)
        with self.assertRaises(GameError):
            decode_text(b"abc\ndef")

    def test_unknown_picture_width_mismatch_is_not_repaired(self):
        # Same dimensions and excess as INFO26, but not the demonstrated file.
        data = b"SpidyGfx"+struct.pack("<HH",191,127)+bytes([1])*(192*127)+b"\x0c"+bytes(768)
        with self.assertRaises(GameError):
            decode_picture(data)

    def test_valid_odd_picture_width_is_preserved(self):
        data = b"SpidyGfx"+struct.pack("<HH",191,127)+bytes([1])*(191*127)+b"\x0c"+bytes(768)
        picture = decode_picture(data)
        self.assertEqual((picture.width,picture.height),(191,127))
        self.assertEqual(picture.pixels,bytes([1])*(191*127))


class RecoveredSessionTests(unittest.TestCase):
    def session(self):
        return RecoveredSession(*fixture())

    def test_parallel_orders_and_refunds_preserve_progress(self):
        session = self.session()
        session.apply("order",product_id=1,quantity=2)
        session.apply("order",product_id=2,quantity=2)
        session.apply("advance",hours=1)
        self.assertEqual([p["work_remaining"] for p in session.state["products"][:2]],[5,5])
        session.apply("order",product_id=1,quantity=1)
        self.assertEqual(session.state["resources"]["credits"],9700)
        self.assertEqual(session.state["products"][0]["work_remaining"],5)
        session.apply("advance",hours=1)
        self.assertEqual([p["stock"] for p in session.state["products"][:2]],[1,1])
        self.assertEqual(session.state["products"][1]["work_remaining"],15)

    def test_zero_order_cancellation_retains_partial_work(self):
        session = self.session()
        session.apply("order",product_id=1,quantity=2)
        session.apply("advance",hours=1)
        session.apply("order",product_id=1,quantity=0)
        self.assertEqual(session.state["resources"]["credits"],10000)
        session.apply("advance",hours=5)
        self.assertEqual(session.state["products"][0]["stock"],0)
        session.apply("order",product_id=1,quantity=1)
        self.assertEqual(session.state["products"][0]["work_remaining"],5)

    def test_insufficient_ore_rolls_back_credits_and_everything_else(self):
        session = self.session()
        session.state["resources"]["texon"] = 0
        before = deepcopy(session.state)
        with self.assertRaises(GameError):
            session.apply("order",product_id=1,quantity=1)
        self.assertEqual(session.state,before)

    def test_admin_is_allowlisted_logged_and_overflow_safe(self):
        session = self.session()
        with self.assertRaises(GameError):
            session.apply("admin",command="give credits 50")
        session.admin_enabled = True
        session.apply("admin",command="give texon 50")
        self.assertEqual(session.state["resources"]["texon"],10050)
        self.assertTrue(session.state["assisted"])
        for command in ("give credits 4294967295","stock 1 32768","__import__('os')","stock 0 5","give texon -1"):
            before = deepcopy(session.state)
            with self.assertRaises((GameError,ValueError)):
                session.apply("admin",command=command)
            self.assertEqual(session.state,before)
        session.apply("admin",command="stock 1 32767")
        with self.assertRaises(GameError):
            session.apply("order",product_id=1,quantity=1)

    def test_research_switch_and_commander_upgrade(self):
        session = self.session()
        session.state["products"][0].update(research_state=1,research_remaining=10000)
        session.state["products"][1].update(research_state=3,research_remaining=10000)
        session.apply("research",product_id=1)
        session.apply("advance",hours=1)
        self.assertEqual(session.state["products"][0]["research_remaining"],10000)
        session.apply("hire",role="developer",rank=1)
        session.apply("research",product_id=2)
        session.apply("advance",hours=1)
        self.assertEqual(session.state["products"][0]["research_state"],1)
        self.assertEqual(session.state["products"][1]["research_remaining"],9500)
        with self.assertRaises(GameError):
            session.apply("hire",role="developer",rank=1)

    def test_save_continuation_validation_and_admin_reset(self):
        session = self.session()
        session.apply("order",product_id=1,quantity=3)
        session.apply("advance",hours=1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"session.json"
            session.admin_enabled = True
            session.save(path)
            loaded = RecoveredSession.load(session.catalog,path)
            self.assertFalse(loaded.admin_enabled)
            loaded.apply("advance",hours=8)
            session.apply("advance",hours=8)
            self.assertEqual(loaded.state,session.state)
            for contents in ('{"schema":1,"schema":2}',json.dumps({**session.state,"date":[2927,2,31,1]}),json.dumps({**session.state,"workforce":0}),"[]"):
                path.write_text(contents)
                with self.assertRaises(GameError):
                    RecoveredSession.load(session.catalog,path)
            with self.assertRaises(GameError):
                session.save(Path(directory)/"SPIDYSAV.1")


class BundleTests(unittest.TestCase):
    def catalog(self):
        catalog,state = fixture()
        catalog.update(sha256=sorted(SUPPORTED_HASHES)[0],ore_names={key:key.capitalize() for key in ORE_KEYS},
                       buildings=[{"id":i,"name":"Synthetic","price":100,"width":1,"height":1,"tile_ids":[0]*16,
                                   "unclassified_fields_hex":"00"*24,"unclassified_43_44":[0,0]} for i in range(1,26)])
        catalog["surface_rules"]={"groups":list(range(1,12)),"editable":[1]*11,"blocked_hex":["00"*256]*11}
        catalog["settlement_options"]=[2,3,22,4,17,7]
        catalog["cargo_rules"]={"hull_capacity":[500,2000,1000,8000],"items":[{"slot":i,"product":i,"weight":i*10} for i in range(1,14)]}
        catalog["colony_messages"]={str(offset):"Synthetic message" for offset in MESSAGE_OFFSETS}
        catalog["system_names"]=["Test"]*8
        catalog["alien_names"]=["Test"]*11
        catalog["worlds"] = [{"id":f"{system}:{(index-1)//9+1}:{(index-1)%9}","system":system,
            "planet":(index-1)//9+1,"moon":(index-1)%9,"index":index,"name":"Test",
            "address":DETAIL_BASES[system-1]+65*(index-1),"name_address":NAME_BASES[system-1]+13*(index-1),
            "orbital_display_bytes":[0,0,0]} for system,count in enumerate(COUNTS,1) for index in range(1,count+1)]
        for definition,row in zip(catalog["products"],state["products"]):
            definition.update(row)
        return catalog

    def test_catalog_validation_rejects_invalid_runtime_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"catalog.json"
            catalog = self.catalog()
            path.write_text(json.dumps(catalog))
            self.assertEqual(load_catalog(path),catalog)
            mutations = [lambda c:c["products"][0].update(price=-1),lambda c:c["products"][0].update(id=True),
                         lambda c:c["products"][0]["ore_costs"].pop("texon"),lambda c:c["commanders"][0].update(level=100),
                         lambda c:c.update(sha256="f"*64),lambda c:c["worlds"][0].update(address=0),
                         lambda c:c["worlds"].pop(),lambda c:c["worlds"][0].update(planet=True),
                         lambda c:c["buildings"][0].update(unclassified_fields_hex="00"),
                         lambda c:c["buildings"][0].update(unclassified_43_44=[True,0])]
            for mutation in mutations:
                bad = deepcopy(catalog)
                mutation(bad)
                path.write_text(json.dumps(bad))
                with self.assertRaises(GameError):
                    load_catalog(path)

    def test_bundle_reads_without_an_executable_and_bounds_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"catalog.json").write_text(json.dumps(self.catalog()))
            text = {"decoded":[{"path":"TEXT/TEST.TXT","lines":["01 hello|there",""]}]}
            (root/"text.json").write_text(json.dumps(text))
            source = ContentSource(root)
            self.assertTrue(source.bundled)
            self.assertEqual(source.text("TEST.TXT"),["01 hello|there",""])
            with self.assertRaises(GameError):
                source.picture("../../outside.PIC")
            text["decoded"] *= 2
            (root/"text.json").write_text(json.dumps(text))
            with self.assertRaises(GameError):
                ContentSource(root)
