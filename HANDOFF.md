# Maintenance handoff

This repository is the curated `opensource` project. Its earlier misspelled
folder was renamed; private development assets and history were moved out of
the repository before Git initialization. The original recreation was accepted
as complete, with future work driven by player feedback. Do not start another
full campaign replay for routine documentation or packaging changes.

## Where to work

- `src/openreunion/dos/session.py`: transactional campaign state and saves.
- `content.py`, `extraction.py`, `asset_import.py`, `import_ui.py`: original/local
  content adapters, conversion and responsive first-run setup.
- `original_ui.py` and screen modules: graphical game routes.
- `tests/`: synthetic regressions; six evidence-only checks skip in clean clones.
- `tools/`: curated build/import/checkpoint/repository validation tools.
- `tester-saves/`: reviewed optional campaign collection; personal saves go in
  ignored `saves/`. Historical original message logs have been removed.

## Validation and packaging

Run the README's unit suite, `tools/check_checkpoints.py`, and
`tools/audit_repository.py --staged` before pushing. The staged audit reads
Git's index. Keep third-party source and checkpoint bytes stable; .gitattributes
preserves their hashes across checkout. A modified guide requires updating its
manifest entry. `prepare_public_checkpoints.py` reproducibly removes only logs
from a separately supplied original checkpoint collection.

For local game validation, import your supported original copy and use
`tools/check_checkpoints.py --content local/recovered`. The public builder uses
`--content-bundle` only for local verification and always excludes it from output.
Use fresh archive/report names. `check_tester_archive.py --original-source ...`
verifies a real frozen import and graphical checks without Python on PATH.
Actual audio tests must be muted per process, not by changing system volume.

The initial GitHub source preparation ran 943 tests (937 pass, six optional
skips), validated all 23 cleaned checkpoints and the frozen asset-free runtime.
Detailed local reports and previous checkpoint originals remain with the
maintainer outside the repository; no raw research evidence is required for CI.

## Publishing and contact

Repository: https://github.com/scienceandresearch/open-reunion.

The owner requested a PRIVATE GitHub repository. Do not change its visibility
without explicit permission. Git commits use a GitHub noreply identity; do not
replace it with a personal email. The rights-holder issue template and README
invitation let people make initial contact via username when they have access.
Do not post confidential rights documentation in an issue or discussion.

Read docs/CONTENT-POLICY.md before adding files or attaching a release. Source
logic includes reconstructed presentation timing and is not clean-room code.
No claim is made that excluding media resolves all IP questions. Keep original
assets, converted bundles, screenshots, old tester ZIPs and private output out
of both Git history and release attachments.
