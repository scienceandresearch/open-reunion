"""Validate the optional campaign collection without requiring original assets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def validate_collection(folder, content=None):
    folder = Path(folder).resolve()
    manifest = json.loads((folder/'MANIFEST.json').read_text(encoding='utf-8'))
    expected = {row['path'] for row in manifest['files']} | {'MANIFEST.json'}
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    if expected != actual:
        raise ValueError('Checkpoint collection has missing or unlisted files.')
    for row in manifest['files']:
        path = folder/row['path']
        if path.is_symlink() or not path.resolve().is_relative_to(folder):
            raise ValueError('Checkpoint path escapes the collection.')
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Checkpoint file changed without a manifest update: '+row['path'])
    saves = manifest['saves']
    if len(saves) != 23 or len({row['file'] for row in saves}) != 23:
        raise ValueError('Expected the 23 curated checkpoints.')
    for row in saves:
        path = folder/row['file']
        if row['file'] not in expected or not re.fullmatch(r'\d\d - .+\.json', row['file']):
            raise ValueError('Invalid checkpoint filename.')
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Checkpoint does not match its recorded provenance.')
        state = json.loads(data)
        if state.get('schema') != 'recovered-strategy-v23' or state.get('assisted') is not False:
            raise ValueError('Expected an unassisted modern campaign checkpoint.')
        if state.get('log') != []:
            raise ValueError('Public checkpoints must omit historical original message text.')
        if state['date'] != row['date']:
            raise ValueError('Checkpoint date disagrees with its catalog.')
        if content is not None:
            from openreunion.dos.session import RecoveredSession
            session = RecoveredSession.load(content.catalog, path)
            if session.state['date'] != row['date'] or session.state['assisted']:
                raise ValueError('Loaded checkpoint does not match the catalog.')
    return saves


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, default=ROOT/'tester-saves')
    parser.add_argument('--content', type=Path, help='Also validate every save using locally imported content')
    args = parser.parse_args()
    content = None
    if args.content:
        sys.path.insert(0, str(ROOT/'src'))
        from openreunion.dos.content import ContentSource
        content = ContentSource(args.content)
    saves = validate_collection(args.folder, content)
    print(f'Validated {len(saves)} checkpoints; gameplay load checked: {content is not None}.')


if __name__ == '__main__':
    main()
