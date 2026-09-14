# Set up Open Reunion with a coding agent

Copy the prompt below into a coding agent with access to your computer. Replace
the folder placeholder with the location of your original Reunion files.

---

Help me install and run Open Reunion from this checkout. Read README.md,
docs/ASSET-IMPORT.md and docs/SOURCE-QUICKSTART.md before starting.

My original Reunion folder is: **[INSERT FULL FOLDER PATH]**.

1. Check for Python 3.11 or newer with Tcl/Tk. Windows supports the full native
   audio setup. Preserve any existing imports and saves.
2. Set up the audio libraries using tools/install_module_audio.py and
   tools/build_audio.py. Find an available C compiler or help me install one.
   Use the project's pinned dependencies.
3. Import my original files with
   `python run.py import-assets "ORIGINAL_FOLDER" --output local/recovered`.
   Reuse an existing working import. If it is incomplete, keep it and use a fresh
   destination. Don't download the original game, change my original files or
   bypass the importer's version checks.
4. Run the unit suite and check the campaign saves with
   `python tools/check_checkpoints.py --content local/recovered`.
   Keep imported assets and test output out of Git. Mute any audio tests using
   the project's per-process controls.
5. Launch `python run.py recover local/recovered --original-ui` when I'm ready.
   Show me how to start and pause time, save my progress, load a checkpoint and
   open the optional admin console.
6. Tell me how to launch the game next time, where my saves are stored and
   whether anything still needs attention.

---
