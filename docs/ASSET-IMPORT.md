# Open Reunion: import your original game

This Windows build contains the modern game and an offline importer. It does
not include the original game's artwork, music, sound effects, converted content
bundle or executable. The 23 optional modern campaign checkpoints are included. Supply your own legally obtained
copy of the original game. This distribution arrangement is not a legal opinion
or a claim that the project has permission from the original rights holders.

## First launch

1. Extract the entire Open Reunion ZIP to a writable folder, such as Documents.
2. Double-click **OpenReunion.exe** (or **Import-Assets.cmd**).
3. Click **Choose game folder and import...** and select your extracted original
   Reunion folder. Choose the folder containing **GRWAR**, **SAVE**, **GRAFIKA**,
   **INTRO**, **TEXT**, and the other original content folders.
4. Wait for **Import complete**, then click **Continue to game**.

Future launches go straight to the game. You do not need Python or DOSBox for
this Windows package. Importing makes no network requests and plays no audio.
Game audio behaves normally after you continue to the game.

The original game executable by itself is insufficient: most visuals and audio
live in separate files. Unpack any ZIP containing your original copy first.
The importer currently supports the three previously inspected English
288,992-byte `GRWAR/REUNION.PRG` builds and the original `SAVE/INIT` file.
Other releases, languages, installers and disk images are not yet supported.
Do not rename an unknown executable to force it through the version check.

## What happens to my files?

The importer reads the required files into a temporary working copy and converts
them locally. It never runs or patches the original executable, changes your
original installation, or imports your personal numbered DOS saves.
`SAVE/INIT` is the original New Game template, not a player save.

The complete result is installed under `local/recovered` beside OpenReunion.exe.
`IMPORT-MANIFEST.json` records the input and output file hashes. Personal game
saves remain separate under `saves`. Keep the whole Open Reunion folder together.
Once import succeeds, the original folder is no longer needed to run the port.

Failed imports are not installed. Existing destination folders are never
overwritten. If an older or incomplete `local/recovered` folder already exists,
preserve it by renaming it before retrying, or extract Open Reunion into a fresh
folder. Keep any player saves when moving between builds.

If files are missing, setup names the missing paths. Check that you selected
the full game folder rather than a parent folder, a shortcut or only GRWAR.
Unknown executable versions fail with an explanation instead of guessing their
data layout. Symbolic links/junctions inside the source copy are not supported;
use ordinary extracted files. File-name casing is normalized during import.

## Source checkout

With Python 3.11+ including Tk installed, double-click **Import-Assets.cmd**.
The source launch also requires the native audio libraries for full music;
see SOURCE-QUICKSTART.md. Alternatively, from the project folder:

```powershell
python run.py import-assets "C:\Games\Reunion" --output local/recovered --play
```

Omit `--play` to convert silently without starting the game. An executable path
can also be supplied if the rest of its installation is beside it; a
`GRWAR/REUNION.PRG` selection resolves to its containing game folder.

For automated Windows import without Python or a setup dialog:

```powershell
.\OpenReunion.exe --import-from "C:\Games\Reunion" --import-only
```

The older `recover-data` research command is retained and can import personal
saves unless `--no-saves` is specified. Use `import-assets` for player setup.

## Building a package without original assets

After preparing the native audio libraries and a local content import for
verification, run:

```powershell
python tools/build_tester_package.py --without-game-assets --content-bundle local/recovered --name Open-Reunion-Asset-Importer-UNIQUE
```

This mode uses the local bundle only for the muted graphical self-test. It
does not copy original content into the release. It includes the reviewed optional campaign saves. The
public builder always excludes original assets; the flag is retained only for
compatibility with older commands.

For a curated source ZIP with the checkpoint collection, use `tools/build_source_package.py`. Do not copy older private development artifacts into this source tree or
attach them to releases. Generated content
must stay out of repositories and release attachments, including repository
history if it was previously committed. The source ZIP's file selection is a
packaging safeguard, not a comprehensive review of copyright in source, text,
data, branding or reconstructed material. The MIT license does not relicense
original game material. Copyright and trademark questions remain separate.
