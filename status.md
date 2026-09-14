# Project status

Updated September 14, 2026. Current version: **0.38.0a8 (beta)**.

## Available now

- The campaign is playable from New Game through the ending.
- The graphical interface covers colonies, research, fleets, exploration, diplomacy, battles and story scenes.
- Setup imports assets from a supported original English installation.
- There are 23 optional campaign saves, including late-game battles and the ending.
- Source code and build tools are available here. No prebuilt Windows release has been published on GitHub yet.

## Checks

[Windows CI](https://github.com/scienceandresearch/open-reunion/actions/runs/34884688070)
passed on Python 3.11 and 3.14: 938 tests passed and six optional tests were
skipped on each version. CI also checks repository contents and checkpoint hashes.

Local checks loaded all 23 campaign saves and verified 2,593 converted asset
files. A Windows package completed a fresh asset import and passed its graphical
self-test, including time controls, save/load, battles and cinematic playback.

## Follow-up work

- Player reports on campaign branches, balance and long sessions.
- Further comparison of model shading, palettes and animation with the original.
- Investigate an intermittent Space-key assertion in the packaged graphical test.
  The same build and import passed on retry; the cause is still unresolved.
- Publish a Windows download with setup instructions and release notes.

Report bugs through [Issues](https://github.com/scienceandresearch/open-reunion/issues).
Include the game version, starting save and steps to reproduce the problem.
The [maintainer guide](HANDOFF.md) covers checks and packaging.
