# Setup prompt for a coding agent

Copy the prompt below into an agent that has access to this repository and your
computer. Provide the path to your legally obtained original Reunion folder.
The agent needs normal filesystem/terminal access and may need permission to
install Python or download the open-source audio dependencies. This repository
does not contain a ready-to-run original game installation.

---

Help me set up and run Open Reunion from this checkout. Read README.md,
CONTRIBUTING.md, docs/ASSET-IMPORT.md and docs/SOURCE-QUICKSTART.md first.

My original Reunion game folder is: [INSERT FULL LOCAL FOLDER PATH].

1. Inspect the OS and available Python. Use Python 3.11+ with Tcl/Tk. Windows is
   the supported platform for native audio. Work inside this checkout; preserve
   existing files and saves. Ask for missing original-folder information rather
   than searching for or downloading the copyrighted game files.
2. Check `python run.py --help`. No Python package dependencies are needed for
   the game engine. For full audio, run tools/install_module_audio.py to obtain
   the pinned open-source module decoder, and build the FM bridge with
   tools/build_audio.py using an available C compiler. Ask before any installation
   for which you lack authorization. Do not download an unverified DLL.
3. Validate the complete supplied original folder. It must include the supported
   GRWAR/REUNION.PRG, SAVE/INIT and the separate asset directories. Do not execute
   the original program, patch version checks, alter the originals, or import
   personal DOS saves as part of asset setup.
4. If local/recovered already holds a working import, reuse it. Otherwise run
   `python run.py import-assets "ORIGINAL_FOLDER" --output local/recovered`.
   If an existing destination is incomplete, preserve it and use a fresh path.
   Report unsupported versions or missing files clearly; do not guess offsets.
5. Set PYTHONPATH to src and run the source unit suite. Run
   `python tools/check_checkpoints.py --content local/recovered` and
   `python tools/audit_repository.py`. Keep generated content ignored and do not
   stage, upload or redistribute any original files or converted bundles.
6. Launch `python run.py recover local/recovered --original-ui` when I am ready
   to play. During automated testing keep audio muted per process using the
   project's quiet-test tools; never change my global volume. Explain Space for
   time, Disk Operations for saves, the optional F2 admin console, and the
   tester-saves catalog. Checkpoints need the imported assets too.
7. Summarize the exact launch command, installed dependencies, saved-data
   locations, tests run and anything unresolved. Do not claim all branches or
   original fidelity are proven merely because setup succeeds. Do not publish
   this repository or change its visibility without my explicit instruction.

---
