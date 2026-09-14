"""Offline import of user-supplied files; originals are read, never executed."""
import hashlib
import json
from pathlib import Path
import tempfile

from ..core import GameError
from ..persistence import atomic_write
from .catalog import read_catalog
from .content import ContentSource
from .extraction import recover_data

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024


def asset_layout():
    return json.loads((Path(__file__).parents[1] / 'data/asset-layout.json').read_text())


def original_root(selection):
    """Accept the installation folder, or its launcher / GRWAR/REUNION.PRG."""
    path = Path(selection).resolve()
    if path.is_file():
        return path.parent.parent if path.name.upper() == 'REUNION.PRG' and path.parent.name.upper() == 'GRWAR' else path.parent
    return path


def find_source_file(root, relative):
    """Normalize DOS file casing without following links outside the copy."""
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or '..' in parts:
        raise GameError('Invalid asset inventory path.')
    current = root
    for part in parts:
        if not current.is_dir():
            raise FileNotFoundError(relative)
        matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()]
        if not matches:
            raise FileNotFoundError(relative)
        if len(matches) != 1:
            raise GameError(f'Ambiguous filename casing: {relative}')
        current = matches[0]
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)() or not current.resolve().is_relative_to(root):
            raise GameError(f'Linked game files are not supported: {relative}. Supply a normal extracted copy.')
    if not current.is_file():
        raise FileNotFoundError(relative)
    return current


def inspect_source(selection, layout=None):
    layout = layout or asset_layout()
    root = original_root(selection)
    if not root.is_dir():
        raise GameError('Choose the extracted original Reunion game folder.')
    files = {}
    missing = []
    total = 0
    for relative in layout['required_source_files']:
        try:
            path = find_source_file(root, relative)
        except FileNotFoundError:
            missing.append(relative)
            continue
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise GameError(f'Original file exceeds the import size limit: {relative}')
        total += size
        files[relative] = path
    if missing:
        detail = '\n'.join(missing[:12])
        more = f'\n...and {len(missing)-12} more.' if len(missing) > 12 else ''
        raise GameError(f'This copy is incomplete or the wrong folder was selected. Missing:\n{detail}{more}\n\nChoose the full extracted English game folder. An executable alone is not enough.')
    if total > MAX_TOTAL_BYTES:
        raise GameError('Original files exceed the total import size limit.')
    # Reject unknown executable layouts before doing any conversion.
    read_catalog(files['GRWAR/REUNION.PRG'])
    return root, files


def validate_bundle(folder, layout=None):
    layout = layout or asset_layout()
    folder = Path(folder).resolve()
    missing = [name for name in layout['required_output_files'] if not (folder/name).is_file()]
    if missing:
        raise GameError('Conversion did not produce all required assets:\n' + '\n'.join(missing[:12]))
    if (folder/'sessions').exists():
        raise GameError('An asset-only import must not contain personal save sessions.')
    for name in ('pictures.json', 'text.json'):
        report = json.loads((folder/name).read_text())
        if report['malformed']:
            raise GameError(f'Invalid original content reported in {name}. Import was not installed.')
    # The supported original contains one broken, unused FM version of FAILURE.
    # Its complete MOD version is imported and used by the game.
    music = json.loads((folder/'music.json').read_text())
    if any(row['path'] != 'GRWAR/FAILURE.PIC' for row in music['unsupported']):
        raise GameError('Unexpected unsupported FM music in this copy.')
    content = ContentSource(folder)
    if len(content.catalog['surface_maps']) != 47:
        raise GameError('The import does not include all 47 surface maps.')
    content.new_game()  # Includes SAVE/INIT validation and complete state validation.
    return content


def import_assets(selection, output, *, progress=print):
    """Commit a complete bundle to a new folder, leaving existing data alone."""
    output = Path(output).resolve()
    source = original_root(selection)
    if output.exists():
        raise GameError(f'The destination already exists: {output}. Choose a new folder; existing imports and saves are preserved.')
    if output == source or source.is_relative_to(output) or (
        output.is_relative_to(source) and 'opensource' not in output.relative_to(source).parts
    ):
        raise GameError('Choose an output folder separate from the original installation.')
    progress('Checking the original game folder...')
    layout = asset_layout()
    source, files = inspect_source(source, layout)
    output.parent.mkdir(parents=True, exist_ok=True)
    # All temporary writes and cleanup remain under this resolved destination parent.
    with tempfile.TemporaryDirectory(prefix='.asset-import-', dir=output.parent) as temporary:
        work = Path(temporary).resolve()
        if not work.is_relative_to(output.parent):
            raise GameError('Temporary import path escaped its destination.')
        staged_source = work/'original'
        converted = work/'converted'
        rows = []
        progress('Reading your game files...')
        total = 0
        for relative, path in files.items():
            with path.open('rb') as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            total += len(data)
            if len(data) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                raise GameError('Original content changed or exceeds the import size limit.')
            target = staged_source/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            rows.append({'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        recover_data(staged_source, converted, include_saves=False, progress=progress)
        progress('Checking the complete import and New Game...')
        content = validate_bundle(converted, layout)
        outputs = []
        for path in sorted(converted.rglob('*')):
            if path.is_file():
                data = path.read_bytes()
                outputs.append({'path': path.relative_to(converted).as_posix(), 'bytes': len(data),
                                'sha256': hashlib.sha256(data).hexdigest()})
        report = {'format': 1, 'profile': layout['profile'], 'executable_sha256': content.catalog['sha256'],
                  'original_files_executed': False, 'player_saves_imported': False,
                  'source_files': rows, 'files': outputs}
        atomic_write(converted/'IMPORT-MANIFEST.json', (json.dumps(report, indent=2)+'\n').encode())
        # rename cannot merge with or overwrite an existing nonempty directory.
        # Recheck for another import completing while this one was running.
        if output.exists():
            raise GameError('Another import created the destination. Existing content was preserved.')
        converted.rename(output)
    progress('Import complete. Ready to play.')
    return report
