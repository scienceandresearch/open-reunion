"""Build space battle participants from campaign forces (0x159F3..0x16189)."""
import struct
from ..core import GameError, integer
from .aliens import fleet_at
from .campaign import random_bounded
from .space_combat import RULE_START


def build_space_battle(fleets, civilizations, worlds, destination, fighter_level, seed, rules):
    """Preserve roster order, statistics, placement draws and 500-unit side cap.

    The original checked the player cap only before each hull group, allowing
    writes beyond its allocation. Check every entry. Full unsigned alien/world
    quantities participate up to that cap instead of wrapping signed counts.
    Typed origins repair the shared planet ID and fleet ID collisions.
    """
    integer(fighter_level, "Fighter skill", maximum=32767)
    integer(seed, "Battle random seed", maximum=2**32-1)
    if len(destination) != 3 or ":".join(map(str, destination)) not in worlds:
        raise GameError("Unknown space battle destination.")
    table = bytes(rules["bytes"])
    def byte(at):return table[at-RULE_START]
    def dword(at):return struct.unpack_from("<i", table, at-RULE_START)[0]
    battle = {"rng": seed, "frame": 0, "done": False, "explosions": False,
              "instant_kill": False, "friendly": [], "hostile": []}
    def roll(limit):
        battle["rng"], value = random_bounded(battle["rng"], limit)
        return value
    def add(side, origin, legacy_id, hull, quantity, damage, mirrored):
        integer(quantity, "Battle hull stock", maximum=2**32-1)
        health = dword(0x5D4+4*hull)
        integer(health, "Battle hull health", minimum=1, maximum=32767)
        for _ in range(min(quantity, 500-len(battle[side]))):
            x = byte(0x7B7+hull)+roll(byte(0x7BB+hull))
            if mirrored:x = 160-x
            y = byte(0x7BF+hull)+roll(byte(0x7C3+hull))
            pattern = 2+roll(6);direction = byte(0x753+roll(8))
            raw = [legacy_id & 255, hull, *struct.pack("<Hh", min(65535, max(0, damage)), health),
                   x & 255, y & 255, pattern, direction, 0, 1]
            battle[side].append({"raw": raw, "origin": dict(origin)})
    for bank_index, bank in enumerate(("moving", "local")):
        for slot, row in enumerate(fleets[bank], 1):
            if row[19:21] != list(destination[:2]) or row[22] not in (1, 2, 7) or row[0] not in (1, 3, 5):continue
            for hull in range(1, 5):
                quantity, *equipment = struct.unpack_from("<5h", bytes(row), 29+10*(hull-1))
                if any(value < 0 for value in equipment):raise GameError("Negative battle equipment.")
                power = sum(value*dword(0x5C8+4*i) for i, value in enumerate(equipment))
                power = power*2//3 if fighter_level == 0 else power*(200+fighter_level)//220
                damage = power//quantity if quantity > 0 else 0
                add("friendly", {"source": "player", "bank": bank, "slot": slot},
                    100*bank_index+slot, hull, quantity, damage, False)
    for race, civilization in enumerate(civilizations, 2):
        side = {2: "hostile", 6: "friendly"}.get(civilization[27])
        if side is None:continue
        for slot in range(1, civilization[38]+1):
            row = fleet_at(civilization, slot)
            if row[8:10] != list(destination[:2]) or row[2] != 1:continue
            for hull in range(1, 5):
                quantity = struct.unpack_from("<H", bytes(row), 9+2*hull)[0]
                add(side, {"source": "alien", "race": race, "slot": slot},
                    10*race+slot, hull, quantity, dword(0x5E4+4*hull), True)
    for identity in sorted(worlds, key=lambda key: tuple(map(int, key.split(":")))):
        coords = tuple(map(int, identity.split(":")));raw = worlds[identity]["raw"];owner = raw[0]
        if coords[:2] != tuple(destination[:2]) or not 2 <= owner <= 12:continue
        side = {2: "hostile", 6: "friendly"}.get(civilizations[owner-2][27])
        if side is None:continue
        for hull in range(1, 5):
            quantity = struct.unpack_from("<I", bytes(raw), 23+4*hull)[0]
            add(side, {"source": "world", "world": identity}, 201,
                hull, quantity, dword(0x5E4+4*hull), True)
    for side in ("friendly", "hostile"):battle[side+"_count"] = len(battle[side])
    return battle
