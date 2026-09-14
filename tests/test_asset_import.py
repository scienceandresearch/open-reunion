"""Synthetic bounds and transaction checks for original-file import."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from openreunion.core import GameError
from openreunion.dos import asset_import


def minimal_layout():
    return {
        'profile': 'synthetic-reunion',
        'required_source_files': ['GRWAR/REUNION.PRG', 'SAVE/INIT'],
        'required_output_files': [
            'catalog.json', 'pictures.json', 'text.json', 'music.json',
            'startup.json',
        ],
    }


def make_source(parent, *, lowercase=False):
    root = Path(parent) / 'original'
    grwar = 'grwar' if lowercase else 'GRWAR'
    executable = 'reunion.prg' if lowercase else 'REUNION.PRG'
    save = 'save' if lowercase else 'SAVE'
    (root / grwar).mkdir(parents=True)
    (root / save).mkdir()
    (root / grwar / executable).write_bytes(b'synthetic executable')
    (root / save / 'init').write_bytes(b'synthetic init')
    return root


def write_converted(folder):
    folder = Path(folder)
    folder.mkdir(parents=True)
    (folder / 'catalog.json').write_text('{}')
    (folder / 'pictures.json').write_text(json.dumps({'malformed': []}))
    (folder / 'text.json').write_text(json.dumps({'malformed': []}))
    (folder / 'music.json').write_text(json.dumps({
        'unsupported': [{'path': 'GRWAR/FAILURE.PIC'}],
    }))
    (folder / 'startup.json').write_text('{}')
    nested = folder / 'pictures' / 'GRAFIKA'
    nested.mkdir(parents=True)
    (nested / 'MAIN.png').write_bytes(b'converted pixels')


class AssetImportTests(unittest.TestCase):
    def test_inventory_paths_cannot_escape_source_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for relative in ('', '../outside.bin', 'GRWAR/../outside.bin', root / 'outside.bin'):
                with self.subTest(relative=relative), self.assertRaisesRegex(GameError, 'Invalid asset inventory path'):
                    asset_import.find_source_file(root, relative)

    def test_wrong_or_incomplete_folder_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'wrong-folder'
            root.mkdir()
            with patch.object(asset_import, 'read_catalog') as read_catalog:
                with self.assertRaises(GameError) as raised:
                    asset_import.inspect_source(root, minimal_layout())
            message = str(raised.exception)
            self.assertIn('incomplete or the wrong folder', message)
            self.assertIn('GRWAR/REUNION.PRG', message)
            self.assertIn('SAVE/INIT', message)
            self.assertIn('executable alone is not enough', message.lower())
            read_catalog.assert_not_called()

    def test_missing_selection_has_helpful_folder_message(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / 'does-not-exist'
            with self.assertRaisesRegex(GameError, 'extracted original Reunion game folder'):
                asset_import.inspect_source(missing, minimal_layout())

    def test_source_paths_are_normalized_case_insensitively(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_source(directory, lowercase=True)
            with patch.object(asset_import, 'read_catalog') as read_catalog:
                found_root, files = asset_import.inspect_source(root, minimal_layout())
            self.assertEqual(found_root, root.resolve())
            self.assertEqual(set(files), {'GRWAR/REUNION.PRG', 'SAVE/INIT'})
            self.assertEqual(files['GRWAR/REUNION.PRG'].name, 'reunion.prg')
            self.assertEqual(files['SAVE/INIT'].name, 'init')
            read_catalog.assert_called_once_with(files['GRWAR/REUNION.PRG'])

    def test_unsupported_executable_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_source(directory)
            output = Path(directory) / 'new-parent' / 'content'
            with patch.object(asset_import, 'asset_layout', return_value=minimal_layout()), \
                    patch.object(asset_import, 'read_catalog', side_effect=GameError('Unsupported executable size.')), \
                    patch.object(asset_import, 'recover_data') as recover_data:
                with self.assertRaisesRegex(GameError, 'Unsupported executable'):
                    asset_import.import_assets(root, output)
            self.assertFalse(output.parent.exists())
            recover_data.assert_not_called()

    def test_existing_destination_is_preserved_without_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_source(directory)
            output = Path(directory) / 'content'
            output.mkdir()
            sentinel = output / 'keep.bin'
            sentinel.write_bytes(b'preserve me')
            with patch.object(asset_import, 'inspect_source') as inspect_source:
                with self.assertRaisesRegex(GameError, 'destination already exists'):
                    asset_import.import_assets(root, output)
            self.assertEqual(sentinel.read_bytes(), b'preserve me')
            inspect_source.assert_not_called()

    def test_source_and_output_overlap_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_source(directory)
            cases = (
                (root, 'destination already exists'),
                (root.parent, 'destination already exists'),
                (root / 'converted', 'separate from the original installation'),
            )
            for output, message in cases:
                with self.subTest(output=output), patch.object(asset_import, 'inspect_source') as inspect_source:
                    with self.assertRaisesRegex(GameError, message):
                        asset_import.import_assets(root, output)
                    inspect_source.assert_not_called()

    def test_conversion_failure_leaves_no_target_temporary_data_or_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_source(directory)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            output = Path(directory) / 'destination' / 'content'

            def fail_after_write(staged, converted, **kwargs):
                converted.mkdir(parents=True)
                (converted / 'partial.bin').write_bytes(b'partial')
                raise OSError('synthetic conversion failure')

            with patch.object(asset_import, 'asset_layout', return_value=minimal_layout()), \
                    patch.object(asset_import, 'read_catalog'), \
                    patch.object(asset_import, 'recover_data', side_effect=fail_after_write), \
                    patch.object(asset_import, 'validate_bundle') as validate_bundle:
                with self.assertRaisesRegex(OSError, 'synthetic conversion failure'):
                    asset_import.import_assets(root, output)
            self.assertFalse(output.exists())
            self.assertFalse(list(output.parent.glob('.asset-import-*')))
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(after, before)
            validate_bundle.assert_not_called()

    def test_success_uses_staged_copy_excludes_saves_and_commits_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_source(directory, lowercase=True)
            output = Path(directory) / 'destination' / 'content'
            progress = Mock()
            calls = {}

            def convert(staged, converted, **kwargs):
                calls['staged'] = Path(staged)
                calls['converted'] = Path(converted)
                calls['kwargs'] = kwargs
                self.assertNotEqual(Path(staged), root.resolve())
                self.assertEqual((Path(staged) / 'GRWAR/REUNION.PRG').read_bytes(), b'synthetic executable')
                self.assertEqual((Path(staged) / 'SAVE/INIT').read_bytes(), b'synthetic init')
                write_converted(converted)

            content = SimpleNamespace(catalog={'sha256': 'ab' * 32})
            layout = minimal_layout()
            with patch.object(asset_import, 'asset_layout', return_value=layout), \
                    patch.object(asset_import, 'read_catalog'), \
                    patch.object(asset_import, 'recover_data', side_effect=convert) as recover_data, \
                    patch.object(asset_import, 'validate_bundle', return_value=content) as validate_bundle:
                report = asset_import.import_assets(root, output, progress=progress)

            recover_data.assert_called_once()
            self.assertIs(calls['kwargs']['progress'], progress)
            self.assertIs(calls['kwargs']['include_saves'], False)
            validate_bundle.assert_called_once_with(calls['converted'], layout)
            self.assertTrue(output.is_dir())
            self.assertFalse((output / 'sessions').exists())
            manifest = json.loads((output / 'IMPORT-MANIFEST.json').read_text())
            self.assertEqual(manifest, report)
            self.assertFalse(manifest['original_files_executed'])
            self.assertFalse(manifest['player_saves_imported'])
            self.assertEqual(manifest['executable_sha256'], 'ab' * 32)
            self.assertEqual(
                {row['path'] for row in manifest['source_files']},
                {'GRWAR/REUNION.PRG', 'SAVE/INIT'},
            )
            output_paths = {row['path'] for row in manifest['files']}
            self.assertIn('pictures/GRAFIKA/MAIN.png', output_paths)
            self.assertIn('catalog.json', output_paths)
            self.assertNotIn('IMPORT-MANIFEST.json', output_paths)
            self.assertFalse(list(output.parent.glob('.asset-import-*')))
            self.assertEqual((root / 'grwar/reunion.prg').read_bytes(), b'synthetic executable')
            self.assertEqual((root / 'save/init').read_bytes(), b'synthetic init')


if __name__ == '__main__':
    unittest.main()
