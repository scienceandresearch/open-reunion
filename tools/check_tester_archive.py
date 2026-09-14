"""Extract a new portable build, verify its manifest, and run its frozen test."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

PROJECT = Path(__file__).resolve().parents[1]


def validate_checkpoints(folder):
    """Verify the optional checkpoint collection and return its save entries."""
    manifest = json.loads((folder/'MANIFEST.json').read_text(encoding='utf-8'))
    expected = {entry['path'] for entry in manifest['files']} | {'MANIFEST.json'}
    actual = {path.relative_to(folder).as_posix() for path in folder.rglob('*') if path.is_file()}
    assert expected == actual, 'Optional save collection membership changed.'
    for entry in manifest['files']:
        path = (folder/entry['path']).resolve()
        assert path.is_relative_to(folder.resolve()) and not path.is_symlink(), entry['path']
        data = path.read_bytes()
        assert len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256'], entry['path']
    return manifest['saves']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--extract-to', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--original-source', type=Path, help='For asset-free packages: import this local original copy before the frozen test')
    a = p.parse_args()
    archive, destination, report = a.archive.resolve(), a.extract_to.resolve(), a.output.resolve()
    if any(not path.is_relative_to(PROJECT) for path in (archive, destination, report)):
        p.error('All paths must be inside opensource')
    if destination.exists() or report.exists():
        p.error('Choose new extraction/report paths to preserve prior evidence')
    report.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            if not (destination/member.filename).resolve().is_relative_to(destination):
                p.error('Archive entry escapes the extraction folder')
        zipped.extractall(destination)
    package = destination/archive.stem
    manifest = json.loads((package/'MANIFEST.json').read_text())
    assert manifest['original_content_included'] is False
    assert manifest['first_run_asset_import'] is True
    expected = {row['path'] for row in manifest['files']} | {'MANIFEST.json'}
    actual = {path.relative_to(package).as_posix() for path in package.rglob('*') if path.is_file()}
    assert expected == actual, 'Archive contains missing or unmanifested files.'
    for row in manifest['files']:
        path = (package/row['path']).resolve()
        if not path.is_relative_to(package):
            p.error('Manifest entry escapes the package')
        data = path.read_bytes()
        assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], row['path']
    checkpoints = package/'Optional Saves'
    if manifest['supplied_player_saves_included']:
        saves = validate_checkpoints(checkpoints)
        assert len(saves) == manifest['optional_campaign_checkpoints']
    else:
        assert manifest['optional_campaign_checkpoints'] == 0 and not checkpoints.exists()
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['PATH'] = str(Path(os.environ['SystemRoot'])/'System32')
    imported = False
    if a.original_source:
        for name in ('local/recovered', 'tester-saves', 'saves', 'reports'):
            assert not (package/name).exists(), name
        subprocess.run([str(package/'OpenReunion.exe'), '--import-from', str(a.original_source.resolve()), '--import-only'],
                       cwd=destination, env=env, check=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
        bundle = package/'local/recovered'
        import_report = json.loads((bundle/'IMPORT-MANIFEST.json').read_text())
        assert import_report['player_saves_imported'] is False
        assert import_report['original_files_executed'] is False
        assert not (bundle/'sessions').exists()
        for row in import_report['files']:
            path = (bundle/row['path']).resolve()
            assert path.is_relative_to(bundle)
            data = path.read_bytes()
            assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
        imported = True
    subprocess.run([str(package/'OpenReunion.exe'), '--self-test', '--output', str(report)],
                   cwd=destination, env=env, check=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
    result = json.loads(report.read_text())
    assert result['passed'] and result['frozen']
    assert result['version'] == manifest['version']
    result.update(archive=str(archive), sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  manifest_files_checked=len(manifest['files']), path_with_spaces=' ' in str(destination),
                  python_on_path=False)
    if imported:
        result.update(asset_free_archive=True, frozen_asset_import=True,
                      imported_asset_files=len(import_report['files']), original_files_executed=False,
                      personal_saves_imported=False)
    report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
