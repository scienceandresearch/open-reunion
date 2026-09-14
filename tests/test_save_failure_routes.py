"""Failed load/new-game backups must preserve the player's current campaign.

Uses real session serialization and temporary files. Only presentation objects
are stand-ins; no Tk window or audio device is opened.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_surface import surface_session
from openreunion.core import GameError
from openreunion.dos.ui import RecoveredApp


def app_fixture(directory):
    session = surface_session()
    return SimpleNamespace(session=session, catalog=session.catalog,
                           save_dir=Path(directory), pause_battles=Mock(),
                           effects=SimpleNamespace(prepare=Mock()),
                           music_panel=SimpleNamespace(capture=Mock()),
                           admin=SimpleNamespace(set=Mock()), refresh=Mock())


class SaveFailureRoutesTests(unittest.TestCase):
    def test_invalid_load_preserves_campaign_and_existing_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            app = app_fixture(directory)
            original = app.session
            before = deepcopy(original.state)
            backup = app.save_dir / 'recovered-before-load.json'
            original.save(backup)
            backup_bytes = backup.read_bytes()
            bad = app.save_dir / 'broken.json'
            for raw in (b'{', b'\xff', b'{"schema":1,"schema":2}'):
                bad.write_bytes(raw)
                with self.subTest(raw=raw), self.assertRaises(GameError):
                    RecoveredApp.load_path(app, bad)
                self.assertIs(app.session, original)
                self.assertEqual(original.state, before)
                self.assertEqual(backup.read_bytes(), backup_bytes)
                self.assertEqual(bad.read_bytes(), raw)
            app.refresh.assert_not_called()
            app.music_panel.capture.assert_not_called()

    def test_backup_replace_failure_preserves_campaign_and_all_save_files(self):
        for operation, name in (('load', 'recovered-before-load.json'),
                                ('new_game', 'recovered-before-new-game.json')):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                app = app_fixture(directory)
                original = app.session
                before = deepcopy(original.state)
                backup = app.save_dir / name
                original.save(backup)
                candidate = surface_session()
                candidate.state['resources']['credits'] += 1
                incoming = app.save_dir / 'incoming.json'
                candidate.save(incoming)
                app.content = SimpleNamespace(new_game=Mock(return_value=candidate))
                files = {path.name: path.read_bytes() for path in app.save_dir.iterdir()}
                with patch('openreunion.persistence.os.replace', side_effect=OSError('Simulated disk failure')):
                    with self.assertRaisesRegex(OSError, 'Simulated disk failure'):
                        if operation == 'load':
                            RecoveredApp.load_path(app, incoming)
                        else:
                            RecoveredApp.new_game(app)
                self.assertIs(app.session, original)
                self.assertEqual(original.state, before)
                self.assertEqual({path.name: path.read_bytes() for path in app.save_dir.iterdir()}, files)
                app.refresh.assert_not_called()
                app.admin.set.assert_not_called()
