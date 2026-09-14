"""Space battle withdrawal and ordered campaign consequences."""
from copy import deepcopy
import struct
from ..core import GameError, integer
from .aliens import fleet_at, route_fleet, store_fleet, unload_fleet
from .campaign import schedule_idea
from .fleets import local_record
from .navigation import depart
from .savefile import SaveBlocks


FLAGS = (0x5D67, 0x5D6D, 0x5D75, 0x164, 0x5D3C, 0x23C)


def read_space_outcome_fields(data):
    blocks = SaveBlocks(data)
    return {f"{at:x}": blocks.number(at, "B") for at in FLAGS}


def withdraw_space_forces(fleets, civilizations, worlds, destination, player_won, seed):
    """0x1EA42..0x1EC0E: withdraw the losing side after casualty writeback.

    Fleet removal uses its actual bank, fixing the DOS selected-count defect.
    Home-world disbanding transfers Army space/ground and Pirate space records
    to the last local defense at the exact world, as in 0x1F203..0x1F3CA.
    """
    fleets, civilizations, worlds = deepcopy((fleets, civilizations, worlds))
    if not player_won:
        kept = []
        for row in fleets["moving"]:
            if row[22] > 2 or row[19:21] != list(destination[:2]):
                kept.append(row)
                continue
            if tuple(destination[:2]) != (1, 5):
                row, seed = depart(row, (1, 5, 0), seed)
                kept.append(row)
                continue
            local = local_record(fleets, row[19:22])
            if local is not None and row[0] in (1, 3):
                stop = 109 if row[0] == 1 else 69
                for at in range(29, stop, 2):
                    old = struct.unpack_from("<h", bytes(local), at)[0]
                    incoming = struct.unpack_from("<h", bytes(row), at)[0]
                    integer(old, "Local defense stock", maximum=32767)
                    integer(incoming, "Disbanded fleet stock", maximum=32767)
                    integer(old+incoming, "Combined defense stock", maximum=32767)
                    local[at:at+2] = struct.pack("<h", old+incoming)
        fleets["moving"] = kept
    relation = 2 if player_won else 6
    for race, civilization in enumerate(civilizations, 2):
        if civilization[27] != relation:continue
        for slot in range(1, civilization[38]+1):
            row = fleet_at(civilization, slot)
            if row[2] != 1 or row[0] <= 1 or row[8:10] != list(destination[:2]):continue
            home = civilization[17:19]
            if home == list(destination[:2]):
                identity = ":".join(map(str, row[8:11]))
                if identity not in worlds:raise GameError("Unknown alien fleet home world.")
                row, worlds[identity]["raw"] = unload_fleet(row, worlds[identity]["raw"], race)
            else:
                row, seed = route_fleet(row, (*home, 0), seed)
            store_fleet(civilization, slot, row)
    return fleets, civilizations, worlds, seed


def space_outcome(state, destination, *, player_won, player_attacking, ground_requested):
    """0x76AD..0x77F1: copied campaign state, next screen purpose and events.

    Numerical casualties must already be applied. player_won is false for an
    explicit retreat even when friendly ships remain. Ground setup is a later
    interaction phase, not evidence that a ground battle has been resolved.
    """
    for value in (player_won, player_attacking, ground_requested):
        if type(value) is not bool:raise GameError("Invalid space battle outcome flag.")
    state = deepcopy(state)
    state["fleets"], state["civilizations"], state["worlds"], state["rng"] = withdraw_space_forces(
        state["fleets"], state["civilizations"], state["worlds"], destination, player_won, state["rng"])
    phase = "ground_setup" if ground_requested and player_won == player_attacking else "starmap"
    flags = state["flags"];events = []
    if player_won:
        if not flags["5d67"]:
            flags["5d67"] = 1
            schedule_idea(state, state["products"], 13, 20, 20)
            schedule_idea(state, state["products"], 17, 90, 50)
        if flags["5d6d"]:
            flags["5d6d"] = 0
            schedule_idea(state, state["products"], 18, 3, 0)
            events.extend((("message", 16), ("scene", 3)))
            state["training_phase"] = 3
        if flags["5d75"]:
            flags["5d75"] = 0
            events.append(("message", 19))
            flags["164"] = 2;flags["5d3c"] = 1
            schedule_idea(state, state["products"], 20, 30, 10)
            schedule_idea(state, state["products"], 25, 500, 100)
            events.append(("scene", 3));state["training_phase"] = 4
        if destination[0] == 8:flags["23c"] = 2
    return state, phase, events
