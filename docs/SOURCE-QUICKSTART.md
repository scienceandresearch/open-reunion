# Source and build guide

Use Python 3.11+ with Tcl/Tk. Windows is the supported target for native audio
and frozen packages. There are no Python runtime package dependencies for the
game engine. Running run.py directly avoids installing the project.

## First check

```powershell
python run.py --help
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
python tools/check_checkpoints.py
python tools/audit_repository.py
```

The tests use synthetic data. Optional private research checks may skip. Actual
play and visual/audio integration require your supported original game files.

## Audio and game setup

Install the pinned open-source Windows module decoder:

```powershell
python tools/install_module_audio.py
```

This downloads verified upstream dependency archives, not original game files.
The matching dependency source ZIP and license notices are included. Build FM
audio with a C compiler available on PATH, or provide its path:

```powershell
python tools/build_audio.py --compiler "C:\Tools\LLVM\bin\clang.exe"
```

The helper also accepts a Zig executable. Compiled libraries are local ignored
files, not committed source. THIRD_PARTY.md describes library replacement
variables and licensing. Without the optional libraries, full music playback
will be unavailable.

Import from the complete legally supplied original folder, then play:

```powershell
python run.py import-assets "C:\Games\Reunion" --output local/recovered --play
```

Import-Assets.cmd provides a folder picker and reuses an existing import on later
launches. The original executable alone is not sufficient; see ASSET-IMPORT.md.
The original SAVE/INIT template starts a fresh game without a personal save.
To load a checkpoint, use the in-game Disk Operations Load file control and
browse to tester-saves. Do not overwrite those files with personal continuations.

## Windows package

Prepare a local content import for verification and both native audio libraries.
Install packaging dependencies in your Python environment:

```powershell
python -m pip install pyinstaller pyinstaller-hooks-contrib
python tools/build_tester_package.py --content-bundle local/recovered --name Open-Reunion-Windows-UNIQUE
```

The public builder ALWAYS excludes the original asset bundle, includes the 23
reviewed checkpoints, and runs a muted frozen graphical check against your
local content. There is no asset-inclusive mode. The old --without-game-assets
flag remains accepted for command compatibility. Use a fresh package name.

Verify a fresh extraction and actual import into it:

```powershell
python tools/check_tester_archive.py dist/Open-Reunion-Windows-UNIQUE.zip --extract-to "local/package-check/Fresh Build" --original-source "C:\Games\Reunion" --output reports/fresh-build.json
```

The frozen test mutes its own audio session. Other native test drivers should be
launched through tools/run_quiet.py. Never change the user's global volume.

## Source ZIP and publication

```powershell
python tools/build_source_package.py --name Open-Reunion-Source-UNIQUE
python tools/audit_repository.py --staged
```

The source packager includes the audited public tree and checkpoint collection,
checks the upstream dependency archive, and excludes local/generated data.
The ZIP has a manifest and SHA256 companion. Audits of staged files read Git's
index, so an unstaged clean working copy cannot conceal an unsafe staged blob.
See CONTENT-POLICY.md for the limits of automated content checks.

GitHub Actions repeats the source audit, checkpoint validation and unit suite
on Windows/Python 3.11 and 3.14. It never imports or uploads original game assets.
Private local integration reports are intentionally absent from this repository.
