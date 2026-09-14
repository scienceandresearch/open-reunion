# Tested scope

Open Reunion is a playable beta fan recreation, not a claim of exact original
parity. The accepted development campaign reached victory from a fresh New Game
through an automated, unassisted graphical route. That route used real resource
costs, casualties and Save/Load. Other branches and player behavior still need
feedback.

The current source suite uses synthetic fixtures; a few private-evidence checks
skip in a clean checkout. The local importer reproduced all 2,593 files in the
accepted converted bundle byte for byte. Setup cancellation/retry/responsiveness
and a fresh Windows import without Python on PATH passed. Frozen graphical
checks covered startup, time, save/load, interface routes and ending assets with
audio muted per process.

The GitHub preparation preserves gameplay and adds content-exclusion checks,
clean source packaging and 23 checkpoints whose historical event logs have
been cleared. Checkpoint gameplay fields match the original tested collection.
See status.md for current verification and version details.

Original files are needed only for local integration, rendering/audio checks
and actual play. Never attach their contents to CI artifacts or releases.
The public Windows builder uses a local bundle for validation but excludes it
from the output. It includes dependency notices and the reviewed checkpoint pack.

Use TESTER-FEEDBACK.md or the repository issue template for reproducible bugs.
State which checkpoint or New Game start you used and whether admin was enabled.
