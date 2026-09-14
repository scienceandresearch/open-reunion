"""Synthetic checks for the publication guard."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from audit_repository import audit, check_blob, public_files


class RepositoryAuditTests(unittest.TestCase):
    def test_original_media_and_generated_files_are_rejected(self):
        for name in ('src/original.PIC', 'docs/screen.png', 'local/recovered/catalog.json',
                     'reports/results.json', 'saves/player.json', 'src/surprise.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_blob(name, b'{}')

    def test_binary_disguised_as_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'binary contents'):
            check_blob('src/payload.py', b'hello\0world')
        with self.assertRaisesRegex(ValueError, 'embedded hex'):
            check_blob('src/payload.py', ('data="'+'a3'*600+'"').encode())

    def test_unknown_nested_archive_is_rejected(self):
        with self.assertRaises(ValueError):
            check_blob('third_party/unknown.zip', b'PK')
        with self.assertRaisesRegex(ValueError, 'pinned upstream'):
            check_blob('third_party/libopenmpt/source-0.8.9-msvc.zip', b'PK')

    def test_checkpoint_cannot_reintroduce_original_history_text(self):
        with self.assertRaisesRegex(ValueError, 'historical original text'):
            check_blob('tester-saves/01 - Example.json', b'{"schema":"recovered-strategy-v23","log":["unreviewed narrative"]}')

    def test_staged_audit_reads_index_blob_not_working_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'README.md').write_text('Harmless working copy')
            with patch('audit_repository.subprocess.check_output', side_effect=[b'README.md\0', b'bad\0payload']) as call:
                with self.assertRaisesRegex(ValueError, 'binary contents'):
                    audit(root, staged=True)
            self.assertEqual(call.call_args_list[1].args[0], ['git', 'show', ':README.md'])

    def test_public_worktree_rejects_unreviewed_root_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'README.md').write_text('Project')
            (root/'private-notes.txt').write_text('Private')
            with self.assertRaisesRegex(ValueError, 'Unapproved repository root file'):
                public_files(root)


if __name__ == '__main__':
    unittest.main()
