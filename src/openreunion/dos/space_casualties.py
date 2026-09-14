"""Space-battle survivor writeback, independent of presentation and simulation."""
from collections import Counter
from copy import deepcopy
import struct
from ..core import GameError, integer
from .aliens import fleet_at, store_fleet


def apply_casualties(fleets, civilizations, worlds, destination, survivors):
    """0x17010..0x175F5 with explicit participant identities and target worlds.

    Survivor entries identify source 'player' (bank/slot), 'alien' (race/slot)
    or 'world' (world ID), plus hull 1..4. These typed identities avoid the
    original overlapping one-byte fleet IDs. Counts refer to surviving combat
    entries; do not pass already reconstructed final fleet quantities.
    """
    fleets, civilizations, worlds = deepcopy((fleets, civilizations, worlds))
    counts = Counter()
    for entry in survivors:
        if not isinstance(entry, dict):raise GameError("Invalid battle survivor record.")
        source = entry.get("source")
        integer(entry.get("hull"), "Surviving hull type", minimum=1, maximum=4)
        if source == "player":
            bank = entry.get("bank")
            if bank not in ("moving", "local"):raise GameError("Invalid battle fleet bank.")
            integer(entry.get("slot"), "Battle fleet slot", minimum=1, maximum=len(fleets[bank]))
            key = (source, bank, entry["slot"], entry["hull"])
        elif source == "alien":
            integer(entry.get("race"), "Battle race", minimum=2, maximum=12)
            integer(entry.get("slot"), "Alien battle slot", minimum=1, maximum=7)
            key = (source, entry["race"], entry["slot"], entry["hull"])
        elif source == "world":
            if entry.get("world") not in worlds:raise GameError("Unknown battle world.")
            key = (source, entry["world"], entry["hull"])
        else:raise GameError("Unknown battle participant source.")
        counts[key] += 1
    losses = {"friendly": [0]*4, "hostile": [0]*4}

    def retained(old, key, side, hull):
        integer(old, "Original battle stock", maximum=2**32-1)
        live = counts.pop(key, 0)
        if live > old:raise GameError("Survivor count exceeds the original force.")
        quantity = live + (old-live)//5
        losses[side][hull-1] += old-quantity
        return quantity

    for bank in ("moving", "local"):
        for slot, row in enumerate(fleets[bank], 1):
            if row[19:21] != list(destination[:2]) or row[22] not in (1, 2, 7) or row[0] not in (1, 3, 5):continue
            for hull in range(1, 5):
                at = 29+10*(hull-1)
                old, *equipment = struct.unpack_from("<5h", bytes(row), at)
                quantity = retained(old, ("player", bank, slot, hull), "friendly", hull)
                if any(value < 0 for value in equipment):raise GameError("Negative battle equipment.")
                row[at:at+10] = struct.pack("<5h", quantity, *[value*quantity//old if old else 0 for value in equipment])
    for race, civilization in enumerate(civilizations, 2):
        side = {2: "hostile", 6: "friendly"}.get(civilization[27])
        if side is None:continue
        for slot in range(1, civilization[38]+1):
            row = fleet_at(civilization, slot)
            if row[8:10] != list(destination[:2]) or row[2] != 1:continue
            for hull in range(1, 5):
                at = 11+2*(hull-1);old = struct.unpack_from("<H", bytes(row), at)[0]
                quantity = retained(old, ("alien", race, slot, hull), side, hull)
                row[at:at+2] = struct.pack("<H", quantity)
            store_fleet(civilization, slot, row)
    for identity, world in worlds.items():
        coords = tuple(map(int, identity.split(":")));raw = world["raw"];owner = raw[0]
        if coords[:2] != tuple(destination[:2]) or not 2 <= owner <= 12:continue
        side = {2: "hostile", 6: "friendly"}.get(civilizations[owner-2][27])
        if side is None:continue
        for hull in range(1, 5):
            at = 27+4*(hull-1);old = struct.unpack_from("<I", bytes(raw), at)[0]
            quantity = retained(old, ("world", identity, hull), side, hull)
            raw[at:at+4] = struct.pack("<I", quantity)
    if counts:raise GameError("Survivors refer to a force outside this battle.")
    return fleets, civilizations, worlds, losses
