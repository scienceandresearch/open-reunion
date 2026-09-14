"""Recovered-session serialization remains reloadable within its size cap."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openreunion.core import GameError
from openreunion.dos import session as session_module
from openreunion.dos.session import RecoveredSession
from test_surface import surface_session


def payload_for(session):
    return dict(session.state, audio=session.audio, effects=session.effects,
                result_animation=session.result_animation, hero=session.hero)


class RecoveredSessionSaveSizeTests(unittest.TestCase):
    def test_oversized_pretty_payload_falls_back_to_compact_utf8_and_roundtrips(self):
        session = surface_session()
        # This is valid session text.  The lone surrogate specifically needs
        # the fallback encoder's JSON-safe backslash replacement.
        session.state["log"] = [(chr(0x10000) * 499) + "\ud800"]
        payload = payload_for(session)
        pretty = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
        compact = (json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                              allow_nan=False) + "\n").encode("utf-8", errors="backslashreplace")
        self.assertGreater(len(pretty), len(compact))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fallback.json"
            with patch.object(session_module, "MAX_SAVE_BYTES", len(compact)):
                session.save(path)
                self.assertEqual(path.read_bytes(), compact)
                restored = RecoveredSession.load(session.catalog, path)
        self.assertEqual(restored.state, session.state)
        self.assertEqual(restored.audio, session.audio)
        self.assertEqual(restored.effects, session.effects)
        self.assertEqual(restored.result_animation, session.result_animation)
        self.assertEqual(restored.hero, session.hero)

    def test_ordinary_save_retains_preexisting_pretty_bytes(self):
        session = surface_session()
        expected = (json.dumps(payload_for(session), indent=2, allow_nan=False) + "\n").encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ordinary.json"
            session.save(path)
            self.assertEqual(path.read_bytes(), expected)

    def test_save_too_large_even_when_compact_preserves_existing_file(self):
        session = surface_session()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preserved.json"
            session.save(path)
            before = path.read_bytes()
            with patch.object(session_module, "MAX_SAVE_BYTES", 1):
                with self.assertRaises(GameError):
                    session.save(path)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
