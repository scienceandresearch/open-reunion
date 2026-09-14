"""Ground frame attack pass, including deferred rocket creation."""
from copy import deepcopy
import struct
from ..core import GameError
from .campaign import random_bounded
from .catalog import DATA_FILE_OFFSET
from .ground_geometry import can_attack, ground_distances, nearest_ground_target, pixel_position
from .ground_battle import ground_group


def read_ground_attack_rules(data):
    return {"cooldowns": list(struct.unpack_from("<4h", data, DATA_FILE_OFFSET+0x22)),
            "target_coefficients": list(struct.unpack_from("<5h", data, DATA_FILE_OFFSET+0x2A)),
            "animation_lengths": [data[DATA_FILE_OFFSET+0x86+6*i] for i in range(9)]}


def cardinal_direction(first, second):
    """0xB575..0xB5CE: choose the larger axis, horizontal on ties."""
    dx, dy = first[0]-second[0], first[1]-second[1]
    if abs(dx) >= abs(dy):return 1 if dx > 0 else 3
    return 2 if dy > 0 else 4


def projectile_heading(first, second):
    """0xB5CE..0xB6DF: sixteen sprite headings; zero for coincident points."""
    dx, dy = abs(second[0]-first[0]), abs(second[1]-first[1])
    if dx == dy == 0:return 0
    base = (cardinal_direction(first, second)-1)*4
    if base in (0, 8):
        value = (5*dx+4*(second[1]-first[1]))//(2*dx)
        offset = 4-value if base == 0 else value
    else:
        value = (5*dy+4*(second[0]-first[0]))//(2*dy)
        offset = value if base == 4 else 4-value
    return (base+offset+2)%16


def set_ground_animation(row, animation, rules):
    """0xB6DF..0xB723: animation kind, remaining frames and frame wait."""
    row[12:15] = [animation, rules["animation_lengths"][animation], 3]


def ground_attack_pass(battle, motion, rules):
    """0xBA55..0xBF77: copied state plus pending sound ID for this frame.

    Adds to each side's projectile list; movement, impacts, animation playback
    and completion are later frame stages. A projectile stores eighteen raw
    bytes to preserve the recovered interpolation and power layout.
    """
    battle = deepcopy(battle);sound = 0
    for side in ("friendly", "hostile"):battle.setdefault(side+"_projectiles", [])
    battle["rng"], reverse = random_bounded(battle["rng"], 2)
    sides = ("hostile", "friendly") if reverse else ("friendly", "hostile")
    quantity = lambda row: struct.unpack("<h", bytes(row[1:3]))[0]
    for side in sides:
        opponent_side = "hostile" if side == "friendly" else "friendly"
        groups, opponents = battle[side+"_groups"], battle[opponent_side+"_groups"]
        for index, row in enumerate(groups, 1):
            count = quantity(row)
            if count <= 0:continue
            if row[15] == 3:
                selected = row[16]
                ordered = ground_group(battle, opponent_side, selected)
                if ordered is None or quantity(ordered) <= 0:
                    if side == "friendly":row[15] = 1
                    else:row[16] = nearest_ground_target(groups, opponents, index, motion)
            cooldown = struct.unpack("<h", bytes(row[6:8]))[0]
            if opponents and row[12] == 0 and cooldown == 0:
                target = 0
                if row[15] == 3:
                    ordered = ground_group(battle, opponent_side, row[16])
                    if ordered is not None and can_attack(row, ordered, motion):target = row[16]
                if target == 0:
                    for candidate, enemy in enumerate(opponents, 1):
                        if quantity(enemy) > 0 and can_attack(row, enemy, motion):target = candidate
                enemy = ground_group(battle, opponent_side, target)
                if enemy is not None and quantity(enemy) > 0:
                    kind = row[0]-1
                    total = battle[side+"_totals"][kind]
                    if total <= 0:raise GameError("A ground attacker has no original class total.")
                    ranged_rocket = row[0] == 4 and ground_distances(row, enemy, motion)[1] > 1
                    pool = battle[side+("_secondary" if ranged_rocket else "_primary")][kind]
                    if pool < 0:raise GameError("Negative ground attack power.")
                    if row[0] == 3:
                        # DOS pools aircraft Missiles but never reads that
                        # secondary power. Use both fitted weapon pools in
                        # their existing direct attack, for either side.
                        missiles = battle[side+"_secondary"][kind]
                        if missiles < 0:raise GameError("Negative ground attack power.")
                        pool += missiles
                    power = count*pool//total
                    if ranged_rocket:
                        start, end = pixel_position(row, motion), pixel_position(enemy, motion)
                        cells = (tuple(row[4:6]), tuple(enemy[4:6]))
                        # Opposite subcell positions may make rockets eligible
                        # within the same cell; DOS divides by zero on its grid
                        # heading calculation. Use their distinct pixel points.
                        heading = projectile_heading(*(cells if cells[0] != cells[1] else (start, end)))
                        duration = ground_distances(row, enemy, motion)[1]*8
                        projectile = list(struct.pack("<7hI", *start, *end, 1, duration, heading, min(power, 2**32-1)))
                        battle[side+"_projectiles"].append(projectile)
                        set_ground_animation(row, 5, rules);sound = 5
                    else:
                        damage = max(1, min(15, rules["target_coefficients"][enemy[0]-1]*power//500))
                        left = max(0, quantity(enemy)-damage);enemy[1:3] = struct.pack("<h", left)
                        set_ground_animation(row, row[0], rules)
                        set_ground_animation(enemy, 7 if left == 0 else 8, rules)
                        sound = enemy[0]+5 if left == 0 else row[0]
                        if row[9] == 0:row[8] = cardinal_direction(row[4:6], enemy[4:6])
                    cooldown = rules["cooldowns"][kind]
            if cooldown > 0:cooldown -= 1
            row[6:8] = struct.pack("<h", cooldown)
    return battle, sound
