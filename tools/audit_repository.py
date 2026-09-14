"""Check public file selection and staged Git blobs before publication.

This is a technical guard against asset/secret inclusion, not legal clearance.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_ARCHIVE = 'third_party/libopenmpt/source-0.8.9-msvc.zip'
DEPENDENCY_SHA256 = '8d3b3c14b92dd1fcbb31b2bf28ed917c1d3b529b0d9380562d5bdb6256d32bea'
ROOT_FILES = {
    '.gitignore', '.gitattributes', 'LICENSE', 'README.md', 'CONTRIBUTING.md',
    'THIRD_PARTY.md', 'QUICKSTART.md', 'PLAYER-GUIDE.md', 'TEST-BUILD.md',
    'TESTER-FEEDBACK.md', 'status.md', 'HANDOFF.md', 'pyproject.toml', 'run.py',
    'Import-Assets.cmd', 'Launch-Original.cmd', 'Launch-Recovered.cmd', 'Launch.cmd',
}
SOURCE_DIRECTORIES = {'src', 'tests', 'tools', 'native', 'third_party', 'docs', '.github', 'tester-saves'}
LOCAL_DIRECTORIES = {'local', 'saves', 'reports', 'dist', 'build', '.git', '.venv', '__pycache__'}
TEXT_EXTENSIONS = {'.py', '.c', '.h', '.md', '.txt', '.json', '.yml', '.yaml', '.toml', '.cmd'}
DATA_FILES = {'src/openreunion/data/prototype.json', 'src/openreunion/data/save-layout.json',
              'src/openreunion/data/asset-layout.json'}
SECRETS = (
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    re.compile(rb'\bAKIA[0-9A-Z]{16}\b'),
)


def public_files(root=ROOT):
    """Enumerate a curated working tree, never generated/ignored data."""
    root = Path(root).resolve()
    files = {}
    for child in root.iterdir():
        if child.name in LOCAL_DIRECTORIES or child.name == 'MANIFEST.json' or child.name.endswith('.egg-info'):
            continue
        if child.is_symlink():
            raise ValueError('Repository symlinks are not approved: '+child.name)
        if child.is_file():
            if child.name not in ROOT_FILES:
                raise ValueError('Unapproved repository root file: '+child.name)
            files[child.name] = child
        elif child.is_dir():
            if child.name not in SOURCE_DIRECTORIES:
                raise ValueError('Unapproved repository root directory: '+child.name)
            for path in child.rglob('*'):
                if '__pycache__' in path.parts or any(part.endswith('.egg-info') for part in path.parts):
                    continue
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    raise ValueError('Repository path escapes its root: '+str(path))
                if path.is_file():
                    files[path.relative_to(root).as_posix()] = path
    return dict(sorted(files.items()))


def check_blob(name, data):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name:
        raise ValueError('Unsafe repository path: '+name)
    if path.parts[0] in LOCAL_DIRECTORIES:
        raise ValueError('Generated or private content is tracked: '+name)
    if len(path.parts) == 1:
        if name not in ROOT_FILES:
            raise ValueError('Unapproved root file: '+name)
    elif path.parts[0] not in SOURCE_DIRECTORIES:
        raise ValueError('Unapproved source directory: '+name)
    if name == DEPENDENCY_ARCHIVE:
        if hashlib.sha256(data).hexdigest() != DEPENDENCY_SHA256:
            raise ValueError('Third-party source archive differs from pinned upstream.')
        return
    if path.suffix.lower() not in TEXT_EXTENSIONS and name not in ROOT_FILES and name != 'third_party/nuked_opl3/LICENSE':
        raise ValueError('Binary/asset or unapproved file type: '+name)
    if b'\0' in data:
        raise ValueError('Unexpected binary contents: '+name)
    for pattern in SECRETS:
        if pattern.search(data):
            raise ValueError('Possible credential in '+name+'; contents withheld.')
    if re.search(rb'(?:C:[/\\]Users[/\\][A-Za-z0-9_. -]+[/\\]|/home/[A-Za-z0-9_.-]+/)', data):
        raise ValueError('Personal absolute path in '+name)
    if path.suffix.lower() == '.json':
        if name not in DATA_FILES and path.parts[0] != 'tester-saves' and not name.startswith('third_party/'):
            raise ValueError('Unreviewed JSON data file: '+name)
        value = json.loads(data)
        if name.startswith('tester-saves/') and path.name != 'MANIFEST.json':
            if value.get('schema') != 'recovered-strategy-v23' or value.get('log') != []:
                raise ValueError('Checkpoint contains unreviewed state or historical original text: '+name)
            if value.get('active_dialog') is not None or value.get('active_scene') is not None:
                raise ValueError('Checkpoint embeds an active narrative: '+name)
    # Large literals can conceal asset payloads even inside source code.
    if path.suffix == '.py':
        tree = ast.parse(data, filename=name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, (bytes, str)):
                continue
            value = node.value
            if isinstance(value, bytes) and len(value) > 512:
                raise ValueError(f'Large embedded binary literal: {name}:{node.lineno}')
            if isinstance(value, str) and len(value) > 1024 and re.fullmatch('[0-9a-fA-F]+', value):
                raise ValueError(f'Large embedded hex literal: {name}:{node.lineno}')


def audit(root=ROOT, staged=False):
    root = Path(root).resolve()
    if staged:
        names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
        blobs = {name: subprocess.check_output(['git', 'show', ':'+name], cwd=root) for name in names if name}
    else:
        blobs = {name: path.read_bytes() for name, path in public_files(root).items()}
    if not blobs:
        raise ValueError('No public files selected.')
    for name, data in blobs.items():
        check_blob(name, data)
    # Check index-to-index hashes too; a clean working copy cannot hide a
    # different checkpoint or manifest already staged for publication.
    collection = {name[len('tester-saves/'):]: data for name, data in blobs.items() if name.startswith('tester-saves/')}
    if collection:
        manifest = json.loads(collection['MANIFEST.json'])
        if {row['path'] for row in manifest['files']} | {'MANIFEST.json'} != set(collection):
            raise ValueError('Selected checkpoint collection membership differs from its manifest.')
        for row in manifest['files']:
            data = collection[row['path']]
            if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Selected checkpoint blob differs from its manifest: '+row['path'])
    return blobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true', help='Read the Git index, not working-tree copies')
    args = parser.parse_args()
    blobs = audit(staged=args.staged)
    from check_checkpoints import validate_collection
    validate_collection(ROOT/'tester-saves')
    print(f'Public-file audit passed: {len(blobs)} files; 23 checkpoints; pinned third-party source archive.')


if __name__ == '__main__':
    main()
