"""Destroyed bases release terrain without losing explosions or live occupants."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest
from test_ground_frame import state,rocket,RULES
from test_ground_geometry import unit,MOTION
from test_ground_movement import RULES as MOVEMENT
from test_ground_presentation import plan
from test_ground_controls import RULES as CONTROLS
from test_strategy_session import battle_session
from openreunion.dos.ground_frame import ground_frame,ground_animation_pass
from openreunion.dos.ground_controls import nearest_ground_selection
from openreunion.dos.session import RecoveredSession


def quiet():
    b=state([unit(quantity=10,x=5,y=1)],[unit(quantity=10,x=10,y=7)])
    for side in ("friendly","hostile"):
        row=b[side+"_groups"][0];row[6:8]=struct.pack("<h",300);row[15]=1
    return b


class GroundBaseTests(unittest.TestCase):
    def test_projectile_destruction_releases_all_four_layouts_without_winning(self):
        for attacking in (False,True):
            for side in ("friendly","hostile"):
                with self.subTest(attacking=attacking,side=side):
                    b=quiet();b["player_attacking"]=attacking;b["hostile_special"][4]=14 if attacking else 15
                    b=ground_animation_pass(b);base=b[side+"_special"]
                    firing="friendly" if side=="hostile" else "hostile"
                    b[firing+"_projectiles"]=[rocket(x=base[4],y=base[5],power=180)]
                    b.update(selected_group=21,selected_friendly=side=="friendly");before=deepcopy(b)
                    result,_=ground_frame(b,MOTION,RULES,MOVEMENT)
                    self.assertEqual(b,before);self.assertEqual(result[side+"_special"][1:3],[0,0])
                    code=21 if side=="friendly" else 121
                    self.assertFalse(any(code in column for column in result["board"]))
                    self.assertEqual(result["selected_group"],0);self.assertFalse(result["done"])
                    self.assertEqual(len([c for c in plan(result) if c["atlas"]=="terrain"]),1)
                    self.assertTrue(any(c["atlas"]=="effects" for c in plan(result)))

    def test_explosion_finishes_without_restoring_the_intact_base(self):
        b=quiet();b["hostile_special"][1:3]=[0,0];b["hostile_special"][12:15]=[7,10,3]
        for frame in range(30):
            b=ground_animation_pass(b);calls=plan(b)
            self.assertEqual(len([c for c in calls if c["atlas"]=="terrain"]),1)
            self.assertFalse(any(121 in col for col in b["board"]))
        self.assertEqual(b["hostile_special"][12:15],[0,0,0])
        self.assertFalse(any(c["atlas"]=="effects" for c in calls))

    def test_released_base_cells_keep_new_troop_reservations(self):
        b=quiet();b["hostile_special"][1:3]=[0,0]
        b["board"][14][4]=1;b["board"][15][4]=121
        result=ground_animation_pass(b)
        self.assertEqual(result["board"][14][4],1);self.assertEqual(result["board"][15][4],0)

    def test_destroyed_base_cannot_be_selected_or_marked_as_a_target(self):
        b=quiet();base=b["hostile_special"];base[1:3]=[0,0]
        b.update(selected_group=21,selected_friendly=False)
        self.assertFalse(any(c.get("frame")==15 for c in plan(b)))
        self.assertEqual(nearest_ground_selection(b,MOTION,CONTROLS,296,124,"hostile"),0)
        b.update(selected_group=1,selected_friendly=True);b["friendly_groups"][0][15:17]=[3,21]
        self.assertFalse(any(c.get("frame")==16 for c in plan(b)))
        after,_=ground_frame(b,MOTION,RULES,MOVEMENT)
        self.assertEqual(after["friendly_groups"][0][15],1)

    def test_old_phantom_reservations_are_cleared_before_saved_movement(self):
        s=battle_session();s.apply("ground_start");b=s.state["ground_encounter"]["battle"]
        for side in ("friendly","hostile"):
            for row in b[side+"_groups"]:row[6:8]=struct.pack("<h",300);row[15:19]=[1,0,0,0]
        b["hostile_special"][1:3]=[0,0];b["board"]=[[0]*9 for _ in range(16)]
        for x,y in ((14,4),(14,5),(15,4),(15,5)):b["board"][x][y]=121
        row=b["friendly_groups"][0];row[4:6]=[13,4];row[8:12]=[3,1,15,0];row[15:18]=[2,14,4];b["board"][13][4]=1
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"base.json";s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            for current in (s,loaded):current.apply("ground_tick")
            self.assertEqual(s.state,loaded.state)
            result=s.state["ground_encounter"]["battle"]
            self.assertEqual(result["friendly_groups"][0][4:6],[14,4]);self.assertEqual(result["board"][14][4],1)
            self.assertFalse(any(121 in col for col in result["board"]))
            s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            for current in (s,loaded):current.apply("ground_tick",frames=5)
            self.assertEqual(s.state,loaded.state)


if __name__=="__main__":unittest.main()
