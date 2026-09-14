"""Ground battle survivors and proportional campaign stock writeback."""
from copy import deepcopy
import struct
from ..core import GameError, integer
from .aliens import fleet_at, store_fleet


def apply_ground_casualties(fleets, civilizations, worlds, destination, battle):
    """0xC869..0xCF5E, with exact world identity and both sides' reserves.

    Groups retain their original class identity. Each participating source's
    quantities receive the original pooled survivor fraction. Its equipment
    follows its actual surviving units, as in space casualties, so rounding
    cannot increase weapons per hull or leave weapons on a zero-unit group.
    The fourth equipment word is untouched. Inputs are not mutated.
    """
    fleets, civilizations, worlds = deepcopy((fleets, civilizations, worlds))
    identity = ":".join(map(str, destination))
    if identity not in worlds:raise GameError("Unknown ground casualty world.")
    live = {};losses = {}
    for side in ("friendly", "hostile"):
        totals = battle[side+"_totals"];reserve = battle[side+"_reserve"]
        if len(totals) != 4 or len(reserve) != 4:raise GameError("Invalid ground casualty class pools.")
        live[side] = list(reserve)
        for value in totals+reserve:integer(value, "Ground casualty pool", maximum=2**63-1)
        for row in battle[side+"_groups"]:
            integer(row[0], "Ground survivor class", minimum=1, maximum=4)
            count = struct.unpack("<h", bytes(row[1:3]))[0]
            integer(count, "Ground survivors", maximum=32767);live[side][row[0]-1] += count
        if any(a > b for a, b in zip(live[side], totals)):raise GameError("Ground survivors exceed their original class total.")
        losses[side] = [total-count for total, count in zip(totals, live[side])]

    def scaled(value, side, kind):
        integer(value, "Original ground stock", maximum=2**32-1)
        total = battle[side+"_totals"][kind]
        return value*live[side][kind]//total if total else 0

    for bank in ("moving", "local"):
        for row in fleets[bank]:
            if row[19:22] != list(destination) or row[22] not in (1, 2, 7) or row[0] not in (1, 5):continue
            for kind in range(4):
                at = 69+10*kind;values = struct.unpack_from("<4h", bytes(row), at)
                old,*equipment=values
                quantity=scaled(old,"friendly",kind)
                for value in equipment:integer(value,"Original ground equipment",maximum=2**32-1)
                row[at:at+8] = struct.pack("<4h",quantity,*[value*quantity//old if old else 0 for value in equipment])
    for civilization in civilizations:
        side = {6: "friendly", 2: "hostile"}.get(civilization[27])
        if side is None:continue
        for slot in range(1, civilization[38]+1):
            row = fleet_at(civilization, slot)
            if row[8:11] != list(destination) or row[2] != 1:continue
            values = struct.unpack("<4H", bytes(row[19:27]))
            row[19:27] = struct.pack("<4H", *[scaled(value, side, kind) for kind, value in enumerate(values)])
            store_fleet(civilization, slot, row)
    raw = worlds[identity]["raw"];owner = raw[0]
    side = {6: "friendly", 2: "hostile"}.get(civilizations[owner-2][27]) if 2 <= owner <= 12 else None
    if side:
        values = struct.unpack("<4I", bytes(raw[43:59]))
        raw[43:59] = struct.pack("<4I", *[scaled(value, side, kind) for kind, value in enumerate(values)])
    return fleets, civilizations, worlds, losses
