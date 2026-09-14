"""Exercise the quiet first-run import window against a complete local copy."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))

from openreunion.dos.asset_import import validate_bundle
from openreunion.dos.import_ui import ImportWindow


def resolved_under(path, parent, label):
    path = Path(path).resolve()
    parent = Path(parent).resolve()
    if not path.is_relative_to(parent):
        raise ValueError(f'{label} must remain under {parent}.')
    return path


def pump_until(root, predicate, timeout, heartbeat=None):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise TimeoutError('Import window did not reach the expected state.')
        root.update()
        if heartbeat is not None:
            heartbeat[0] += 1
        time.sleep(.01)
    root.update()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    output = resolved_under(args.output_dir, PROJECT / 'local', '--output-dir')
    report_path = resolved_under(args.report, PROJECT / 'reports', '--report')
    if not source.is_dir():
        parser.error('--source must be the complete extracted game folder.')
    if output.exists():
        parser.error('--output-dir must be a fresh destination.')
    if report_path.exists():
        parser.error('--report must be a fresh path.')
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    window = ImportWindow(root, output)
    started = time.monotonic()
    checks = {}
    try:
        root.update_idletasks()
        checks['initial_choose_enabled'] = window.choose.instate(['!disabled'])
        assert checks['initial_choose_enabled'] and not window.running and not window.complete

        with patch('openreunion.dos.import_ui.filedialog.askdirectory', return_value=''):
            window.browse()
        root.update()
        checks['cancel_created_no_output'] = not output.exists() and not window.running
        assert checks['cancel_created_no_output']

        with tempfile.TemporaryDirectory(prefix='asset-import-invalid-', dir=output.parent) as invalid:
            window.start(invalid)
            assert window.running and window.choose.instate(['disabled'])
            pump_until(root, lambda: not window.running, 30)
        inline = window.status.get()
        checks['invalid_inline_error'] = (
            ('incomplete or the wrong folder' in inline or 'extracted original Reunion game folder' in inline)
            and window.choose.instate(['!disabled']) and not output.exists()
        )
        assert checks['invalid_inline_error'], inline

        heartbeat = [0]
        window.start(source)
        checks['choose_disabled_during_import'] = window.running and window.choose.instate(['disabled'])
        assert checks['choose_disabled_during_import']
        pump_until(root, lambda: not window.running, 600, heartbeat)
        checks['responsive_tk_updates'] = heartbeat[0] >= 2
        checks['completed'] = window.complete
        checks['finish_visible'] = window.finish.winfo_manager() == 'pack'
        assert checks['responsive_tk_updates']
        assert checks['completed'], window.status.get()
        assert checks['finish_visible']

        content = validate_bundle(output)
        manifest = json.loads((output / 'IMPORT-MANIFEST.json').read_text())
        checks['valid_bundle'] = bool(content.catalog['sha256'])
        checks['no_saves'] = (
            not (output / 'sessions').exists()
            and manifest['player_saves_imported'] is False
            and all(not row['path'].startswith('sessions/') for row in manifest['files'])
        )
        assert checks['valid_bundle'] and checks['no_saves']
        result = {
            'passed': True,
            'scope': 'Quiet Tk import window, cancellation, retry, real conversion and save-free validation; no game or audio initialized.',
            'source_executable_sha256': content.catalog['sha256'],
            'output': str(output),
            'output_files': len(manifest['files']) + 1,
            'responsive_updates': heartbeat[0],
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'checks': checks,
        }
        report_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    finally:
        if root.winfo_exists():
            window.close()
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
