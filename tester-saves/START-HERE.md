# Optional campaign save points

Choose a point in the campaign without replacing your own saves. These are optional; New Game still starts normally.

Find these saves in `tester-saves` in the source repository, or **Optional Saves** in a built Windows package. Import your original game assets before loading a checkpoint.

The old message logs have been cleared. Resources, decisions, casualties, timers and all other gameplay state are preserved.

In the game, open More Icons > Disk Operations > Load file... and browse to `tester-saves` (or **Optional Saves** beside OpenReunion.exe). Select a numbered JSON below. In a battle or ending, use the Load control below it.

Time and battles load paused. Press Space/Run when ready; in a ground deployment select OK, ATTACK first. Save your continued game under a new name in your normal save folder.

**Spoilers:** the names and notes reveal campaign milestones. These saves come from a campaign played without resource assistance, including a battle retry. You inherit its economy, fleets and earlier decisions.

## Choose a checkpoint

| File | Date | What to expect | What to do next |
| --- | --- | --- | --- |
| 01 - New Game - Starting Colony.json | 2927/08/13/23 | Untouched campaign start at New Earth. | Build your economy and hire commanders, or use New Game for your own fresh campaign. |
| 02 - New Earth - Economy Established.json | 2927/09/09/10 | Home industry, services and additional housing are built. | Research and deploy survey satellites, then expand to other colonies. |
| 03 - Apollo - Colony Established.json | 2927/10/25/08 | Apollo has been settled. | Develop its power, industry, housing and colony services. |
| 04 - Four Colonies - Ready for First Contact.json | 2928/04/24/00 | New Earth, Apollo, Mir and Penelope are established; Jade contact has not happened. | Send the Trade group to Jade (1:7:0) to make first contact. |
| 05 - Jade Contact - Communicator Researched.json | 2928/04/26/08 | Jaanosian contact and Communicator research are complete; the Trade group is home. | Build up remote mining and ore transport. |
| 06 - Home Defense - Hunter Fleet Prepared.json | 2928/08/30/20 | Twenty armed Hunters are prepared; this is before the first Morgrul defense, not an active battle. | Maintain your colonies and advance time until the incoming attack arrives. |
| 07 - First Morgrul Defense - Already Won.json | 2928/09/20/06 | The first invasion has been defeated and acknowledged. | Replace losses, recover the Radio at Jade and develop Russel. |
| 08 - Phelonian Trade - Tank Technology Earned.json | 2928/10/27/13 | The Tank technology bargain is complete and the Trade group has returned home. | Manufacture and equip Tanks while preparing for later Morgrul attacks. |
| 09 - Third Morgrul Defense - Already Won.json | 2929/01/05/19 | The third invasion is defeated; later contact and technology progression is available. | Follow the prisoner/informant leads toward Mirach and its wreck. |
| 10 - Mirach Wreck - Technology Recovered.json | 2929/01/08/11 | The wreck landing has revealed Missile and Destroyer technology. | Return the expedition home, research the discoveries and prepare an assault force. |
| 11 - Morgrul Capital - Ground Deployment.json | 2929/03/23/08 | The space battle is won; player troops and Kall assistance are at ground deployment. | Arrange ground groups, choose OK, ATTACK, then use Space to run or pause the battle. |
| 12 - Morgruls Defeated - Later Systems Open.json | 2929/03/23/09 | The Morgrul campaign is complete and later systems are unlocked. | Replace losses and prepare an Antares expedition. |
| 13 - Antares - Nova Warning.json | 2929/04/07/21 | The Observatory has detected the impending nova. This is a time-sensitive campaign checkpoint. | Take the Trade group to the Erans at 4:2:0, complete contact, then bring your fleets out of Antares. |
| 14 - League Diplomacy - Alliance and Aircraft Idea.json | 2929/08/04/23 | The Undorling alliance has been earned and the Aircraft idea is available. | Research and equip Aircraft, defend your colonies and survey the League capitals. |
| 15 - Hirachi Capital - Ground Deployment.json | 2929/10/10/23 | The Hirachi space battle is won; ground forces await deployment. | Arrange forces and select OK, ATTACK. Space runs or pauses combat. |
| 16 - Druedian Capital - Ground Deployment.json | 2929/10/11/07 | The Druedian space battle is won; ground forces await deployment. | Arrange forces and select OK, ATTACK. Space runs or pauses combat. |
| 17 - Lisonian Capital - Formation Ready.json | 2929/10/11/15 | The ground formation is already organized into twenty groups; combat has not started. | Choose OK, ATTACK, select friendly groups and issue attack orders. Victory is not automatic. |
| 18 - Rigel Expedition - Earth Coordinates Known.json | 2929/11/04/10 | Syonian contact, advanced research and Earth coordinates are complete; the expedition is home. | Build and equip the final Earth fleet and establish the home Energy shield. |
| 19 - Final Fleet - Equipped and Home Shield Ready.json | 2930/09/10/17 | The final fleet is equipped and New Earth has a powered Energy shield. | Travel to Earth, establish contact and carry out reconnaissance and resistance preparations. |
| 20 - Earth - Surveyed Before Final Assault.json | 2930/09/23/00 | Earth reconnaissance and sabotage preparations are complete; the fleet is at Earth. | Select the Army in Earth orbit and choose Assault. |
| 21 - Earth - Final Ground Deployment.json | 2930/09/23/00 | The final space battle is won. Ground forces are ready to deploy. | Arrange the army, choose OK, ATTACK and command the final ground battle. |
| 22 - Earth - Battle Won Before Victory Film.json | 2930/09/23/00 | The final ground battle is already won; no further fighting is needed. | Click Continue, then Continue on the liberation notice to start the victory film. |
| 23 - Victory - Watch the Ending.json | 2930/09/23/00 | The campaign has been won; the victory film opens paused. | Press Play or Space to watch the ending. |

## Provenance and feedback

Tested with Open Reunion 0.38.0a8. The collection was generated by a campaign test that recorded game actions, with graphical checks at key milestones. These are Open Reunion saves, not imported DOS saves.
Each public checkpoint was derived from the verified archived checkpoint by clearing only its top-level event log. Gameplay state fields—including resources, battle results, campaign flags and unassisted status—are unchanged. `MANIFEST.json` records current hashes plus the original file and state hashes.
These points have different economies, fleets and active timers. Outcomes after loading depend on your decisions. For feedback, include the numbered save name, your clicks and a new save showing the problem.
