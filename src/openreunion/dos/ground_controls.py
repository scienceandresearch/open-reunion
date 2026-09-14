"""Ground selection and orders using original 320-by-200 input coordinates."""
from copy import deepcopy
import struct
from ..core import GameError, integer
from .catalog import DATA_FILE_OFFSET
from .ground_battle import ground_group
from .ground_geometry import pixel_position


def read_ground_control_rules(data):
    return {"base_offsets": [list(data[DATA_FILE_OFFSET+0xB8+2*i:DATA_FILE_OFFSET+0xBA+2*i]) for i in range(2)]}


def nearest_ground_selection(battle, motion, rules, x, y, side="both"):
    """0xB723..0xB9D0: first nearest living center within squared distance 500.

    Troops are scanned before the two separate bases. Both-side results encode
    hostile indices with +100; a single-side search returns its plain index.
    """
    integer(x, "Ground cursor x", minimum=-32768, maximum=32767)
    integer(y, "Ground cursor y", minimum=-32768, maximum=32767)
    if side not in ("friendly", "hostile", "both"):raise GameError("Invalid ground selection side.")
    sides = ("friendly", "hostile") if side == "both" else (side,)
    best = 1000000;selected = 0
    def consider(row, key, index, center):
        nonlocal best, selected
        if row is None or struct.unpack("<h", bytes(row[1:3]))[0] <= 0:return
        distance = (center[0]-x)**2+(center[1]-y)**2
        if distance < best:
            best = distance;selected = index+(100 if side == "both" and key == "hostile" else 0)
    for key in sides:
        for index, row in enumerate(battle[key+"_groups"], 1):
            if struct.unpack("<h", bytes(row[1:3]))[0] <= 0:continue
            px, py = pixel_position(row, motion)
            consider(row, key, index, (px+2, py+51))
    for key in sides:
        row = battle.get(key+"_special")
        if row is not None:
            offset = rules["base_offsets"][int(battle["player_attacking"])][0 if key == "friendly" else 1]
            consider(row, key, 21, (64+16*row[4]+offset, 52+16*row[5]+offset))
    return selected if best <= 500 else 0


def ground_input(battle, motion, rules, action, *, x=None, y=None, base_attack_available=False):
    """0x7871..0x7AEF: copied battle and ordered cursor/notice requests.

    A click uses the original pointer-hotspot adjustments. Move coordinates are
    clamped to the logical board, fixing unchecked negative/right-edge writes.
    The caller computes base_attack_available from completed operating building
    18 at the battle world. Base orders are retained, but the separate ordinary
    troop frame does not simulate a base weapon.
    """
    if action not in ("click", "move", "attack", "cancel", "context_cancel", "retreat"):
        raise GameError("Unknown ground control action.")
    if battle.get("done", False):raise GameError("This ground battle has already ended.")
    if type(base_attack_available) is not bool:raise GameError("Invalid base attack availability.")
    if action == "click":
        integer(x, "Ground cursor x", minimum=-32768, maximum=32767)
        integer(y, "Ground cursor y", minimum=-32768, maximum=32767)
    battle = deepcopy(battle);events = []
    battle.setdefault("control_mode", 1);battle.setdefault("selected_group", 0)
    battle.setdefault("selected_friendly", True);battle.setdefault("retreated", False)
    mode = battle["control_mode"]
    if mode not in (1, 2, 3, 4):raise GameError("Invalid ground control mode.")
    def notice(value):events.append(("ground_notice", value))
    def cursor(value):events.append(("ground_cursor", value))
    def selected(allow_base=False):
        index = battle["selected_group"]
        if type(index) is not int or not battle["selected_friendly"] or index == 21 and not allow_base:return None
        row = ground_group(battle, "friendly", index)
        return row if row is not None and struct.unpack("<h", bytes(row[1:3]))[0] > 0 else None
    if action == "click":
        if mode == 1:
            code = nearest_ground_selection(battle, motion, rules, x-6, y-6)
            if code:
                previous = (battle["selected_group"], battle["selected_friendly"])
                battle["selected_group"] = code if code < 100 else code-100
                battle["selected_friendly"] = code < 100;cursor(0)
                if previous != (battle["selected_group"], battle["selected_friendly"]):notice(20)
        elif mode in (3, 4):
            row = selected(allow_base=mode == 4 and battle["player_attacking"] and base_attack_available)
            battle["control_mode"] = 1;cursor(0)
            if row is None:notice(22)
            elif mode == 3:
                divide16 = lambda value: (abs(value)//16)*(1 if value >= 0 else -1)
                cx = max(0, min(15, divide16(x-64+6)))
                cy = max(0, min(8, divide16(y-52+6)))
                row[15:19] = [2, cx, cy, 0];notice(21)
            else:
                target = nearest_ground_selection(battle, motion, rules, x, y, "hostile")
                if target:row[15] = 3;row[16] = target;row[18] = 0;notice(21)
                else:notice(22)
    elif action == "move":
        if selected() is not None:battle["control_mode"] = 3;cursor(5);notice(30)
        else:notice(22)
    elif action == "attack":
        if selected(allow_base=battle["player_attacking"] and base_attack_available) is not None:
            battle["control_mode"] = 4;cursor(5);notice(31)
        else:notice(22)
    elif action in ("cancel", "context_cancel"):
        if action == "cancel" or mode > 1:notice(22)
        battle["control_mode"] = 1;cursor(0)
    else:
        battle["done"] = True;battle["retreated"] = True
        events.extend((("control_layout", 30), ("ground_result_requested", 0)))
    return battle, events
