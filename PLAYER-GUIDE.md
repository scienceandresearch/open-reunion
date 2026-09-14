# Open Reunion player guide

This is the detailed control reference for the
**Open Reunion 0.38.0a8 fan recreation**. The short entry guide is
[QUICKSTART.md](QUICKSTART.md).

Import your original game files before playing. See the
[setup instructions](README.md#getting-started) if this is your first launch.

## Controls

Landing discoveries now open their story automatically after the landing
animation and sound finish. Satellite discoveries also open their story.
Use **Continue** on the notice, then watch or resume the scene to return to play.

The cockpit's **Move / Change destination** lever now moves before opening
the map. Choose a destination there, or use **Abort Move** to return without
changing the journey. Back, Load and F10 cancel an unfinished lever action.

In a fleet's **Control Panel**, the left **Launch / Dock** lever now plays
the original cockpit transition, white fades and sound. Campaign time pauses
during the brief sequence; wait for it to finish before the next cockpit action.
The sound can continue briefly after movement finishes. Back, Load or F10
ends playback safely. Launching/landing still requires a valid equipped fleet
and suitable destination.

On the research screen, **Pause research / Resume research** below the picture
stops or resumes research while campaign time can continue. The selected
active project displays **Paused by player** when this setting is enabled.
It is saved with the game; use **Resume research** after loading a paused save.
Hiring/training requirements and story-related research blocks still apply.

In **Disk Operations**, the **I / II** buttons select main music, the square
button stops main music, and **E** toggles effects. Settings survive Save/Load.
Special-scene music still plays with main music stopped.
The original CD tray animates when changing main music; let it finish before
choosing another sound button. Campaign time pauses in Disk Operations.

To save, select one of the **twelve rows** and click the original **Save**
icon above the picture. Occupied slots show their game date; replacing one
requires confirmation. To restore it, select the row and click **Load**.
Successful slot saves/loads return to the control room. **Save file...** and
**Load file...** below the picture let you use named JSON files, including
the optional campaign checkpoints.

Original **Game Credits** is available through **Disk Operations** in the
control-room icons. **Space** pauses/resumes; **Replay** restarts the film;
**Back / Escape** returns to play. Campaign time stays paused.

## Start

1. From source, double-click **Import-Assets.cmd**. In a built Windows package,
   run **OpenReunion.exe**.
2. On first launch, choose your original game folder, wait for import, then
   click **Continue to game**.
3. Click **NEW GAME**, choose the female hero on the left or male hero on the
   right, then click the portrait (or Enter). No previous save is required.
4. You enter the control room with 120,000 credits at 2927/08/13/23.
   **Time starts paused.** Click **Run (Space)** below the game, or press
   **Space**, to begin.

Source checkouts require Python 3.11+ with Tk. Built Windows packages include
the runtime, but both need assets imported from your original game. See the
[build guide](docs/SOURCE-QUICKSTART.md) to create a Windows package.

Escape goes back during hero selection; **Main menu** below the game
opens these choices during play. **F10** also opens the menu during a
conversation or battle. The previous game is backed up before reset.
**LOAD GAME** opens your saved session. Hero choice persists across Save/Load.

Map attacks now use original icons. Select an alien
fleet in the orbital panel and click **Attack** for space combat. Select your
Army at a surveyed, non-allied alien world and click **Assault** for the
space/ground sequence. Attacks require a fighter commander; assault requires
rank 2 or 3. Space battles now stay in the main game screen. Use **Run (Space)**
or **Step** below the picture; use the original **Retreat** or **Continue** icon
above it. Save/Load remains available below the picture. Escape pauses combat;
campaign time stays paused throughout the battle. Ground deployment, combat
and results also stay in the main screen.

On ground deployment, click a group icon to remove it; left/right-click its
count to add/subtract one. The class icons add groups from reserve.
**CANCEL ATTACK** returns an attacker to the map before ground combat,
preserving troops and any prior space losses. Defenders cannot cancel.
**OK, ATTACK** begins ground combat. Select a friendly group, click **Move**
(or press **M**) and click its destination. Use **Attack** (or **A**) and click
an enemy group to target it. Right-click cancels targeting. **Run (Space)**
starts/pauses combat; **Step** advances one combat step. Escape pauses combat
and cancels targeting. Save/Load keeps the current battle and orders.
After retreat or resolution, use the original **Continue** icon to return to
play. Ground defeat animation can be paused separately below the picture.

Story cinematics and notices
now stay in the main screen. Use **P** or **Play/Pause** below the picture;
**Space** supplies input to a scene's wait. Click the picture when prompted.
Escape pauses. Continue acknowledges a notice or a completed scene. Loading a
scene leaves it paused. Scripted conversations now stay in the original room:
click a response, read the answer, then click **Continue** for the next choices.
Use the mouse wheel/Page Up/Page Down if text extends beyond the seven-line
pane. Loading a conversation shows its saved answer again without repeating
its effect. The Bar now also opens in the main game screen: click a visitor,
choose a response, read the answer and Continue. Scroll long conversations with
the mouse wheel or Page Up / Page Down. Use Leave to return to the bar and its
Back icon to return to the control room. Save/Load remains available during
conversations. Returned intelligence, pirate rewards and contract announcements
now appear as incoming messages and remain available in **Messages**. Scroll
long reports, then Continue. Click a hired commander at the control-room table
for advice or **Go to university?** Developer training offers four courses;
other commanders receive general training. Accept or decline the quoted price.
Leave/Escape returns to the room. Loading closes the consultation; click the
commander again to resume a saved training quote without requesting another.
The current source saves in format v23. Older v21/v22 saves can load here,
retaining their previously displayed female hero; older saves do not gain
missing historical report snapshots.

Losing New Earth plays the original defeat film after battle
results and pending notices. **Space** or **Play/Pause** controls playback;
**Escape** pauses. **Replay**, **Save result**, **Load** and **Main menu (F10)**
remain available. Loading a defeated campaign restarts the film paused.
The film now uses the complete original module music. Music pauses/restarts
with the film; disable **Follow game music** in Music controls to opt out.
Source installations need `python tools/install_module_audio.py` once for the
local module decoder. Earth victory now plays the original congratulations
sequence, animation, music and scrolling credits with the same controls. The
original 1995 promotional cards are preserved as historical artwork. Loading
a won campaign opens this film paused. The portable ZIP includes the decoder.

## First steps

1. Hover over an icon or room feature to see its name in the upper status bar.
   The red arrow at the top right switches between the two rows of icons.
2. Switch to the second row and click **COMMANDERS** (first icon).
3. Click **DEVELOPERS** (fifth icon), then Sapphire Fox's portrait on the left.
   Her offer appears below the portraits. Click **HIRE MAN** (sixth icon).
4. Click **BACK TO M.SCREEN** (the door at the far left). Your developer now
   appears in the control room.
5. Click **RESEARCH-DESIGN** (second icon on the first row, or the left room
   computer). Click the **Miner droid** cell, second from the left in the top
   row. Clicking an active research cell pauses it; clicking again resumes it.
6. Click **Run (Space)** below the artwork, press **Space** while the game
   canvas has focus, or click the date/time box. Repeat to pause.
   The bottom bar shows **Running** or **Paused** and offers **1x / 4x / 12x**
   speeds; 1x advances one game hour per second. Default speed is 4x.
   Right-clicking the date box starts at 12x when paused. Research, travel
   and construction require time to run.

The clock pauses for Save/Load and events that need your attention. Placement,
route selection and production orders also keep time paused while you make a
decision. The bottom bar explains these pauses. Finish or cancel the action,
then click Run; loading a save never resumes time automatically.

**Esc** returns to the control room. **F11** toggles fullscreen. The artwork
scales in whole pixels, with black borders when the window shape differs.

## Explore the map

Open **GALACTIC MAP**, fourth icon on the control room's first row. Left-click
a planet for information; right-click it to see its moons. Click a moon to
inspect it. **ZOOM OUT** returns to the solar system. In planet information,
the map icon returns to the orbital view; click the landscape to enlarge it.
Owned active colonies have tax increase/decrease icons. Changing taxes affects
later income and morale. Other system buttons appear as research and discovery
allow. Hidden planets and undiscovered moons stay hidden.

Click an identified alien's portrait to
read its original race profile. Survey must reach 40. A spy ship or returned
military-intelligence mission reveals known force counts below the profile.
Click those counts to see exact values (`+++` means the small field overflowed).
Click the body or press Escape to return to the profile, then planet information.

In a planet's orbital view, click a fleet icon in the right-hand panel to
select it. Use **LAUNCH** / **LAND** below the map; a fleet in orbit can
**MOVE** by clicking a destination. Right-click a primary planet to zoom in
and choose a moon. **ABORT MOVE** cancels without moving the fleet. Choosing
a route pauses time; resume time after departure to let the fleet travel.
For more than 18 fleets, use the mouse wheel or Page Up / Page Down.
New games have no moving fleets until you create them through progression.

Ship Info opens the original fleet overview with that fleet selected. Cargo
opens the original transfer screen. Space attacks use the map icons and main
screen; ground deployment and combat also use the original main screen.
Map motion and sprite scaling
approximate the original animation.

## Fit a fleet

Open **SHIP INFO** from the control room. Left-click a group to select it;
right-click it, or select **GROUP**, to open its equipment. **CHANGE** switches
between moving fleets and planetary forces. Mouse wheel or Page Up / Page Down
shows additional local groups when there are more than 32.

**NEW UNIT** opens the original creation form when progression unlocks a type
and there is room in the 32-group moving fleet limit. Click the type to cycle
available types; right-click cycles backward. Click the name to edit, then press
Enter. **OK,CREATE IT** creates the empty group at New Earth; **ABORT** discards
the draft. No stock is consumed until you fit the group.

On the original equipment screen, **left-click a count to load one** hull or
component; **right-click to unload one**. Returning a hull also returns equipment
that no longer fits. Transfers require a landed fleet at an owned colony.
New Earth supplies the main depot; remote worlds use their local stock.

Use the large right arrows to change equipment category and the arrows beside
the name to change groups. Click the name to edit it; **Enter** confirms and
**Esc** cancels. Naming pauses time. Resume time after finishing.

The equipment screen's **SHIP INFO** icon returns to the selected overview
group. **TRANSFER** opens cargo controls. **CONTROL PANEL** opens that fleet's
original cockpit, including while it is travelling.

## Use the cockpit

Hover over the instruments to identify their controls. The left lever launches
or docks the fleet. The middle control selects **Move** or **Change destination**:
choose a destination on the graphical map, or **ABORT MOVE** to return without
changing the route. Resume time after confirming a route so the fleet travels.
The left monitors open cargo for Trade/Pirate groups; the right instruments open
Ship Info and Group equipment. Clicking the forward view opens Planet Main
while the fleet is stationary. The top menu also provides map/surface links and
available deployment actions; use the top-right arrow for additional icons.
Instrument animation does not advance game time. Launch/landing transition
playback, fades, sound and input cleanup are included in this preview. Other
screen transitions, ambient animation and exact original colors remain under
audit.

## Transfer cargo

Select **TRANSFER** from fleet overview or equipment, or **CARGO** from the
selected orbital fleet. Land at an owned colony or mining outpost first.
The original screen shows planet stock on the left and ship stock on the right.
**Right-side arrows load the ship; left-side arrows unload it.** Left-click
moves up to 100 ore; right-click moves as much as fits. Both buttons move one
stored item per click. Research must be complete for stored items to appear,
and their transfers require a completed **Space Port** and a local item depot.
The bottom line shows shared cargo weight and the planet's per-ore storage.
Use **GROUP** to return to the selected fleet's equipment.

To remove an empty group, land at an owned colony, unload its cargo and hulls,
then select **DISBAND UNIT** on the equipment screen. Use the top-right arrow
if that icon is on the second page. Removal frees a group slot. Planetary defense
groups stay in place, and remaining cargo or unsafe inventory totals block removal.
The equipment menu also offers direct **GALACTIC MAP** and **PLANET MAIN** links.

## Build on a colony

Discovered foreign and unsettled worlds also allow **PLANET MAIN**, but their
terrain and radar remain black without support. Survey satellites reveal
unsettled surfaces on arrival; alien worlds destroy ordinary satellites and
require spy support. Deployed spy ships also reveal terrain. Viewing a foreign
surface does not permit construction. Owned colonies and mining outposts are
visible without a satellite.

Open **PLANET MAIN**, fifth control-room icon, to view New Earth. On an owned
colony's planet-information screen, the same icon opens that colony's surface.
Use the left arrows or mouse wheel to choose a building. Click the preview
for its cost and basic information. Hire a suitable builder before construction.

Click **BUILD**, move over the terrain, then click a clear position. Green
outlines indicate a footprint fits; red outlines indicate blocked placement.
The normal money, research, builder and prerequisite rules still apply.
Right-click the terrain to cancel. Resume time after placing the building.

Click **DEMOLISH**, then a completed building to remove it for 2,000 credits.
The Command centre and unfinished buildings cannot be demolished.
Click or drag the lower-left radar to move around; arrow keys and border clicks
also pan. Click most buildings to inspect their status, then the surface to return.
Completed mines and derricks open the mining screen described below.
Building information includes the original illustration and
description, blueprint requirements or live production, staffing, power and
working percentage. Click the card or left preview to return. The selected
building stays open as time advances. Terrain animation remains unfinished.
**SPACEPORT** opens that world's original local-force equipment
screen; its group selection stays restricted to the current world.
**SHIP INFO** separately opens the fleet overview. **SPACEPORT**
appears only for an owned colony with a local group. Entering the surface from
a cockpit also adds **CONTROL PANEL** to return to that ship.

You can pan a revealed foreign surface, but cannot build or demolish there.

## Manage mining

Click a completed mine or derrick on the colony surface, or **RESOURCE-MINE**
in planet information. The screen shows ore stocks, completed mines and active
and stored droids for that world. **ADD DROID**, the third icon, moves one
stored Miner droid into a completed unstaffed mine, up to nine active droids.
New Earth starts with two staffed mines and one stored droid: build another
mine and let construction finish before assigning it. Producing droids alone
does not put them to work; remote colonies need droids delivered to local stock.

Click the surface icon or scene to return. Mining outposts
return to their surface too. Ore rates are extraction batch amounts; outposts extract by
chance and full storage limits output. Detoxin uses derricks and shows **--**.
Large stocks use K/M/B units. No admin assistance is needed for normal mining.

## Deploy support and establish a colony

Open the destination's planet information. Deployment icons appear when the
world and available supplies qualify. Use the top-right arrow when there is
a second page of icons. **ADD SATELLITE**, **ADD MINER STATION**, **ADD SPY SAT**,
**ADD SPY SHIP** and **ADD SOLAR SAT** use the normal inventory and deployment
rules. Stationary fleets support their primary planet and all of its moons.
Fit hulls and station/satellite payloads in the original equipment screen.
Cargo loading still uses the existing cargo window.

**COLONIZATION** appears once Control Centre research is complete and a suitable
world has survey 30 or more. Hire a rank 2 builder for systems 1 and 2, or rank 3
for other systems. The base purchase costs **100,000 credits**.

Click building previews to add or remove any of the six optional buildings.
Selected previews brighten and the total updates. **Sorry** marks an unavailable
option. **OK,BUILD IT** pays and starts the colony; **ABORT** discards the draft
without charging. Time stays paused while selecting the bundle.

Click Run after confirming. Planet information shows the colony's remaining
arrival days. The site establishes at midnight after one or two game days;
optional buildings arrive later. Open **PLANET MAIN** once the colony exists.
Buildings still need their ordinary construction time after delivery.

## Find colonies and useful worlds

Open **MAIN COMPUTER**, third icon on the control room's second row.
**YOUR PLANETS** lists colonies and miner stations; **USEFUL PLANETS** lists
known colony/mining sites; **ALIEN PLANETS** lists known alien worlds.
Use the wheel, Page Up / Page Down or click the scrollbar to scroll.
Moons occupy two lines showing their parent planet and moon name. Either line
opens the moon's information; right-click opens its planetary map.
An empty list means no known world currently qualifies. A suitable site still
requires the normal research, supplies, commanders and money to settle it.

## Buy and manufacture

Open **INFO-BUY**, the first control-room icon or the second research icon.
Only completed research appears. **SELECT** opens the product list; use its
rows, arrows or mouse wheel. Click the picture to see the description and ore
costs. **BUY** opens quantity controls: +10, +1, -1 and -10. The handshake
confirms; the raised hand cancels. Time pauses while you edit an order.

Confirmation charges the displayed quantity; cancelling changes nothing.
Setting an existing queue to zero refunds its pending items. Resume time to
manufacture. Large numbers that cannot fit use rounded K/M/B labels;
resources and charges remain exact. Destroyer and Cruiser orders require existing space stations.
Technology used for colony construction or fleet upgrades is not purchased here.

## Save and resume

Open **DISK OPERATIONS**, the fourth icon on the control room's second row.
Use **SAVE** (third icon) to create a named `.json` save, and **LOAD** (second
icon) to resume it. Keep separate saves before major decisions and battles.

Reopening the application shows the menu; choose **LOAD GAME** to resume.
Closing normally writes
`saves/recovered-autosave.json`; it does not automatically resume that file.
Automatic backups are reused, so keep named saves for progress you value.

## Graphical and diagnostic interfaces

The startup menu and hero selection, control room, commander hiring/advice,
university, research, Info/Buy, map/planet/race views, colony surfaces, mining,
fleets, equipment, cargo, cockpit, battles, story scenes, conversations, Bar,
messages and ending films are connected through the original graphical client.
Use **Play intro** from the startup menu to watch the opening film. Product
models use original geometry; their rotation and shading may differ from the
DOS version.

`Launch-Recovered.cmd` opens a table-based interface for diagnostics.
The controls in this guide use the graphical game; you do not need the
diagnostic interface to play.

## Optional admin help

Press **F2** to open the optional **Admin & log** panel, select **Enable admin
changes for this session**, then enter a valid command. Opening the panel or
enabling the checkbox alone does not alter the session; applying a valid admin
command marks the session assisted. For example:

```text
give credits 100000
give texon 5000
```

Press Esc to return. Admin changes are logged and mark the session assisted.
F2 is not required for ordinary player actions. Leave admin disabled for normal
balance testing, and report any older DOS save imports separately.

## Send feedback

Use [TESTER-FEEDBACK.md](TESTER-FEEDBACK.md). Describe the screen, what you
clicked, what you expected, and the game date. Keep a named save from before
the problem, and mention it in your report. For crashes in a Windows package,
check `logs/launch.log`; from source, check terminal output.

## Editing a new group name

Click the displayed type (for example Army) to cycle through unlocked group
types. Enter commits a typed name and Escape cancels its edit. Clicking another
control also commits a valid name, so you can edit the name and then click the
type directly. An empty or invalid name keeps the editor open; correct it or
press Escape.

## Deploy a Spy ship

A Spy ship is carried as payload by a Carrier group. Research/manufacture it,
then load it through Group/Equipment at an eligible colony. Move the loaded
Carrier to the alien planet and wait for travel to finish. Survey must be at
least 30; a Spy satellite can establish the necessary scanning first. Open
Planet Info or the stationary carrier cockpit and choose the Spy ship deployment
icon (use the menu paging arrow when necessary). Hover to identify icons.

The action requires alien ownership, no spy ship already deployed and a loaded
stationary carrier at the same system/primary planet. It consumes one carried
Spy ship and establishes reconnaissance, including terrain/force intelligence.
It is not an independently routed combat group. Researching or manufacturing
one without loading the Carrier is insufficient.

## Equipment limits (a6 update)

Reaching a stock or equipment-capacity limit no longer opens a separate
error dialog in the original graphical equipment screen. The in-game header
shows No stock available, Equipment bay full, or Nothing to unload. The
rejected transfer changes no inventory and keeps keyboard/mouse focus in the
game. Hovering does not erase the notice; the next equipment action or opening
another equipment view clears it. Normal stock and capacity rules still apply.

## Loading tanks and starting a planetary assault

Army groups have two equipment categories. While landed at an owned colony
with stock (New Earth is the simplest), open Group/Equipment and click the
lower red arrow on the right edge of the equipment table. This switches from
spacecraft to Trooper, Tank, Aircraft and Missile Tank. Load researched,
manufactured ground units and their weapons there; the upper arrow returns to
spacecraft. You do not need a separate Trade group to carry an Army's tanks.

Travel with the Army to a surveyed non-allied alien planet, select the Army in
the planet's orbital view, and choose Assault. A rank 2 or 3 fighter commander
is required. Resolve any space defense, then arrange ground groups and use
OK, ATTACK. Ground forces must be equipped before departing; the Group screen
cannot load inventory while the fleet is in orbit or traveling.

## Fast loading and troop assignment (a7)

Hover an equipment count, a cargo arrow or stock/carried count, or a ground
setup troop count. The screen layout is unchanged.

| Control | Equipment and troop counts | Cargo arrows/counts |
| --- | --- | --- |
| Middle-click | Load/fill maximum | Transfer maximum in the target's direction |
| Shift + middle-click | Unload/return all possible | Transfer maximum in the opposite direction |
| Wheel up/down | Add/remove one per notch | Load/unload 100 ore or one stored item per notch |
| Shift + wheel | Add/remove ten per notch | Load/unload 1,000 ore or ten stored items per notch |

Without a middle button, Shift + left-click does the same as middle-click;
Shift + right-click does the same as Shift + middle-click. For cargo, the depot
number loads and the carried number unloads. Wheel direction always means
load/up or unload/down, whichever side you hover.

Maximum applies only to the selected counter. It respects available stock,
shared payload/cargo capacity, group limits, production reservations and depot
space. Unloading hulls returns their excess equipment; hulls still needed for
loaded cargo stay aboard. Ground groups can be emptied to reserve and refilled
without deleting the group. Normal left/right clicks keep their existing behavior.

## Who is attacking? (a8)

Incoming space battles show a bold notice above the battle controls, for
example "UNDER ATTACK: The Morgruls at New Earth". The battle starts paused;
read the notice, then press Space or Run to begin. This identifies the attack
when it reaches combat; it is not an advance warning of fleets still in transit.

The notice stays visible while hovering controls and after loading a battle
save. The result retains the opponent's identity. Additional hostile forces
are listed if several civilizations participate; queued attacks are counted
separately. Outgoing battles show the target and opponent. A brief "Vs" label
also appears in the native header when no control is being hovered.

New incoming attacks write a named entry to the log (F2 > Admin & log), with
the attacking fleet and planet. The notice also works with older battle saves;
no new saved fields or campaign restart are needed. No external popup is used.

## Optional campaign save points

The 23 checkpoints are in **tester-saves** in the source repository and
**Optional Saves** in a built Windows package. START-HERE.md lists their dates,
what is already done and the next step. Choose More Icons > Disk Operations >
Load file..., browse to that folder and load your selection. A battle or
ending also has a Load control below the game. Save your continuation under a
new name in your usual save folder.

The checkpoints preserve the resources, decisions and casualties from a
campaign played without resource assistance. Their old message logs have
been cleared. Some
battles are still to be fought; saves labeled Already Won or Battle Won are
after combat. Number 22 starts at the final battle result: Continue, then
Continue the liberation notice. Number 23 opens the victory film paused.
The collection is optional and includes story spoilers; New Game is unchanged.
