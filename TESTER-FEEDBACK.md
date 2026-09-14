# Open Reunion tester feedback

- **Candidate name:** [release name or Git commit]
- **Archive SHA256:** see the companion `.sha256` file beside the ZIP
- **Runtime path:** portable `OpenReunion.exe` / source `Launch-Original.cmd`
- **Windows version:**
- **Screen and window size / fullscreen:**
- **Game date/time:**
- **Started a new game or imported a DOS save?**
- **Optional feedback save used?** Yes / No (filename if yes)
- **Admin used in this session?** Yes / No

## What to report

Describe the screen, exact clicks/keys, expected result, actual result and
frequency. For the startup intro, identify whether the report concerns **Play
intro**, the first transition, **Space** pause/resume, **Replay**, **Back /
Escape**, or a later film. Say whether the campaign state/date stayed the same
after replay or abort and whether music stopped and resumed as expected.

The candidate includes the original graphical routes and integrated intro.
The automated graphical campaign has reached victory; independent player
feedback is needed on progression, usability and remaining defects.

## Steps to reproduce

1.
2.
3.

## Expected result


## Actual result


## How often does it happen?

Always / Sometimes / Once

## Saves and attachments

Before a reproducible issue, use a visible numbered Disk Operations slot or
**Save file...** for a named JSON save. Loading leaves campaign time paused.
Closing normally writes `saves/recovered-autosave.json`; a named save made
before the issue is more useful than autosave alone.

Attach the relevant `.json` save and a screenshot when useful. Attach
`logs/launch.log` for startup failures, crashes, audio/callback errors or
cleanup problems. Include the companion archive SHA256, screen/window details
and exact reproduction steps.

## Optional admin

F2 opens the optional **Admin & log** panel; opening it alone does not alter
the session. Applying a valid admin command marks the session assisted. Leave
admin disabled for ordinary balance testing. If used, record the commands and
identify any imported DOS save.

## Known boundaries

Broad adverse-choice, concurrent-event and long-session Save/Load testing,
plus independent Windows/player feedback, remain final-release work after the
verified candidate is shared. Cosmetic differences in model shading, map
motion, palettes and ambient transitions may also remain.

A7 focus: try middle-click maximum, Shift-middle reverse, wheel adjustments and
Shift-click alternatives on equipment, cargo and ground troop counts. Report
screen, hovered counter, modifier/button, stock before/after and expected amount.

A8 focus: incoming battle notice names the attacker and planet, remains visible
over hover/Save/Load, and starts paused. Include your save if identity seems wrong.

When using Optional Saves, include the exact numbered checkpoint filename and
your new continuation save. Its START-HERE.md describes the expected entry state.
