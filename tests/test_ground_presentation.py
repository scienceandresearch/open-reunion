"""Original-free sprite decisions, indexed conversions and drawing bounds."""
from copy import deepcopy
import struct
import unittest
import zlib
from test_ground_frame import state, rocket
from test_ground_geometry import unit, MOTION
from test_ground_controls import RULES as CONTROLS
from openreunion.core import GameError
from openreunion.dos.assets import Picture, decode_converted_png
from openreunion.dos.ground_presentation import ground_render_plan, validate_ground_presentation
from openreunion.dos.ground_pixels import sprite_pixels, GroundPixels


RULES = {"animations": [[6,4,10], [2,1,4], [7,1,4], [12,1,4], [17,1,4],
                         [1,3,9], [10,3,9], [1,1,10], [11,1,4]],
         "names": ["Trooper", "Tank", "Aircraft", "Missile", "Base"]}


def plan(battle):return ground_render_plan(battle, MOTION, RULES, CONTROLS)


class GroundPresentationTests(unittest.TestCase):
    def test_draws_are_read_only_and_base_layout_matches_attacking_side(self):
        battle = state();before = deepcopy(battle);calls = plan(battle)
        self.assertEqual(battle, before)
        self.assertEqual([(c["source"],c["x"],c["width"]) for c in calls], [([64,33],64,16), ([192,0],288,32)])
        battle["player_attacking"] = False;calls = plan(battle)
        self.assertEqual([(c["source"],c["x"],c["transparent"]) for c in calls], [([64,0],64,False), ([132,33],304,True)])

    def test_hit_overlays_preserve_living_troops_and_late_death_hides_underlay(self):
        living = unit();living[12:15] = [8, 3, 1]
        dead = unit(quantity=0);dead[12:15] = [7, 5, 1]
        battle = state([living], [dead]);calls = plan(battle)[2:]
        self.assertEqual([(c["atlas"],c["frame"],c["bank"]) for c in calls], [("units",1,1),("effects",12,1),("effects",6,1)])
        dead[13] = 6
        self.assertEqual([c["atlas"] for c in plan(battle)[2:]], ["units","effects","units","effects"])

    def test_hostile_rocket_bank_and_base_effect_offsets(self):
        row = unit(kind=4);row[12:15] = [5, 8, 1]
        battle = state([], [row]);battle["friendly_special"][12:15] = [8, 3, 1]
        calls = plan(battle)
        self.assertEqual((calls[2]["frame"],calls[2]["bank"]), (11,3))
        self.assertEqual((calls[3]["x"],calls[3]["y"]), (64,67))
        battle["player_attacking"] = False
        self.assertEqual((plan(battle)[3]["x"],plan(battle)[3]["y"]), (72,75))

    def test_selection_move_and_target_markers_and_missing_target_protection(self):
        row = unit();row[15:18] = [2,9,8]
        battle = state([row], [unit(x=10)]);battle.update(selected_group=1, selected_friendly=True)
        calls = plan(battle)
        self.assertEqual([(c["frame"],c["bank"]) for c in calls[-2:]], [(15,1),(16,2)])
        self.assertEqual((calls[-1]["x"],calls[-1]["y"]), (208,131))
        row[15:17] = [3,21]
        self.assertEqual((plan(battle)[-1]["x"],plan(battle)[-1]["y"]), (296,75))
        row[16] = 0
        self.assertEqual(plan(battle)[-1]["frame"], 15)

    def test_projectile_interpolation_truncates_negative_coordinates_toward_zero(self):
        battle = state();battle["friendly_projectiles"] = [list(struct.pack("<7hI", 100,50,93,41,2,3,8,1))]
        self.assertEqual(plan(battle)[-1], {"atlas":"projectiles","heading":8,"x":96,"y":44})
        battle["friendly_projectiles"][0][10:12] = [0,0]
        with self.assertRaises(GameError):plan(battle)

    def test_sprite_transposes_and_reverse_preserve_asymmetric_pixels(self):
        picture = Picture(3,3,bytes(range(9)),bytes(768))
        expected = {1:[0,1,2,3,4,5,6,7,8],2:[0,3,6,1,4,7,2,5,8],
                    3:[8,7,6,5,4,3,2,1,0],4:[8,5,2,7,4,1,6,3,0]}
        for direction, pixels in expected.items():
            self.assertEqual(sprite_pixels(picture,0,0,3,3,direction),bytes(pixels))
        for args in ((1,1,3,3,1),(0,0,2,3,2),(0,0,3,3,5)):
            with self.assertRaises(GameError):sprite_pixels(picture,*args)

    def test_indexed_png_roundtrip_retains_duplicate_rgb_palette_indices(self):
        picture = Picture(3,2,bytes([0,1,0,255,2,3]),bytes(768))
        self.assertEqual(decode_converted_png(picture.png()),picture)
        for data in (picture.png()[:-1],picture.png()+b"junk",picture.png()[:48]+b"X"+picture.png()[49:]):
            with self.assertRaises(GameError):decode_converted_png(data)

    def test_compressed_png_cannot_exceed_header_pixel_count(self):
        def chunk(kind,data):return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data))
        prefix = b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",1,1,8,3,0,0,0))+chunk(b"PLTE",bytes(768))
        for raw in (bytes(1000000),b"\x01\0",b"\0"):
            data = prefix+chunk(b"IDAT",zlib.compress(raw))+chunk(b"IEND",b"")
            with self.assertRaises(GameError):decode_converted_png(data)

    def test_composition_clips_to_viewport_and_transparency_uses_index_not_rgb(self):
        palette = bytearray(768);palette[9:12] = b"\x00\xff\x00"
        class Source:
            def indexed_picture(self,name):
                width,height = (64,200) if "GRWAR" in name else (320,200) if "GRF" in name else (320,32) if "GRICON2" in name else (320,48)
                pixels = bytearray([3])*(width*height)
                if "GRICON" in name:pixels = bytearray(width*height);pixels[1] = 1
                return Picture(width,height,bytes(pixels),bytes(palette))
        renderer = GroundPixels(Source(),1)
        calls = [{"atlas":"units","frame":1,"bank":1,"x":64,"y":0,"direction":1}]
        rendered = renderer.render(calls)
        self.assertEqual(rendered[64*3:66*3],b"\x00\xff\x00\x00\x00\x00")
        calls[0]["x"] = 63
        rendered = renderer.render(calls)
        self.assertEqual(rendered[63*3:65*3],b"\x00\xff\x00\x00\x00\x00")
        self.assertEqual(len(rendered),320*151*3)
        self.assertEqual(renderer.background[64*3:65*3],b"\x00\xff\x00")

    def test_presentation_rules_reject_sprite_bank_overflow(self):
        validate_ground_presentation(RULES)
        for key,value in (("animations",[[20,1,20]]*9),("names",["x"]*4)):
            candidate = deepcopy(RULES);candidate[key] = value
            with self.assertRaises(GameError):validate_ground_presentation(candidate)


if __name__=="__main__":unittest.main()
