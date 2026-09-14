# Importing your original game

Open Reunion needs artwork, sound, music and game data from your own copy of
Reunion. The importer converts those files locally and leaves the originals
untouched. It doesn't download game files or run the DOS program.

## Start the import

From a source checkout, install Python 3.11+ with Tcl/Tk and double-click
**Import-Assets.cmd**. See the [source guide](SOURCE-QUICKSTART.md) for audio setup.
If you've built a Windows package, run **OpenReunion.exe** instead.

1. Click **Choose game folder and import...**.
2. Select the complete, extracted original game folder. It should contain
   **GRWAR**, **SAVE**, **GRAFIKA**, **INTRO**, **TEXT** and the other asset folders.
3. Wait for **Import complete**, then click **Continue to game**.

Later launches reuse the imported files. The original executable alone isn't
enough; most graphics and audio are stored separately. Unpack your original
copy if it is still in a ZIP.

## Supported copies

The importer recognizes three English builds with a 288,992-byte
`GRWAR/REUNION.PRG` and the original `SAVE/INIT` file. Other versions, languages,
installers and disk images aren't supported yet. Setup checks file hashes and
reports an unsupported version rather than trying to read the wrong layout.

## Files and saves

Converted assets are stored in `local/recovered` inside the Open Reunion folder.
`IMPORT-MANIFEST.json` records file hashes. The importer reads `SAVE/INIT` to
create new games, but doesn't import personal DOS saves.

Your Open Reunion saves go in `saves/`. The optional campaign checkpoints are
in `tester-saves/` in source checkouts and **Optional Saves** in Windows packages.
Keep your own saves under new names.

Once import succeeds, Open Reunion uses the converted files and no longer needs
the original folder for play. Keep the Open Reunion folder together when moving it.

## Troubleshooting

If setup reports missing files, check that you selected the game folder itself,
not a parent folder or just `GRWAR`. Use ordinary extracted files; symbolic links
and junctions inside the original copy aren't supported. File-name casing is
normalized during import.

A failed import isn't installed, and an existing destination isn't overwritten.
If `local/recovered` contains an incomplete import, rename that folder before
retrying. Keep any saves when moving between installations.

## Terminal commands

From source, replace the example path with your game folder:

```powershell
python run.py import-assets "C:\Games\Reunion" --output local/recovered --play
```

Leave off `--play` to import without launching. In a built Windows package:

```powershell
.\OpenReunion.exe --import-from "C:\Games\Reunion" --import-only
```

Use `import-assets` for player setup. The older `recover-data` research command
can also import personal DOS saves unless `--no-saves` is specified.

For packaging, see the [build guide](SOURCE-QUICKSTART.md). Imported assets belong
in local storage, not Git or release attachments; see [content and rights](CONTENT-POLICY.md).
