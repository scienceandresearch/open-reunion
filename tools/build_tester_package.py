"""Build a public Windows asset-importer package without original game content."""
import argparse
import hashlib
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', help='Unique output folder name under dist')
    parser.add_argument('--without-game-assets', action='store_true',
                        help='Compatibility flag; public builds always exclude original game assets')
    parser.add_argument('--content-bundle', type=Path,
                        default=ROOT/'local/recovered',
                        help='Local content for verification only; never included (default: local/recovered)')
    args = parser.parse_args()
    content_bundle = args.content_bundle.resolve()
    if not content_bundle.is_dir():
        parser.error('--content-bundle must be an existing directory used only for local verification')
    version = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
    name = args.name or f'Open-Reunion-{version}-Windows'
    if Path(name).name != name or name in ('.', '..'):
        parser.error('Name must be one folder component')
    output = ROOT/'dist'/name
    archive = ROOT/'dist'/(name+'.zip')
    if output.exists() or archive.exists():parser.error('Choose a new name to preserve existing builds')
    work = ROOT/'local/package-build'/name
    work.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
               '--name', name, '--paths', str(ROOT/'src'), '--collect-submodules', 'openreunion',
               '--add-data', str(ROOT/'src/openreunion/data')+os.pathsep+'openreunion/data',
               '--distpath', str(ROOT/'dist'), '--workpath', str(work/'work'),
               '--specpath', str(work), str(ROOT/'tools/tester_launcher.py')]
    print('Building Windows runtime; log:', work/'pyinstaller.log', flush=True)
    # Let PyInstaller discover the module decoder's MSVC and codec dependencies.
    # The external copies below also support the included source launcher.
    for dll in ('libopenmpt','openmpt-mpg123','openmpt-ogg','openmpt-vorbis','openmpt-zlib'):
        command[-1:-1]=['--add-binary',str(ROOT/f'local/native/{dll}.dll')+os.pathsep+'local/native']
    with (work/'pyinstaller.log').open('w', encoding='utf-8') as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    (output/(name+'.exe')).rename(output/'OpenReunion.exe')
    def copy_file(relative):
        destination = output/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/relative, destination)
    for folder in ('src', 'native', 'third_party/nuked_opl3', 'third_party/runtime-notices', 'third_party/libopenmpt'):
        shutil.copytree(ROOT/folder, output/folder,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', '*.egg-info'))
    for relative in ('run.py', 'pyproject.toml', 'Launch-Recovered.cmd', 'Launch-Original.cmd', 'LICENSE', 'THIRD_PARTY.md',
                     'QUICKSTART.md', 'PLAYER-GUIDE.md', 'TESTER-FEEDBACK.md', 'TEST-BUILD.md',
                     'Import-Assets.cmd', 'docs/ASSET-IMPORT.md',
                     'tools/build_audio.py', 'tools/build_tester_package.py', 'tools/tester_launcher.py',
                     'tools/check_graphical_clock.py', 'tools/check_tester_archive.py',
                     'local/native/openreunion_opl.dll',
                     'tools/install_module_audio.py',
                     'local/native/libopenmpt.dll', 'local/native/openmpt-mpg123.dll',
                     'local/native/openmpt-ogg.dll', 'local/native/openmpt-vorbis.dll', 'local/native/openmpt-zlib.dll'):
        copy_file(relative)
    # Curated, optional checkpoints live separately from the player's own saves.
    checkpoints = ROOT/'tester-saves'
    if not checkpoints.is_dir():
        parser.error('The validated tester-saves collection is required for public packages')
    checkpoint_manifest = json.loads((checkpoints/'MANIFEST.json').read_text())
    expected = {entry['path'] for entry in checkpoint_manifest['files']} | {'MANIFEST.json'}
    actual = {path.relative_to(checkpoints).as_posix() for path in checkpoints.rglob('*') if path.is_file()}
    if expected != actual:raise ValueError('Optional save collection membership changed.')
    for entry in checkpoint_manifest['files']:
        path = checkpoints/entry['path']
        if path.is_symlink() or not path.resolve().is_relative_to(checkpoints.resolve()):
            raise ValueError('Optional save path escapes its collection.')
        data = path.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:
            raise ValueError('Optional save collection hash mismatch: '+entry['path'])
    shutil.copytree(checkpoints,output/'Optional Saves')
    checkpoint_count = len(checkpoint_manifest['saves'])
    setup_guide = (ROOT/'docs/ASSET-IMPORT.md').read_text(encoding='utf-8')
    (output/'QUICKSTART.md').write_text(setup_guide, encoding='utf-8')
    (output/'README.txt').write_text(setup_guide, encoding='utf-8')
    (output/'QUICKSTART.txt').write_text((output/'QUICKSTART.md').read_text(encoding='utf-8'), encoding='utf-8')
    licenses = output/'licenses'
    licenses.mkdir()
    for path in (ROOT/'third_party/runtime-notices').iterdir():
        if path.is_file():shutil.copy2(path, licenses/path.name)
    shutil.copy2(Path(sys.base_prefix)/'LICENSE.txt', licenses/'PYTHON.txt')
    shutil.copy2(Path(sys.base_prefix)/'tcl/tk8.6/license.terms', licenses/'TCL-TK.txt')
    for package in ('pyinstaller', 'pyinstaller-hooks-contrib'):
        dist = distribution(package)
        for path in dist.files:
            if '/licenses/' in str(path).replace('\\', '/'):
                shutil.copy2(dist.locate_file(path), licenses/(package+'-'+Path(path).name))
    report = ROOT/'reports'/(name+'-packaged-smoke.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    print('Checking packaged runtime without Python on PATH...', flush=True)
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['PATH'] = str(Path(os.environ['SystemRoot'])/'System32')
    test_command = [str(output/'OpenReunion.exe'), '--self-test', '--output', str(report),
                    '--content-dir', str(content_bundle)]
    subprocess.run(test_command,
                   cwd=work, env=env, check=True, timeout=120,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert json.loads(report.read_text())['passed']
    # The self-test log is diagnostic output, not a tester's session.
    log_path = output/'logs/launch.log'
    if log_path.exists():
        shutil.copy2(log_path, work/'packaged-launch.log')
        log_path.unlink()
        log_path.parent.rmdir()
    rows = []
    for forbidden in ('local/recovered', 'tester-saves', 'saves', 'reports'):
        if (output/forbidden).exists():raise ValueError('Original content or generated output in asset-free package: '+forbidden)
    for path in sorted(output.rglob('*')):
        if path.is_file():
            assert not path.is_symlink()
            data = path.read_bytes()
            rows.append({'path': path.relative_to(output).as_posix(), 'bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest()})
    manifest = {'version': version, 'package': name, 'platform': 'Windows x64',
                'python': sys.version, 'pyinstaller': distribution('pyinstaller').version,
                'supplied_player_saves_included': checkpoint_count > 0, 'optional_campaign_checkpoints': checkpoint_count,
                'original_content_included': False,
                'first_run_asset_import': True,
                'packaged_smoke': json.loads(report.read_text()), 'files': rows}
    (output/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(output.rglob('*')):
            if path.is_file():zipped.write(path, name+'/'+path.relative_to(output).as_posix())
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        for row in rows:
            assert hashlib.sha256(zipped.read(name+'/'+row['path'])).hexdigest() == row['sha256']
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT/'dist'/(name+'.sha256')).write_text(digest+'  '+archive.name+'\n')
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size,
                      'sha256': digest, 'files': len(rows)+1, 'packaged_smoke': str(report)}), flush=True)


if __name__ == '__main__':
    main()
