"""Read-only display, sprite geometry, migration and persisted frame regressions."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from test_space_session import prepared
from test_space_combat import battle_fixture, rules_fixture, hit_seed
from openreunion.core import GameError
from openreunion.dos.assets import Picture
from openreunion.dos.space_combat import space_tick
from openreunion.dos.space_presentation import (read_space_presentation, validate_space_presentation,
    space_snapshot_plan, validate_radar_calls)
from openreunion.dos.space_pixels import SpacePixels
from openreunion.dos.session import RecoveredSession


def pixels():
    result = SpacePixels.__new__(SpacePixels);result.cache = {}
    result.atlases = {"sprites": Picture(80, 48, bytes((i%254)+1 for i in range(80*48)),
        b"".join(bytes([i])*3 for i in range(256)))}
    result.rgb = {"radar": bytes(160*151*3), "panel": bytes([77])*(320*151*3),
                  "victory": b"won", "defeat": b"lost"}
    result.spans = [[160*20+40, 320*11+40, 10]]
    return result


class SpacePresentationTests(unittest.TestCase):
    def test_draws_precede_movement_and_explosions_follow_deaths(self):
        battle = battle_fixture();battle["rng"] = hit_seed();before = deepcopy(battle)
        calls = [];after = space_tick(battle, rules_fixture(), render_calls=calls)
        self.assertEqual(battle, before)
        self.assertEqual(after, space_tick(battle, rules_fixture()))
        self.assertEqual([c["kind"] for c in calls], ["ship", "explosion"])
        self.assertEqual(calls[0], {"kind":"ship", "side":"friendly", "hull":3, "x":80, "y":70})
        self.assertEqual(calls[1]["step"], 1)
        held = [];space_tick(after, rules_fixture(), render_calls=held)
        self.assertEqual(held, [])

    def test_persisted_view_is_held_on_skipped_frames_and_survives_load(self):
        session = prepared();plain = RecoveredSession(session.catalog, session.state)
        events = session.apply("space_tick", render=True);plain.apply("space_tick")
        self.assertEqual(session.state, plain.state)
        calls = deepcopy(session.state["space_encounter"]["radar"])
        self.assertEqual(events[0], {"kind":"space_frame", "calls":calls})
        session.apply("space_tick", frames=3, render=True)
        self.assertEqual(session.state["space_encounter"]["radar"], calls)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"radar.json";session.save(path)
            loaded = RecoveredSession.load(session.catalog, path)
            self.assertEqual(session.state, loaded.state)
            self.assertEqual(session.apply("space_tick", render=True), loaded.apply("space_tick", render=True))
            self.assertEqual(session.state, loaded.state)

    def test_hull_shapes_use_original_opaque_pixels_and_enemy_bank(self):
        p = pixels()
        for hull, count in ((1, 1), (2, 2), (3, 8), (4, 14)):
            friendly = p.sprite({"kind":"ship", "side":"friendly", "hull":hull})
            enemy = p.sprite({"kind":"ship", "side":"hostile", "hull":hull})
            self.assertEqual(len(friendly), count);self.assertEqual(len(enemy), count)
            self.assertEqual([(x,y) for x,y,_ in friendly], [(x,y) for x,y,_ in enemy])
            self.assertNotEqual(friendly, enemy)
        self.assertEqual([(x,y) for x,y,_ in p.sprite({"kind":"ship","side":"friendly","hull":3})],
                         [(1,0),(2,0),(0,1),(1,1),(2,1),(3,1),(1,2),(2,2)])

    def test_explosion_transparency_uses_index_not_duplicate_rgb(self):
        p = pixels();values = bytearray(80*48);values[17*80+1] = 5
        p.atlases["sprites"] = Picture(80,48,bytes(values),bytes(768))
        self.assertEqual(p.sprite({"kind":"explosion","hull":1,"step":1}), [(1,0,b"\x00\x00\x00")])
        self.assertEqual(len(p.sprite({"kind":"ship","side":"friendly","hull":4})),14)

    def test_clipping_preserves_adjacent_rows_and_radar_spans_preserve_panel(self):
        p = pixels();calls = [{"kind":"ship","side":"friendly","hull":4,"x":159,"y":20}]
        radar = p.radar(calls)
        self.assertEqual(radar[(21*160)*3:(21*160+8)*3], bytes(24))
        self.assertNotEqual(radar[(21*160+159)*3:(21*160+160)*3], bytes(3))
        frame = p.render([]);start = (320*11+40)*3
        self.assertEqual(frame[start:start+30], bytes(30))
        self.assertEqual(frame[:start], bytes([77])*start)
        self.assertEqual(frame[start+30:], bytes([77])*(len(frame)-start-30))
        self.assertEqual(p.render([],result=True),b"won");self.assertEqual(p.render([],result=False),b"lost")

    def test_geometry_parser_accepts_only_known_instructions_and_bounded_copies(self):
        program = b"\x81\xc6\x00\x00\x81\xc7\x00\x00\xb9\x02\x00\xf3\xa5\xa4"
        program += b"\x83\xc6\x00"*((0x31E50-0x31797-len(program))//3)
        self.assertEqual(len(program),0x31E50-0x31797)
        data = bytearray(0x31E53);data[0x31797:0x31E50] = program
        self.assertEqual(read_space_presentation(data),{"radar_spans":[[0,0,5]]})
        data[0x31797] = 0x90
        with self.assertRaises(GameError):read_space_presentation(data)
        with self.assertRaises(GameError):read_space_presentation(b"")
        for spans in ([], [[0,0,0]], [[0,0,161]], [[0,159,2]], [[24159,0,2]], [[0,0,3],[0,2,3]]):
            with self.assertRaises(GameError):validate_space_presentation({"radar_spans":spans})

    def test_legacy_view_does_not_revive_completed_explosions(self):
        battle = battle_fixture();battle["explosions"] = True;battle["hostile_count"] = 0
        battle["hostile"][0]["raw"][10] = 3
        before = deepcopy(battle)
        self.assertFalse(any(c["kind"]=="explosion" for c in space_snapshot_plan(battle,rules_fixture())))
        self.assertEqual(before,battle)

    def test_v9_migration_preserves_numerical_state_and_rejects_invalid_view_fields(self):
        session = prepared();session.apply("space_tick",frames=3)
        state = deepcopy(session.state);state["schema"] = "recovered-strategy-v9";del state['active_scene']
        del state["active_dialog"];del state["campaign"]["system_observatories"];del state["campaign"]["bar"]
        del state["battle_requests"]
        del state["space_encounter"]["radar"]
        del state["space_encounter"]["cinema"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"old.json";path.write_text(json.dumps(state),encoding="utf-8")
            loaded = RecoveredSession.load(session.catalog,path)
            self.assertEqual(loaded.state["space_encounter"]["battle"],session.state["space_encounter"]["battle"])
            self.assertEqual(loaded.state["campaign"],session.state["campaign"])
            self.assertEqual(loaded.state["space_encounter"]["radar"],space_snapshot_plan(
                state["space_encounter"]["battle"],session.catalog["battle_rules"]["space"]))
            state["space_encounter"]["radar"] = []
            path.write_text(json.dumps(state),encoding="utf-8")
            with self.assertRaises(GameError):RecoveredSession.load(session.catalog,path)
        for calls in ([{"kind":"unknown","hull":1,"x":0,"y":0,"step":1}],
                      [{"kind":"explosion","hull":4,"x":0,"y":0,"step":5}],
                      [{"kind":"ship","hull":1,"x":True,"y":0,"side":"friendly"}], [{}]*2001):
            with self.assertRaises(GameError):validate_radar_calls(calls,session.catalog["battle_rules"]["space"])


if __name__ == "__main__":unittest.main()
