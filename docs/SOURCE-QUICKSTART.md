# Source and build guide

Use Python 3.11 or newer with Tcl/Tk. The game engine has no Python package
dependencies; you can run `run.py` directly. Windows supports the native audio
libraries and packaged executable.

## Check your setup

Install Python from [python.org](https://www.python.org/downloads/windows/). On Windows, use the 64-bit version for the audio decoder and include Tcl/Tk. Make sure `python` is available in your terminal, then reopen the terminal after installation.

From the repository folder, check Python and its graphical toolkit:

```powershell
python --version
python -m tkinter
```

The second command should open a small test window; close it before continuing. If `python` is not recognized or opens the Microsoft Store, fix your Python installation/PATH first. If `tkinter` is missing, install Python with Tcl/Tk support. No `pip install` step is needed to play from source.

Then check the project:

```powershell
python run.py --help
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
python tools/check_checkpoints.py
python tools/audit_repository.py
```

The unit tests use generated data. Six optional tests skip when their additional
test files aren't available. Playing the game requires your original assets.

## Audio

Install the module decoder using 64-bit Python on Windows:

```powershell
python tools/install_module_audio.py
```

This downloads the pinned open-source audio dependency. Its source archive and
license notices are included in the repository.

For FM music, install a C compiler and put `clang` or `cc` on PATH, then run:

```powershell
python tools/build_audio.py
```

You can also pass a compiler path explicitly. Replace this example with yours:

```powershell
python tools/build_audio.py --compiler "C:\Tools\LLVM\bin\clang.exe"
```

The helper also accepts the path to a Zig executable. Built libraries go in
`local/native`. See [THIRD_PARTY.md](../THIRD_PARTY.md) for dependency versions,
licenses and library replacement options.

## Import and play

Double-click **Import-Assets.cmd** to choose your original game folder, or run:

```powershell
python run.py import-assets "C:\Games\Reunion" --output local/recovered --play
```

Replace the example path with your own. The original executable alone isn't
enough; see the [import guide](ASSET-IMPORT.md) for the required files.

For later launches, double-click **Launch.cmd** or **Import-Assets.cmd**, or run:

```powershell
python run.py recover local/recovered --original-ui
```

## Build a Windows package

There is no prebuilt Windows release on GitHub yet. To build one, first prepare
both audio libraries and a working import in `local/recovered`. Then install
the packaging tools and run the builder:

```powershell
python -m pip install pyinstaller pyinstaller-hooks-contrib
python tools/build_tester_package.py --content-bundle local/recovered --name Open-Reunion-Windows-r1
```

The ZIP is written to `dist/`. It includes Python, the audio libraries and 23
campaign checkpoints. Original game assets are used for the build's graphical
test but aren't copied into the package. Each player imports their own files
on first launch. The packaged game doesn't require a separate Python or DOSBox
installation.

Choose a new build name each time to preserve earlier output. To test a fresh
extraction and import, replace the original-folder path below:

```powershell
python tools/check_tester_archive.py dist/Open-Reunion-Windows-r1.zip --extract-to "local/package-check/Fresh Build" --original-source "C:\Games\Reunion" --output reports/fresh-build.json
```

The packaged self-test mutes its own audio session. Other graphical test scripts
can run through `tools/run_quiet.py` without changing system volume.

## Build a source ZIP

```powershell
python tools/build_source_package.py --name Open-Reunion-Source-r1
```

The source ZIP contains the code, documentation, dependencies and checkpoints,
with a file manifest and SHA256 checksum. It excludes imported assets and
other generated files.

Before publishing source changes, review the staged files and run:

```powershell
python tools/audit_repository.py --staged
```

GitHub Actions repeats the source audit, checkpoint validation and unit suite
on Windows with Python 3.11 and 3.14. Review release attachments separately;
see [content and rights](CONTENT-POLICY.md).

## Developer launch modes

All root-level `.cmd` launchers open the player import/game flow. For the older
prototype, use `python run.py play`. For the diagnostic recovered-data interface,
use `python run.py recover local/recovered` without `--original-ui`.
