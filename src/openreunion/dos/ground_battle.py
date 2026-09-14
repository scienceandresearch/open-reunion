"""Ground battle placement; movement/attack progression is recovered separately."""
from copy import deepcopy
import struct
from ..core import GameError
from .ground_geometry import nearest_ground_target


def ground_group(battle, side, index):
    """Resolve a troop or the separately stored original slot-21 base record."""
    if index == 21:return battle.get(side+"_special")
    groups = battle[side+"_groups"]
    return groups[index-1] if 1 <= index <= len(groups) else None


def clear_destroyed_base_reservations(battle):
    """Repair stale base occupancy in a caller-owned battle copy.

    Only clear cells still owned by the destroyed base, preserving any troop
    that has since entered its former footprint. Also handles older snapshots
    whose renderer kept restoring these reservations after quantity reached zero.
    """
    for side,code in (("friendly",21),("hostile",121)):
        base=battle.get(side+"_special")
        if base is None or struct.unpack("<h",bytes(base[1:3]))[0]>0:continue
        for column in battle["board"]:
            for y,value in enumerate(column):
                if value==code:column[y]=0
        if battle.get("selected_group")==21 and battle.get("selected_friendly",True)==(side=="friendly"):
            battle["selected_group"]=0


def initialize_ground_battle(setup, motion, *, player_attacking):
    """0xA050..0xA37E: place selected groups and initialize combat work fields.

    Special class-five records occupy their own fields instead of an implicit
    out-of-count twenty-first array entry. They are not added to troop totals.
    No allocator residue enters the native board or special records.
    """
    if type(player_attacking) is not bool:raise GameError("Invalid ground attack flag.")
    battle = deepcopy(setup)
    battle["friendly_groups"] = [row for row in battle["friendly_groups"] if struct.unpack("<h", bytes(row[1:3]))[0] != 0]
    battle.update({"board": [[0]*9 for _ in range(16)], "done": False, "counter": 0,
                   "instant_kill": False, "player_attacking": player_attacking})
    for side in ("friendly", "hostile"):
        groups = battle[side+"_groups"];count = len(groups)
        if count > 20:raise GameError("Ground battle exceeds twenty troop groups.")
        for index, row in enumerate(groups, 1):
            offset = 4-min(count-index//9, 8)//2
            row[4] = 2+(index-1)//9 if side == "friendly" else 13-(index-1)//9
            row[5] = (index-1)%9+offset
            if side == "friendly":
                row[8:12] = [3, 0, 0, 1];row[15] = 1
            else:
                row[15] = 3
                row[16] = nearest_ground_target(groups, battle["friendly_groups"], index, motion)
            row[6:8] = [0, 0];row[12:15] = [0, 0, 0];row[18] = 0
        special = [0]*39;special[0:6] = [5, 1, 0, 100, 0, 4];special[8] = 1
        if side == "hostile":special[4] = 14 if player_attacking else 15
        battle[side+"_special"] = special
    return battle
