"""Complete numerical ground frame, including state formerly inside rendering."""
from copy import deepcopy
import struct
from .ground_attacks import ground_attack_pass, set_ground_animation
from .ground_battle import ground_group, clear_destroyed_base_reservations
from .ground_movement import ground_movement_pass


def quantity(row):
    return struct.unpack("<h", bytes(row[1:3]))[0]


def ground_projectile_pass(battle, rules, sound=0):
    """0xC447..0xC673: advance rockets; impact the current endpoint occupant."""
    battle = deepcopy(battle)
    for side in ("friendly", "hostile"):
        remaining = []
        for row in battle.setdefault(side+"_projectiles", []):
            sx, sy, ex, ey, step, duration, heading, power = struct.unpack("<7hI", bytes(row))
            if step >= duration:
                # Original signed division truncates toward zero.
                divide16 = lambda value: (abs(value)//16)*(1 if value >= 0 else -1)
                cx, cy = divide16(ex-64), divide16(ey-3)
                code = battle["board"][cx][cy] if 0 <= cx < 16 and 0 <= cy < 9 else 0
                enemy_side = "hostile" if side == "friendly" else "friendly"
                enemy = ground_group(battle, enemy_side, code-100 if side == "friendly" else code) if (
                    code > 100 if side == "friendly" else 0 < code < 100) else None
                if enemy is not None:
                    damage = max(1, min(15, rules["target_coefficients"][enemy[0]-1]*power//180))
                    left = max(0, quantity(enemy)-damage);enemy[1:3] = struct.pack("<h", left)
                    set_ground_animation(enemy, 7 if left == 0 else 8, rules)
                    sound = enemy[0]+5 if left == 0 else 7
            else:
                row[8:10] = struct.pack("<h", step+1);remaining.append(row)
        battle[side+"_projectiles"] = remaining
    return battle, sound


def ground_completion_pass(battle):
    """0xC681..0xC84F: remove dead reservations and check completion pre-animation."""
    battle = deepcopy(battle);battle.setdefault("done", False);battle.setdefault("player_won", False)
    for column in battle["board"]:
        for cy, code in enumerate(column):
            if code == 0:continue
            side = "hostile" if code >= 100 else "friendly"
            row = ground_group(battle, side, code-100 if side == "hostile" else code)
            if row is None or quantity(row) == 0:column[cy] = 0
    friendly_dead = all(quantity(row) <= 0 for row in battle["friendly_groups"])
    hostile_dead = all(quantity(row) <= 0 for row in battle["hostile_groups"])
    if battle.get("instant_kill", False):battle["done"] = True;battle["player_won"] = True
    if friendly_dead or hostile_dead:battle["done"] = True;battle["player_won"] = hostile_dead
    if battle["done"]:
        for side in ("friendly", "hostile"):
            if battle.get(side+"_projectiles") or any(quantity(row) == 0 and row[13] > 0 for row in battle[side+"_groups"]):
                battle["done"] = False
    return battle


def ground_animation_pass(battle):
    """State effects of 0xABF8..0xB042: base footprints, animation and selection."""
    battle = deepcopy(battle);board = battle["board"]
    clear_destroyed_base_reservations(battle)
    if quantity(battle["friendly_special"])>0:
        board[0][4] = 21
        if not battle["player_attacking"]:
            for cx, cy in ((0, 5), (1, 4), (1, 5)):board[cx][cy] = 21
    if quantity(battle["hostile_special"])>0:
        board[15][4] = 121
        if battle["player_attacking"]:
            for cx, cy in ((14, 4), (14, 5), (15, 5)):board[cx][cy] = 121
    def advance(row):
        if row[14] > 0:row[14] -= 1
        else:
            if row[13] > 0:row[13] -= 1
            if row[13] == 0:row[12] = 0
            else:row[14] = 1
    for side in ("friendly", "hostile"):
        for index, row in enumerate(battle[side+"_groups"], 1):
            if quantity(row) <= 0 and row[12] == 0:continue
            advance(row)
            if quantity(row) == 0 and battle.get("selected_group", 0) == index and battle.get("selected_friendly", True) == (side == "friendly"):
                battle["selected_group"] = 0
        special = battle.get(side+"_special")
        if special is not None and special[12] > 0:advance(special)
    return battle


def ground_frame(battle, motion, attack_rules, movement_rules):
    """0xBA55..0xC869: one simulation frame and presentation event requests.

    No drawing or host clock is required. Completion is checked before animation
    playback, so the last death animation finishes one frame before done becomes
    true. Sound IDs and the completion control layout are returned for the client.
    """
    battle=deepcopy(battle)
    # A pre-fix saved battle can still contain phantom base cells. Remove them
    # before pathfinding; ordinary death cleanup keeps its original end-of-frame order.
    clear_destroyed_base_reservations(battle)
    was_done = battle.get("done", False)
    battle, sound = ground_attack_pass(battle, motion, attack_rules)
    battle = ground_movement_pass(battle, motion, movement_rules)
    battle, sound = ground_projectile_pass(battle, attack_rules, sound)
    battle = ground_completion_pass(battle)
    battle = ground_animation_pass(battle)
    events = []
    if sound > 0:events.append({"kind": "ground_sound", "id": sound})
    if not was_done and battle["done"]:events.append({"kind": "control_layout", "id": 30})
    return battle, events
