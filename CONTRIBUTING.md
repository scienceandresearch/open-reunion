# Contributing

Bug reports, fixes and help with testing are welcome. Start with the
[README](README.md) and [source guide](docs/SOURCE-QUICKSTART.md).

For a bug report, include the version, starting save, game date, steps to
reproduce it, and what you expected to happen. Mention any admin commands used.
The [feedback template](TESTER-FEEDBACK.md) has more detail.

## Code changes

Keep changes focused and explain how they affect the player. Preserve existing
campaigns and save compatibility where possible. Add regression coverage for
bugs using generated test data.

Run the [unit suite and content checks](README.md#development). Before pushing,
review `git diff --cached` and run `python tools/audit_repository.py --staged`.
Use original files only for local integration tests; they aren't needed for CI.
For graphical tests with audio, use `tools/run_quiet.py` to mute the test process.

## Files and assets

Don't commit original executables, dialogue, graphics, music, converted bundles
or screenshots of game assets. Use the ignored `local/`, `reports/`, `saves/`,
`logs/` and `dist/` folders for generated files.

The included `tester-saves` collection has had its message logs removed. Keep
its manifest up to date when editing the guide or replacing a checkpoint.
`tools/prepare_public_checkpoints.py` handles log removal when preparing a new
collection. See [content and rights](docs/CONTENT-POLICY.md) before adding data
or attaching files to a release.

The importer must leave original files untouched, work offline and check the
supported version before converting. Support for another release needs its
own format checks; don't bypass validation to make it load.

See the [maintainer guide](HANDOFF.md) for the code map and packaging workflow.
