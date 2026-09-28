# Open Reunion

A fan-made recreation of **Reunion (1994)**, also known as **Merit's Galactic Reunion**, written in Python for modern computers.

I grew up playing Reunion with a friend. We spent hours on it but never managed to beat it. Every few years I'd come back and try again, usually spending as much time getting it to run as I did playing it. Eventually I decided to rebuild it, with help from AI, so I could finally finish the game.

Open Reunion keeps the original game's look and core gameplay, with some small improvements to make it easier to play. You can play the campaign from New Game through the ending: build colonies, research technology, explore other systems, negotiate with alien civilizations, and fight in space and on the ground. It's still a beta, and I'd love to hear how it plays for you.

**You'll need your own copy of the original English game.** This repository includes the new engine and an importer, but no original artwork, music, sound effects or game executable.

## Getting started

The repository contains the source code. **There is no prebuilt Windows download on GitHub yet.** You can run the game from source using the steps below, or [build a Windows package](docs/SOURCE-QUICKSTART.md#build-a-windows-package).

You'll need Python **3.11 or newer with Tcl/Tk**. Windows is the tested platform; the bundled module-audio installer requires 64-bit Python on Windows. macOS and Linux are not yet verified for full gameplay and audio. See the [Python setup check](docs/SOURCE-QUICKSTART.md#check-your-setup) before starting.

Clone the repository, or use **Code > Download ZIP** and extract it:

```powershell
git clone https://github.com/scienceandresearch/open-reunion.git
cd open-reunion
```

If you downloaded the ZIP, open the extracted folder containing `run.py`. Open PowerShell in that folder (right-click in the folder and choose **Open in Terminal**). Run all commands below from there. Git is only needed for the clone command.

For full music playback, install the audio libraries. The second command needs `clang` or `cc` on your PATH:

```powershell
python tools/install_module_audio.py
python tools/build_audio.py
```

See the [source guide](docs/SOURCE-QUICKSTART.md#audio) if you need to specify a compiler. You can start the game without these libraries, but some music will be missing.

Double-click **Import-Assets.cmd** and choose your original Reunion folder. Wait for the import to finish, then click **Continue to game**. You can also start it from the terminal, replacing the example path with your own:

```powershell
python run.py import-assets "C:\Games\Reunion" --output local/recovered --play
```

After setup, double-click **Launch.cmd** (or **Import-Assets.cmd**) again, or run:

```powershell
python run.py recover local/recovered --original-ui
```

Choose **New Game** and your character. Time starts paused: press **Space** to begin. The [quickstart](QUICKSTART.md) covers the basics, and the [player guide](PLAYER-GUIDE.md) explains the controls in detail.

## Your original game files

Choose the complete, extracted English game folder, including `GRWAR`, `SAVE`, `GRAFIKA`, `INTRO`, `TEXT` and the other asset folders. The executable alone isn't enough. The [import guide](docs/ASSET-IMPORT.md) lists supported versions and explains common setup problems.

The importer works locally and leaves your original files untouched. It doesn't run the DOS program or copy your old player saves. Once setup is complete, the converted files stay in `local/recovered`.

If you can no longer read your original media, copies can be found at various abandonware archives. That label doesn't mean the game is freely licensed; make sure you have permission to use the copy you obtain. This project doesn't supply or download the original files.

## A few conveniences

- **Time controls:** start, pause and change speed below the game window.
- **Named saves:** use **More Icons > Disk Operations > Save file...** to save your progress.
- **Faster loading and equipment assignment:** use the mouse wheel to adjust quantities or middle-click for the maximum.
- **Admin console:** press **F2** to add money or resources when you want a helping hand. Using an admin command marks that save as assisted.

## Pick up partway through

The repository includes [23 campaign saves](tester-saves/START-HERE.md), from the opening colony to the final battle and victory film. Their names tell you what to expect, and the guide suggests what to do next. Expect spoilers.

Import the game assets first, then open **More Icons > Disk Operations > Load file...** and choose a save from `tester-saves`. Save your continuation under a new name. These checkpoints were played without resource assistance; their old message logs have been cleared, but their gameplay state is intact.

## Help with setup

If you'd rather have a coding agent handle installation, give it [this setup prompt](docs/AGENT-SETUP-PROMPT.md) and the path to your original game folder.

For bugs, open an [issue](https://github.com/scienceandresearch/open-reunion/issues) with the version, the steps that led to the problem, and whether you started a new game or loaded a checkpoint. General feedback is welcome in [Discussions](https://github.com/scienceandresearch/open-reunion/discussions).

## Development

The engine lives in `src/openreunion/dos/`, tests in `tests/`, and build tools in `tools/`. To run the checks:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
python tools/check_checkpoints.py
python tools/audit_repository.py
```

These checks don't need the original game files. See [contributing](CONTRIBUTING.md), the [build guide](docs/SOURCE-QUICKSTART.md), and the [project status](status.md) for more.

## Credits and permissions

Reunion was created by Amnesty Design, later known as Digital Reality, and published by Grandslam. This is an unofficial fan project, with no affiliation or endorsement from the original creators or rights holders.

The new code is available under the [MIT license](LICENSE). Audio dependencies have their own licenses, listed in [THIRD_PARTY.md](THIRD_PARTY.md). The original game's assets and other rights remain with their respective owners. See [content and rights](docs/CONTENT-POLICY.md) for details about the reconstruction and what's included here.

**To the rights holder:** if you'd be open to allowing the original assets to be distributed with this project, I'd be very glad to hear from you. It would make revisiting the game much simpler. Please open a **Rights and permissions** issue or start a Discussion and mention **@scienceandresearch**. No email address is needed for initial contact; we can arrange a private follow-up for any confidential details.
