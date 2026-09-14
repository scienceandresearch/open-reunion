"""Alien travel, arrival contacts and explicit battle requests.

Recovered from file 0x138C6..0x13ED1. Battle resolution and client integration
remain separate; returning a request never implies that a battle was won.
"""
from copy import deepcopy
import struct

from ..core import GameError
from .aliens import fleet_at, store_fleet
from .navigation import contact


def contact_civilization(state, race):
    """Use the verified contact rules with the complete civilization record.

    This temporary adapter contains no persisted duplicate relationship state.
    It will also serve callers migrated from the older navigation schema.
    """
    campaign = {
        "rng": state["rng"], "idea_timers": state["idea_timers"],
        "alien_status": [row[27] if row[27] < 128 else row[27]-256 for row in state["civilizations"]],
        "navigation": {"flags": state["flags"], "timers": state["timers"], "encounter": state["encounter"]},
    }
    events = contact(campaign, state["products"], race)
    state["rng"] = campaign["rng"]
    state["encounter"] = campaign["navigation"]["encounter"]
    state["civilizations"][race-2][27] = campaign["alien_status"][race-2] & 255
    return events


def alien_hour(state):
    """Return (copied work record, ordered notices and battle requests).

    All counted slots of each race travel before that race's action pass.
    Dormant, uncounted slots remain untouched. Requests retain their own race,
    slot and destination, avoiding the DOS shared battle-global overwrite.

    Repairs: expired/nonpositive active timers resolve promptly; traveling
    player groups cannot defend their not-yet-reached destination.
    """
    state = deepcopy(state)
    events = []
    fleets = state["fleets"]
    for race, civilization in enumerate(state["civilizations"], 2):
        count = civilization[38]
        for slot in range(1, count+1):
            row = fleet_at(civilization, slot)
            if row[2] != 2:
                continue
            left = max(0, struct.unpack("<h", bytes(row[3:5]))[0]-1)
            row[3:5] = struct.pack("<h", left)
            if left == 0:
                row[2] = 1
            store_fleet(civilization, slot, row)
            if left:
                continue
            world = row[8:11]
            hostile = False
            for source in ("local", "moving"):
                for player in fleets[source]:
                    if player[19:22] != world:
                        continue
                    if source == "moving" and (player[0] == 4 or player[22] > 2):
                        continue
                    if civilization[27] == 0:
                        events.append(("contact", {"race": race, "world": list(world),
                                                   "source": "local" if source == "local" else "fleet"}))
                        events.extend(contact_civilization(state, race))
                    elif civilization[27] == 2:
                        hostile = True
            if hostile:
                events.append(("hostile_arrival", {"race": race, "world": list(world)}))

        for slot in range(1, count+1):
            row = fleet_at(civilization, slot)
            mission = row[7]
            if row[2] != 1 or mission == 0:
                continue
            if mission not in (1, 2, 3, 4):
                raise GameError("Unknown alien action; cannot infer a battle type.")
            left = max(0, struct.unpack("<h", bytes(row[5:7]))[0]-1)
            row[5:7] = struct.pack("<h", left)
            if left:
                store_fleet(civilization, slot, row)
                continue
            world = row[8:11]
            identity = ":".join(map(str, world))
            if identity not in state["worlds"]:
                raise GameError("Alien action refers to an unknown world.")
            ground = mission in (2, 4) and state["worlds"][identity]["raw"][0] == 1
            defenders = any(player[0] in (1, 3) and player[19:21] == world[:2]
                            and player[22] in (1, 2) for player in fleets["moving"])
            if ground or defenders:
                events.append(("battle", {"race": race, "slot": slot, "world": list(world),
                                          "ground": ground, "special": mission >= 3}))
            row[7] = 0
            store_fleet(civilization, slot, row)
    return state, events
