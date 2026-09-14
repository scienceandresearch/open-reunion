"""Build a manifest-checked source handoff without original asset payloads; includes reviewed modern checkpoints."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]

def source_files(root=ROOT):
    from audit_repository import public_files, check_blob
    from check_checkpoints import validate_collection
    entries = public_files(root)
    for name, path in entries.items():
        check_blob(name, path.read_bytes())
    validate_collection(Path(root)/'tester-saves')
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', help='New archive basename under dist')
    args = parser.parse_args()
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    name = args.name or f'Open-Reunion-{version}-Source-r1'
    if Path(name).name != name or name in ('.', '..'):
        parser.error('Name must be one folder component.')
    destination = ROOT / 'dist' / (name + '.zip')
    checksum = ROOT / 'dist' / (name + '.sha256')
    if destination.exists() or checksum.exists():
        parser.error('Use a fresh name to preserve prior releases.')
    rows = []
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, path in source_files().items():
            data = path.read_bytes()
            rows.append({'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            archive.writestr(name + '/' + relative, data)
        manifest = {'version': version, 'kind': 'source-and-checkpoints',
                    'original_game_assets': False, 'player_saves': True, 'optional_campaign_checkpoints': 23,
                    'files': rows}
        archive.writestr(name + '/MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        for row in rows:
            data = archive.read(name + '/' + row['path'])
            assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    checksum.write_text(digest + '  ' + destination.name + '\n', encoding='ascii')
    print(json.dumps({'archive': str(destination), 'bytes': destination.stat().st_size,
                      'sha256': digest, 'manifest_files': len(rows)}))


if __name__ == '__main__':
    main()
