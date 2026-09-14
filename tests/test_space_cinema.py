"""Original-free script, animation, view and shared-seed integration regressions."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from test_space_session import prepared
from test_space_presentation import pixels
from openreunion.core import GameError
from openreunion.dos.animation import decode_frame,read_animation
from openreunion.dos.assets import Picture
from openreunion.dos.space_cinema import (validate_cinema_rules,validate_cinema,cinema_tick,
    start_cinema,advance_cinema_view,validate_cinema_view)
from openreunion.dos.space_roster import build_space_battle
from openreunion.dos.space_combat import space_tick
from openreunion.dos.campaign import random_bounded
from openreunion.dos.session import RecoveredSession


def rules():
    result={"pool":sum(1<<i for i in range(2,26)),"repeats":[0]*25,
        "assets":[[1,2,2,160,49] for _ in range(25)],
        "scripts":[[[i,1,0,0],[i,1,4,2],[0,0,0,255]]+[[0]*4 for _ in range(137)] for i in range(1,26)]}
    result["repeats"][2]=2;result["repeats"][14]=3;validate_cinema_rules(result);return result


def animation_frame(payload,width=4,height=1):return b"SpidyAnim"+struct.pack("<HH",width,height)+payload


class SpaceCinemaTests(unittest.TestCase):
    def test_initial_selection_removes_chosen_sequence_without_replacing_pool(self):
        table=rules();state,seed=start_cinema(0,table)
        self.assertEqual(state["sequence"],1);self.assertEqual(seed,1)
        self.assertEqual(state["remaining"],table["pool"])
        self.assertEqual((state["row"],state["wait"]),(1,0))

    def test_row_increment_sound_and_wait_match_original_order(self):
        table=rules();state,seed=start_cinema(0,table);before=deepcopy(state)
        after,result_seed,events=cinema_tick(state,seed,table)
        self.assertEqual(state,before);self.assertEqual(seed,result_seed)
        self.assertEqual(events,[{"kind":"cinema_frame","asset":1,"frame":1},{"kind":"sound","id":4}])
        self.assertEqual(after["row"],2);self.assertEqual(after["wait"],2)
        for remaining in (1,0):
            after,result_seed,events=cinema_tick(after,result_seed,table)
            self.assertEqual(after["wait"],remaining);self.assertFalse(events)

    def test_repeats_restart_first_row_without_random_draw_and_empty_pool_resets(self):
        table=rules();state,seed=start_cinema(0,table)
        state.update(sequence=3,row=2,wait=0,repeats=2,remaining=0)
        after,new_seed,events=cinema_tick(state,seed,table)
        self.assertEqual(new_seed,seed);self.assertEqual(after["repeats"],1)
        self.assertEqual(after["row"],1);self.assertEqual(after["remaining"],table["pool"])
        self.assertEqual(events,[{"kind":"cinema_frame","asset":3,"frame":1}])

    def test_rejection_sampling_uses_initial_25_then_24_and_transition_delay_draw(self):
        table=rules();state,seed=start_cinema(0,table)
        state.update(sequence=1,row=2,wait=0,repeats=0,remaining=1<<25)
        expected,choice=random_bounded(seed,25);choice+=1;draws=1
        while choice!=25:expected,choice=random_bounded(expected,24);choice+=2;draws+=1
        expected,delay=random_bounded(expected,10)
        after,observed,events=cinema_tick(state,seed,table)
        self.assertGreater(draws,1);self.assertEqual(observed,expected)
        self.assertEqual((after["sequence"],after["row"],after["wait"]),(25,1,10+delay))
        self.assertEqual(after["transition"],[160,319,49,199]);self.assertEqual(after["remaining"],0)
        self.assertEqual(events,[{"kind":"cinema_sequence","id":25}])

    def test_wipe_advances_while_waiting_and_view_remains_bounded(self):
        table=rules();state,seed=start_cinema(0,table);state.update(wait=19,transition=[160,319,49,199])
        view={"picture":[1,1],"clears":[],"black":False}
        for _ in range(8):
            state,seed,events=cinema_tick(state,seed,table);view=advance_cinema_view(view,events)
            validate_cinema_view(view,table)
        self.assertEqual(state["transition"][0],2000);self.assertEqual(len(view["clears"]),29)
        view=advance_cinema_view(view,[{"kind":"cinema_frame","asset":2,"frame":1}])
        self.assertTrue(view["black"]);self.assertEqual(view["clears"],[])

    def test_animation_literal_short_long_run_and_skip_tokens(self):
        payload=b"\x01\x02\xc2\x07\x82\xc0\x03\x00\x09\x80\x02\x00"
        raw=animation_frame(payload,11,1)
        self.assertEqual(decode_frame(raw,bytes([5])*11),(11,1,bytes([1,2,7,7,5,5,9,9,9,5,5])))
        for payload in (b"\xc0\x00\x00\x01",b"\x80\x00\x00",b"\xc5\x01",b"\x80\x05\x00",b"\xc4",b"\x01"):
            with self.assertRaises(GameError):decode_frame(animation_frame(payload),bytes(4))
        with self.assertRaises(GameError):decode_frame(animation_frame(b"\x84"))
        with self.assertRaises(GameError):decode_frame(animation_frame(b"\xc4\x01\x00"),bytes(4))

    def test_animation_deltas_overlay_base_and_empty_entries_reuse_previous(self):
        chunks=[b"\x01\x02\x03\x04",b"\x09\x83",b"\x81\x08\x82"]
        container=b"".join(struct.pack("<H",len(payload))+animation_frame(payload) for payload in chunks)+b"\0\0"
        frames=read_animation(container,frames=4,width=4,height=1)
        self.assertEqual(frames,[bytes([1,2,3,4]),bytes([9,2,3,4]),bytes([1,8,3,4]),bytes([1,8,3,4])])
        for bad in (container[:-1],container+b"\0",b"\0\0"):
            with self.assertRaises(GameError):read_animation(bad,frames=4,width=4,height=1)

    def test_cinematic_composition_and_clears_protect_radar(self):
        p=pixels();p.cinema_cache={};table=rules()
        p.content=SimpleNamespace(catalog={"space_cinema":table},space_animation=lambda *_:Picture(2,2,bytes([1])*4,bytes([0])*3+bytes([255])*765))
        view={"picture":[1,1],"black":True,"clears":[[161,49,1,2]]}
        result=p.render([],cinema=view)
        self.assertEqual(result[160*3:162*3],bytes([255])*3+bytes(3))
        self.assertEqual(result[:160*3],bytes([77])*160*3)
        self.assertEqual(result[(320+160)*3:(320+162)*3],bytes([255])*3+bytes(3))

    def test_session_initializes_frame_before_cinema_and_persists_interleaved_rng(self):
        session=prepared();session.state["space_encounter"]=None;session.catalog["space_cinema"]=rules()
        state=session.state;table=session.catalog["battle_rules"]["space"]
        battle=build_space_battle(state["fleets"],state["campaign"]["civilizations"],state["worlds"],[1,5,1],state["levels"]["fighter"],state["campaign"]["rng"],table)
        first=space_tick(battle,table);controller,seed=start_cinema(first["rng"],session.catalog["space_cinema"])
        session.begin_space_battle((1,5,1),player_attacking=True)
        first["rng"]=seed
        self.assertEqual(first,session.state["space_encounter"]["battle"])
        self.assertEqual(controller,session.state["space_encounter"]["cinema"]["controller"])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"cinema.json";session.save(path);loaded=RecoveredSession.load(session.catalog,path)
            for _ in range(4):
                if session.state["space_encounter"]["phase"]!="fighting":break
                self.assertEqual(session.apply("space_tick",render=True),loaded.apply("space_tick",render=True))
                self.assertEqual(session.state,loaded.state)

    def test_old_active_battles_keep_their_previous_rng_sequence(self):
        session=prepared();session.catalog["space_cinema"]=rules();state=deepcopy(session.state)
        state["schema"]="recovered-strategy-v10";del state["space_encounter"]["cinema"];del state['active_scene']
        del state["active_dialog"];del state["campaign"]["system_observatories"];del state["campaign"]["bar"]
        del state["battle_requests"]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"v10.json";path.write_text(json.dumps(state),encoding="utf-8")
            loaded=RecoveredSession.load(session.catalog,path)
            self.assertIsNone(loaded.state["space_encounter"]["cinema"])
            self.assertEqual(loaded.apply("space_tick"),session.apply("space_tick"));self.assertEqual(loaded.state,session.state)

    def test_invalid_cursor_pool_and_saved_view_fail_atomically(self):
        table=rules();state,_=start_cinema(0,table)
        for change in ({"row":3},{"remaining":2},{"wait":-1},{"sequence":26},{"repeats":1}):
            with self.assertRaises(GameError):validate_cinema(dict(state,**change),table)
        for view in ({"picture":[26,1],"clears":[],"black":False},
                     {"picture":None,"clears":[[160,49,161,151]],"black":False}):
            with self.assertRaises(GameError):validate_cinema_view(view,table)


if __name__=="__main__":unittest.main()
