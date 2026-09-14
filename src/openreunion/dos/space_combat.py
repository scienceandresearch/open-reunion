"""Original space-combat movement, attacks, removals and explosion lifetime.

Roster construction and client integration remain separate. Each unit retains
an explicit origin for casualty writeback; no gameplay identity uses DOS IDs.
"""
from copy import deepcopy
import struct
from ..core import GameError
from .campaign import random_bounded
from .catalog import DATA_FILE_OFFSET


RULE_START = 0x56B
RULE_END = 0x7D8


def read_space_rules(data):
    return {"bytes": list(data[DATA_FILE_OFFSET+RULE_START:DATA_FILE_OFFSET+RULE_END])}


def space_tick(battle, rules, *, render_calls=None):
    """0x1671D..0x17010: one frame, with simulation every fourth frame.

    Banks retain the original active prefix/dead suffix ordering. Removing a
    killed unit swaps in the last active unit; its origin moves with it.
    """
    battle = deepcopy(battle)
    battle["frame"] += 1
    if battle["frame"] > 4:battle["frame"] = 1
    if battle["frame"] != 1:return battle
    battle["explosions"] = False

    def byte(address):
        index = address-RULE_START
        if not 0 <= index < len(rules["bytes"]):raise GameError("Combat motion table index is out of range.")
        return rules["bytes"][index]

    def signed_byte(address):
        value = byte(address)
        return value if value < 128 else value-256

    def word(address):
        return struct.unpack("<h", bytes([byte(address), byte(address+1)]))[0]

    def roll(limit):
        battle["rng"], value = random_bounded(battle["rng"], limit)
        return value

    def move(raw, enemy):
        if raw[11]:
            raw[11] -= 1
            return
        def path():
            return byte(0x56B+byte(0x6E7+raw[9])*120+(raw[8]-1)*20+raw[10])
        direction = byte(0x6E6+raw[9]*9+path())
        raw[6] = (raw[6]+signed_byte((0x793 if enemy else 0x789)+direction)) & 255
        raw[7] = (raw[7]+signed_byte(0x79D+direction)) & 255
        raw[10] = (raw[10]+1) & 255
        if path() == 0:
            column = 0 if raw[6] < 50 else 2 if raw[6] > 110 else 1
            if enemy:column = 2-column
            row = 0 if raw[7] < 40 else 2 if raw[7] > 110 else 1
            region = column+3*row+1
            raw[8] = 2+roll(6)
            raw[9] = byte(0x72E+9*region+1+roll(8))
            raw[10] = 1
        raw[11] = (word(0x7A6+2*raw[1])+roll(word(0x7AE+2*raw[1]))) & 255

    for side, target_side in (("friendly", "hostile"), ("hostile", "friendly")):
        for index in range(battle[side+"_count"]):
            raw = battle[side][index]["raw"]
            if struct.unpack("<h", bytes(raw[4:6]))[0] <= 0:continue
            if render_calls is not None:
                render_calls.append({"kind": "ship", "side": side, "hull": raw[1], "x": raw[6], "y": raw[7]})
            move(raw, side == "hostile")
            target_count = battle[target_side+"_count"]
            if target_count == 0:
                battle["done"] = True
                continue
            target_index = roll(target_count)
            if roll(100) > 10:continue
            target = battle[target_side][target_index]["raw"]
            damage = struct.unpack("<H", bytes(raw[2:4]))[0]
            if raw[1] <= 2 and target[1] > 2:damage //= 3
            hp = struct.unpack("<h", bytes(target[4:6]))[0]-damage
            # A large valid unsigned attack must not wrap a destroyed target
            # back into positive signed health.
            hp = max(-32768, hp)
            if raw[1] <= 2 and target[1] <= 2:
                if word(0x7CA+4*raw[1]+2*target[1]) >= roll(100):hp = 0
            if side == "friendly" and battle["instant_kill"]:hp = 0
            target[4:6] = struct.pack("<h", hp)
            if hp <= 0:
                target[10] = 1
                last = target_count-1
                battle[target_side][target_index], battle[target_side][last] = battle[target_side][last], battle[target_side][target_index]
                battle[target_side+"_count"] -= 1
    for side in ("friendly", "hostile"):
        for unit in battle[side][battle[side+"_count"]:]:
            raw = unit["raw"]
            if byte(0x7CB+raw[1]) >= raw[10]:
                if render_calls is not None:
                    render_calls.append({"kind": "explosion", "hull": raw[1], "step": raw[10], "x": raw[6], "y": raw[7]})
                raw[10] = (raw[10]+1) & 255
                battle["explosions"] = True
    if battle["friendly_count"] == 0 or battle["hostile_count"] == 0:battle["done"] = True
    if battle["explosions"]:battle["done"] = False
    return battle


def survivor_roster(battle):
    """Keep typed origins when transferring live combat entries to casualties."""
    return [dict(deepcopy(unit["origin"]), hull=unit["raw"][1])
            for side in ("friendly", "hostile") for unit in battle[side][:battle[side+"_count"]]]
