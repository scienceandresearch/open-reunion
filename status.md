# Project status

Updated 2026-09-14. The working folder is now `opensource`. This tree is the
curated GitHub repository; historical research, original-derived output and
older private builds are preserved outside it.

## Current state

- Playable beta, game version 0.38.0a8, with the original accepted unassisted
  graphical New Game-to-victory route. Broader player feedback is still needed.
- Offline first-run asset importer; the complete supported original English
  installation is required. Original game files are not shipped in the repo.
- 23 optional checkpoints included. Only their historical logs were cleared;
  every other gameplay field matches the tested originals. Provenance and file
  hashes are recorded in tester-saves/MANIFEST.json.
- Public Windows builder always excludes original assets and includes the
  reviewed checkpoints. Source ZIP builder uses the audited public tree.
- GitHub Actions: source audit, checkpoint validation and synthetic tests on
  Windows with Python 3.11 and 3.14. No original assets are used by CI.
- Fan-project README, setup/build guides, agent setup prompt and rights-holder
  invitation are included. Issues/Discussions provide username-based contact;
  no maintainer email is published by this repository.

## Verification

943 source tests run: 937 passed and six expected private-evidence skips.
All 23 sanitized checkpoints load against the accepted imported catalog.
The importer previously reproduced 2,593 converted files byte for byte; the
folder rename preserves that pipeline. Asset-free Windows r2 with checkpoints
passes the frozen graphical self-test. Repository guard tests cover original
media, private paths, disguised binary data, unapproved archives and staged
blobs that differ from their working copies.

The technical content audit covers file selection, known asset payloads,
embedded-data review, checkpoint logs and the pinned licensed dependency ZIP.
It is not legal clearance for reconstructed presentation code or branding;
see docs/CONTENT-POLICY.md. The repository must remain private until the owner
explicitly decides otherwise. No request to contact original rights holders
has been made on the owner's behalf.

See HANDOFF.md for maintenance commands and README.md for setup.
