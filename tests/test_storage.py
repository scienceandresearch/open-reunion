import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openreunion.core import GameError, from_dict, new_game
from openreunion.legacy import LegacySave, RESOURCE_OFFSETS, SAVE_SIZE, TerrainMap, export_legacy, production_candidates
from openreunion.persistence import load_game, save_game


def sample_save():
    # Synthetic fixture: no original game data is distributed with the tests.
    data = bytearray((i * 17) % 256 for i in range(SAVE_SIZE))
    data[:7] = b"\x06Save 1"
    for offset in RESOURCE_OFFSETS.values():
        struct.pack_into("<I", data, offset, 123)
    return bytes(data)


class LegacyTests(unittest.TestCase):
    def test_resource_edits_preserve_all_other_bytes(self):
        original = sample_save()
        changes = {"credits": 1000000, "energon": 5000}
        modified = LegacySave(original).with_resources(changes)
        allowed = {offset+i for key, offset in RESOURCE_OFFSETS.items() if key in changes for i in range(4)}
        self.assertEqual(len(modified), SAVE_SIZE)
        for i, (a, b) in enumerate(zip(original, modified)):
            if i not in allowed:
                self.assertEqual(a, b, f"Unexpected mutation at {i:#x}")
        self.assertEqual(LegacySave(modified).resources()["credits"], 1000000)

    def test_invalid_sizes_and_names(self):
        for data in (b"", sample_save()[:-1], sample_save()+b"x", bytes(SAVE_SIZE)):
            with self.assertRaises(GameError):
                LegacySave(data)

    def test_unknown_offsets_and_out_of_range_are_rejected(self):
        for changes in ({"toxon": 1}, {"unknown": 1}, {"credits": -1}, {"credits": 2**32}, {"credits": True}, {}):
            with self.assertRaises(GameError):
                LegacySave(sample_save()).with_resources(changes)

    def test_u32_boundaries(self):
        for value in (0, 2**32-1):
            result = LegacySave(sample_save()).with_resources({"credits": value})
            self.assertEqual(LegacySave(result).resources()["credits"], value)

    def test_export_refuses_source_or_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/"SPIDYSAV.1", Path(directory)/"edited"
            source.write_bytes(sample_save())
            with self.assertRaises(GameError):
                export_legacy(source, source, {"credits": 1})
            export_legacy(source, output, {"credits": 1})
            with self.assertRaises(FileExistsError):
                export_legacy(source, output, {"credits": 2})
            self.assertEqual(source.read_bytes(), sample_save())

    def test_terrain_grid_and_bounds(self):
        terrain = TerrainMap.decode(bytes([3, 2, 10, 20, 30, 40, 50, 60]))
        self.assertEqual(terrain.tile(2, 1), 60)
        with self.assertRaises(GameError):
            terrain.tile(-1, 0)
        with self.assertRaises(GameError):
            terrain.tile(3, 0)

    def test_terrain_rejects_truncation_trailing_data_zero_dimensions(self):
        for data in (b"", b"\x01", b"\0\0", b"\2\2\1\2\3", b"\1\1\1\1"):
            with self.assertRaises(GameError):
                TerrainMap.decode(data)

    def test_production_scanner_bounds(self):
        self.assertEqual(production_candidates(b""), [])
        data = bytearray(0x457E0)
        data[0x450D1:0x450D1+12] = b"\x0bMiner droid"
        struct.pack_into("<I", data, 0x450D1+0x1F, 70)
        self.assertEqual(production_candidates(data)[0]["candidate_work_u32"], 70)


class SaveTests(unittest.TestCase):
    def test_roundtrip_and_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"game.json"
            state = new_game()
            save_game(state, path)
            self.assertEqual(load_game(path).to_dict(), state.to_dict())
            state.credits = 5
            save_game(state, path)
            self.assertEqual(load_game(path).credits, 5)

    def test_failed_replace_keeps_previous_save_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"game.json"
            save_game(new_game(), path)
            before = path.read_bytes()
            state = new_game()
            state.credits = 1
            with patch("openreunion.persistence.os.replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    save_game(state, path)
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_bad_save_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"game.json"
            save_game(new_game(), path)
            before = path.read_bytes()
            state = new_game()
            state.credits = -1
            with self.assertRaises(GameError):
                save_game(state, path)
            self.assertEqual(path.read_bytes(), before)

    def test_schema_and_shape_rejection(self):
        mutations = [lambda s: s.update(schema=99), lambda s: s.update(credits=True),
                     lambda s: s.update(researched={}), lambda s: s.update(messages="bad"),
                     lambda s: s.update(planets=[]), lambda s: s.update(unknown=1),
                     lambda s: s["planets"]["new_earth"].update(ores={}),
                     lambda s: s["planets"]["new_earth"]["buildings"].append(s["planets"]["new_earth"]["buildings"][0]),
                     lambda s: s.update(research="satellite", research_left=0),
                     lambda s: s.update(admin_log=[{"hour": 1, "command": "finish"}])]
        for mutation in mutations:
            raw = new_game().to_dict()
            mutation(raw)
            with self.subTest(raw=raw), self.assertRaises(GameError):
                from_dict(raw)

    def test_malformed_json_duplicate_keys_and_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"game.json"
            for content in (b"{", b'{"schema":1,"schema":1}', b"\xff", b" " * (4*1024*1024+1)):
                path.write_bytes(content)
                with self.assertRaises(GameError):
                    load_game(path)
