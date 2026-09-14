# Maintainer guide

Use this guide to find the main systems, check a change, or prepare a build.
For installation, start with [README.md](README.md). Current test results and
known issues are in [status.md](status.md).

## Code map

Most game code lives in `src/openreunion/dos/`:

- `session.py` manages campaign state, actions and saved games.
- `content.py` reads original files and converted assets.
- `extraction.py` and `asset_import.py` handle conversion; `import_ui.py` provides the setup window.
- `original_ui.py` connects the graphical screens and their controls.
- `tests/` contains regression tests; `tools/` contains build and validation scripts.
- `tester-saves/` holds the campaign checkpoints. Player saves go in the ignored `saves/` folder.

## Checking changes

Run the [source checks](README.md#development) and any integration checks relevant
to the change. Tests that need original files are separate from the unit suite.
With an imported game, check that the campaign saves load:

```powershell
python tools/check_checkpoints.py --content local/recovered
```

Before committing, review the staged changes and run:

```powershell
git diff --cached
python tools/audit_repository.py --staged
```

The audit reads the Git index. It checks file types, asset exclusions, dependency
hashes and checkpoint contents. Review release attachments separately.

## Saves and dependencies

Checkpoint files and third-party source files have hashes recorded in their
manifests. `.gitattributes` preserves their bytes across platforms. If you edit
the checkpoint guide, update its entry in `tester-saves/MANIFEST.json`.

`tools/prepare_public_checkpoints.py` creates a distributable collection from
an original checkpoint collection by clearing message logs. It preserves all
other gameplay fields. Keep save-format changes compatible with existing saves
where possible, and document any migration.

## Packaging

Follow the [build guide](docs/SOURCE-QUICKSTART.md). The Windows builder uses
`--content-bundle` for testing and leaves those assets out of the ZIP. It bundles
the runtime, audio libraries and optional checkpoints. Use a new name for each
build so earlier archives and reports remain available.

`tools/check_tester_archive.py --original-source ...` checks a fresh extraction,
imports a local original copy and tests the packaged game without Python on PATH.
Its audio is muted for the test process. Other graphical test scripts can run
through `tools/run_quiet.py` without changing system volume.

Keep original files, converted assets and integration-test output out of Git
and release attachments. See [content and rights](docs/CONTENT-POLICY.md).
