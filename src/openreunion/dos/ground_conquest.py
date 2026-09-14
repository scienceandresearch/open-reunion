"""Exact-world conquest and colony-loss effects, independent of screens."""
from copy import deepcopy
import struct
from ..core import GameError
from .aliens import reset_world, settle_world
from .campaign import random_bounded
from .colony import allocate_colony
from .fleets import update_capacity
from .surface import new_building


def reset_battle_world(state, destination):
    """0x1EC0E..0x1EC25: reset world state, retaining buildings and fleets."""
    state = deepcopy(state);identity = ":".join(map(str, destination))
    if identity not in state["worlds"]:raise GameError("Unknown conquest world.")
    state["worlds"][identity]["raw"] = reset_world(state["worlds"][identity]["raw"])
    return state


def lose_colony(state, destination):
    """0x1EC25..0x1ECD6: reset and remove exact-world buildings/local defenses.

    Native compaction uses the actual local bank instead of DOS's selected-bank
    count. Moving fleets and other colonies retain their records.
    """
    state = reset_battle_world(state, destination)
    state["buildings"] = [row for row in state["buildings"] if row[1:4] != list(destination)]
    state["fleets"]["local"] = [row for row in state["fleets"]["local"] if row[19:22] != list(destination)]
    return state


def conquer_for_player(state, destination, catalog):
    """0x1EF65..0x1F0D0 in the post-battle screen context.

    Command center placement remains the original 255/255 pending surface
    placement. The later surface adapter resolves it against terrain. Creation
    includes original building RNG and allocation before adding local defense.
    """
    state = reset_battle_world(state, destination);identity = ":".join(map(str, destination))
    definition = next((world for world in catalog["worlds"] if world["id"] == identity), None)
    if definition is None:raise GameError("Conquest world is missing from the catalog.")
    raw = state["worlds"][identity]["raw"]
    raw[0] = 1;raw[6] = 1;raw[9] = 0
    state["rng"], roll = random_bounded(state["rng"], 3000)
    raw[13:17] = struct.pack("<I", 2000+roll);raw[17:20] = [20, 3, 30]
    command = next(item for item in catalog["buildings"] if item["id"] == 1)
    fields = bytes.fromhex(command["unclassified_fields_hex"])
    if len(state["buildings"]) < 1000 and 1 <= raw[21] <= 11 and fields[raw[21]+4] > 0:
        row, state["rng"] = new_building(command, destination, 255, 255, raw[21], state["rng"])
        state["buildings"].append(row)
        allocation = allocate_colony(raw, state["buildings"], catalog["buildings"], destination)
        update_capacity(state["fleets"], destination, allocation["defense_capacity"])
    row = [0]*161;name = (definition["name"]+" forces").encode("ascii")[:17]
    row[0:2] = [5, len(name)];row[2:2+len(name)] = name;row[19:23] = [*destination, 7]
    state["fleets"]["local"].append(row)
    return state


def conquer_for_alien(state, destination, owner, rules):
    """Ground defeat settlement using the already recovered alien initializer."""
    if type(owner) is not int or not 2 <= owner <= 12:raise GameError("Invalid conquering civilization.")
    state = lose_colony(state, destination);identity = ":".join(map(str, destination))
    state["worlds"][identity]["raw"], state["rng"] = settle_world(
        state["worlds"][identity]["raw"], owner, state["rng"], rules,
        morgrul_late=bool(state.get("flags", {}).get("5d6c", 0)))
    return state
