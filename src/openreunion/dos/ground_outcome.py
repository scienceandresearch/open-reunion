"""Ordered ground campaign consequences after numerical casualty writeback."""
from copy import deepcopy
from ..core import GameError
from .aliens import destroy_civilization
from .campaign import schedule_idea
from .ground_conquest import conquer_for_player, conquer_for_alien
from .savefile import SaveBlocks


FLAGS = (0x5D67, 0x5D68, 0x5D6D, 0x5D75, 0x164, 0x5D3C, 0x5D8C,
         0x5D71, 0x5D70, 0x221, 0x5D6C)


def read_ground_outcome_fields(data):
    blocks = SaveBlocks(data)
    return {f"{at:x}": blocks.number(at, "B") for at in FLAGS}


def ground_outcome(state, destination, catalog, alien_rules, *, player_won,
                   player_attacking, conquering_owner=None, search_ruins=False):
    """0x7AF9..0x7E2B: copied state, next phase and ordered presentation events.

    Casualties must already be applied and retreat must already suppress a win.
    search_ruins is the fleet-action context formerly held in transient 780C.
    Restores the unreachable first nonterminal defeat reward: DOS tests a
    redraw flag that this same handler has unconditionally set to one.
    """
    for value in (player_won, player_attacking, search_ruins):
        if type(value) is not bool:raise GameError("Invalid ground outcome flag.")
    identity = ":".join(map(str, destination))
    if identity not in state["worlds"]:raise GameError("Unknown ground battle world.")
    if not player_won and not player_attacking:
        if type(conquering_owner) is not int or not 2 <= conquering_owner <= 12:
            raise GameError("Ground defeat requires a valid conquering civilization.")
    state = deepcopy(state);events = [];flags = state["flags"]
    phase = "defeat" if not player_won and tuple(destination) == (1, 5, 0) else "starmap"
    raw = state["worlds"][identity]["raw"];owner = raw[0]

    def discover(product, *, complete=False):
        row = state["products"][product-1]
        if row["research_state"] == 0:
            row["research_state"] = 5 if complete else 3
            if complete:row["research_remaining"] = 0

    if player_won and raw[1] == 1 and 2 <= owner <= 12:
        events.append(("civilization_destroyed", owner))
        if owner == 3:
            events.append(("message", 35))
            flags["5d8c"] = 1;flags["5d71"] = 0;flags["5d70"] = 1
            discover(19)
            # The original calls schedule after unlocking; its guard preserves
            # an existing timer and consumes no RNG for this redundant request.
            schedule_idea(state, state["products"], 19, 50, 20)
            if 0 < state["civilizations"][2][27] < 128:state["civilizations"][2][27] = 6
            state["known_systems"][3:6] = [0]*3;flags["221"] = 2
            events.append(("scene", 3));state["training_phase"] = 5
        if owner == 12:phase = "victory"
        if search_ruins and state["products"][11]["research_state"] == 0:
            events.append(("message", 13));discover(12)
        if owner in (7, 8, 9, 10) and all(
                race == owner or state["civilizations"][race-2][15] == 0 or
                state["civilizations"][race-2][27] == 6 for race in (7, 8, 9, 10)):
            events.extend((("message", 32), ("scene", 5)))
            state["training_phase"] = 6;state["known_systems"][6] = 0;discover(33, complete=True)
        state["civilizations"], state["worlds"] = destroy_civilization(state["civilizations"], state["worlds"], owner)
    if player_won and not flags["5d67"]:
        flags["5d67"] = 1;schedule_idea(state, state["products"], 13, 20, 20)
    if not player_won and phase != "defeat" and not flags["5d68"]:
        flags["5d68"] = 1;events.append(("message", 14))
        schedule_idea(state, state["products"], 17, 5, 5)
    if player_won and flags["5d6d"]:
        flags["5d6d"] = 0;events.extend((("message", 16), ("scene", 3)))
        state["training_phase"] = 3
    if player_won and flags["5d75"]:
        flags["5d75"] = 0;events.append(("message", 16));flags["164"] = 2;flags["5d3c"] = 1
        schedule_idea(state, state["products"], 20, 30, 10)
        schedule_idea(state, state["products"], 25, 500, 100)
        events.append(("scene", 3));state["training_phase"] = 4
    if player_won and player_attacking:state = conquer_for_player(state, destination, catalog)
    if not player_won and not player_attacking:
        state = conquer_for_alien(state, destination, conquering_owner, alien_rules)
    return state, phase, events
