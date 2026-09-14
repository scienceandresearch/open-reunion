# Contributing

Start with README.md and the source quickstart. The repository contains a
playable fan recreation; fixes should preserve campaign and save compatibility
unless a deliberate change is documented. Keep changes small and explain the
player-visible behavior, relevant validation and remaining limits.

Run the unit suite, checkpoint check and repository audit described in README.
When changing a particular system, use meaningful synthetic regressions. Do not
add original executable chunks, decrypted dialogue, graphics, music, fonts,
converted data bundles, personal credentials or screenshots of original assets
as fixtures. Use generated data or load user-supplied assets only in local tests.

Generated files belong under local/, reports/, saves/, logs/ or dist/ and stay
out of Git. The reviewed tester-saves collection is an intentional exception
for modern campaign JSON, not permission to commit arbitrary original saves.
See docs/CONTENT-POLICY.md. Preserve its gameplay state and update the manifest
if changing its guide. Use tools/prepare_public_checkpoints.py when regenerating
a public collection from private campaign checkpoints.

The setup importer must remain offline, read-only toward originals, save-free
and transactional. Do not relax executable/version checks to accept an unknown
release. The public package builder must never copy the original asset bundle.

Use `python tools/run_quiet.py tools/<driver>.py ...` for local graphical/audio
checks. It mutes the test process while leaving the audio engine active; do not
change the user's global volume. Do not run lengthy campaigns for a doc-only
change. Record current status and meaningful evidence in status.md/HANDOFF.md.

Before pushing, review `git diff --cached` and run
`python tools/audit_repository.py --staged`. The audit is a technical guard, not
a legal determination. Check release attachments separately. A new asset file
or copied text requires rights review even if it passes an automated scan.
