# Open Reunion

An unofficial, AI-assisted fan recreation of **Reunion (1994)**, also known as
**Merit's Galactic Reunion**, implemented in Python.

This project began with a childhood memory: spending hours playing Reunion with
a friend, never reaching the ending, and returning every few years to try again.
After repeated difficulties getting the old game running reliably, rebuilding
it became a way to revisit that experience and finally finish the campaign.
AI made it possible to take on a project that otherwise would have been out of
reach. The aim is to preserve the game we remember and make it easier to play
on a modern computer, with a few practical improvements along the way.

This is a fan project, not an official release or an endorsed continuation.
The original developers and artists created the world, story, imagery and music
that make Reunion memorable. This repository contains the new implementation,
local import tools, tests and optional campaign checkpoints. **It does not
include the original game executable, artwork, music or converted asset bundle.**
The implementation was reconstructed from original behavior, executable/data
analysis and documented progression; it is not a clean-room implementation.

## What works

The graphical game connects New Game, colonies, economy, research, production,
exploration, diplomacy, fleets, cargo, equipment, space and ground battles,
story sequences, save/load and the ending. An automated unassisted graphical
campaign has completed a fresh game through victory. That verifies one full
route; it does not establish perfect original parity or eliminate every bug.
This remains a playable beta, and player feedback is welcome.

Quality-of-life additions include resource assistance through an optional admin
console, time controls, named saves, clearer attack notices, and faster quantity
adjustments. Admin changes mark a campaign as assisted. The optional checkpoint
collection provides another way to explore later parts of the game.

## Play

### Windows package

If a Windows build is provided under this repository's Releases, extract its
entire ZIP and run **OpenReunion.exe**. On first launch, choose your complete
original English Reunion folder, wait for import and click **Continue to game**.
Python and DOSBox do not need to be installed for the packaged build. No
downloaded release is required to run from source below.

### Run from source

Use Python **3.11 or newer with Tcl/Tk**. Windows is the supported platform for
live native audio. From the repository folder:

```powershell
python run.py --help
python tools/install_module_audio.py
python tools/build_audio.py --compiler "C:\Tools\LLVM\bin\clang.exe"
python run.py import-assets "C:\Games\Reunion" --output local/recovered --play
```

The module installer downloads only a pinned open-source audio dependency.
The FM build command needs a C compiler; the helper also supports Zig and can
discover `cc` or `clang` on PATH. The game can start without these optional
libraries, but full music playback requires them. The Windows package already
contains the libraries and their notices.

For a guided folder picker, double-click **Import-Assets.cmd** instead of the
last command. After setup, use that launcher again or:

```powershell
python run.py recover local/recovered --original-ui
```

See [quickstart](QUICKSTART.md), [asset import details](docs/ASSET-IMPORT.md) and
the [player guide](PLAYER-GUIDE.md). **Space** starts/pauses time. **F2** opens
the optional admin console. Personal saves live under `saves/`, separate from
the included checkpoints.

## Original files

You must supply a legally obtained, complete original game folder. The game
executable alone is insufficient: graphics, animations, text and sound live in
other files. The importer supports the three English executable builds already
inspected by this project, with a 288,992-byte `GRWAR/REUNION.PRG` and the original
`SAVE/INIT`. Other versions and languages require additional analysis.

If you cannot read your original media, copies may be listed on various sites
described as abandonware archives. “Abandonware” is not a license or proof of
permission to download or use a copy. Check the rights and terms that apply to
you. This project does not host, link to or download original game files.

Importing happens locally, never executes the original program, and leaves the
original files untouched. Imported assets stay under ignored `local/` paths and
must not be committed or attached to releases. See [content and rights notes](docs/CONTENT-POLICY.md).

## Jump into the campaign

The [23 optional checkpoints](tester-saves/START-HERE.md) cover the opening,
colony expansion, first contact, Morgrul and League campaigns, Earth and victory.
Their names and guide contain spoilers. Import the original assets first, then
use **More Icons > Disk Operations > Load file...** to browse to `tester-saves/`
(or **Optional Saves** in a Windows package).

These are earned checkpoints from one unassisted automated campaign. Their
gameplay state is preserved; historical message logs were cleared for this
source distribution. They are not invincible armies, and later outcomes depend
on your decisions. Save your own continuation under a new name.

## Let an agent help

Give a coding agent [this setup prompt](docs/AGENT-SETUP-PROMPT.md). It describes
how to inspect the environment, install dependencies, import your local copy,
validate the setup and launch the game without obtaining original files for you.

## Development and testing

No original game assets are needed for the unit suite:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
python tools/check_checkpoints.py
python tools/audit_repository.py
```

Optional checks that need private research evidence may skip. After importing
content, verify the checkpoint collection against it with:

```powershell
python tools/check_checkpoints.py --content local/recovered
```

The main implementation is under `src/openreunion/dos/`; `session.py` manages
campaign transactions, `content.py` adapts original/imported data, and
`original_ui.py` connects the graphical screens. Synthetic regressions live in
`tests/`. Build and validation helpers live in `tools/`.

See [contributing](CONTRIBUTING.md), [build instructions](docs/SOURCE-QUICKSTART.md)
and [tested scope](TEST-BUILD.md). GitHub Actions runs the source checks without
original files. The package builder always excludes original content and
includes the optional checkpoint collection.

## Credits and license

### A note to the rights holder

If you hold rights to Reunion and would be comfortable allowing the original
assets to be included with this fan project, I would sincerely welcome hearing
from you. Being able to offer an authorized, simpler way to revisit the game
would mean a great deal. No such permission is assumed at present.

Please open a **Rights and permissions** issue through this repository's Issues
tab, or start a Discussion and mention **@scienceandresearch**. There is no need
to publish an email address. These are public conversations when the repository
is public; please do not post contracts, identity documents or other confidential
material. We can agree on a suitable private channel if needed. While the
repository is private, these features are available only to invited users.

Reunion was created by Amnesty Design, later known as Digital Reality, and
published by Grandslam. All original game rights remain with their respective
holders. The new implementation is offered under [MIT](LICENSE), with separately
licensed audio components documented in [THIRD_PARTY.md](THIRD_PARTY.md).
Neither that license nor local asset extraction establishes permission for all
uses of the original game's intellectual property or branding.
