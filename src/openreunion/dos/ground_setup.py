"""Ground troop pooling and editable pre-battle groups, independent of UI."""
from copy import deepcopy
import struct
from ..core import GameError, integer
from .aliens import fleet_at
from .catalog import DATA_FILE_OFFSET


def read_ground_rules(data):
    def values(at, count, kind):return list(struct.unpack_from("<"+str(count)+kind, data, DATA_FILE_OFFSET+at))
    return {"equipment_weights": values(2, 3, "i"), "primary": values(0x12, 4, "H"),
            "secondary": values(0x1A, 4, "H"), "group_limits": values(0x32, 4, "h")}


def build_ground_setup(fleets, civilizations, worlds, destination, rules):
    """0x9259..0x99DD: total forces, power pools and initial twenty-group banks.

    Exact world matching is required, including the moon. Native totals use
    wide arithmetic, and allied world troops receive the secondary power
    omitted from the original branch. Campaign input records stay unchanged.
    """
    identity = ":".join(map(str, destination))
    if identity not in worlds:raise GameError("Unknown ground battle world.")
    setup = {}
    for side in ("friendly", "hostile"):
        for field in ("totals", "primary", "secondary"):setup[side+"_"+field] = [0]*4
    def contribute(side, kind, quantity, primary, secondary):
        integer(quantity, "Ground troop quantity", maximum=2**32-1)
        if primary < 0 or secondary < 0:raise GameError("Negative ground equipment power.")
        for field, value in (("totals", quantity), ("primary", primary), ("secondary", secondary)):
            setup[side+"_"+field][kind] += value
    for bank in ("moving", "local"):
        for row in fleets[bank]:
            if row[19:22] != list(destination) or row[22] not in (1, 2, 7) or row[0] not in (1, 5):continue
            for kind in range(4):
                quantity, a, b, c, _ = struct.unpack_from("<5h", bytes(row), 69+10*kind)
                if min(a, b, c) < 0:raise GameError("Negative ground equipment stock.")
                weights = rules["equipment_weights"]
                contribute("friendly", kind, quantity, a*weights[0]+b*weights[1], c*weights[2])
    for civilization in civilizations:
        side = {6: "friendly", 2: "hostile"}.get(civilization[27])
        if side is None:continue
        for slot in range(1, civilization[38]+1):
            row = fleet_at(civilization, slot)
            if row[8:11] != list(destination) or row[2] != 1:continue
            for kind, quantity in enumerate(struct.unpack("<4H", bytes(row[19:27]))):
                contribute(side, kind, quantity, quantity*rules["primary"][kind], quantity*rules["secondary"][kind])
    raw = worlds[identity]["raw"];owner = raw[0]
    side = {6: "friendly", 2: "hostile"}.get(civilizations[owner-2][27]) if 2 <= owner <= 12 else None
    if side:
        for kind, quantity in enumerate(struct.unpack("<4I", bytes(raw[43:59]))):
            contribute(side, kind, quantity, quantity*rules["primary"][kind], quantity*rules["secondary"][kind])
    for side in ("friendly", "hostile"):
        remaining = list(setup[side+"_totals"]);groups = []
        for kind in range(4):
            limit = rules["group_limits"][kind]
            integer(limit, "Ground group limit", minimum=1, maximum=32767)
            while remaining[kind] and len(groups) < 20:
                quantity = min(remaining[kind], limit);remaining[kind] -= quantity
                row = [kind+1, *struct.pack("<h", quantity)]+[0]*36
                if side == "hostile":
                    for at, value in ((8, 3), (9, 0), (10, 1), (11, 1), (15, 1), (18, 0)):row[at] = value
                groups.append(row)
        setup[side+"_groups"] = groups;setup[side+"_reserve"] = remaining
    return setup


def edit_ground_groups(setup, rules, action, selection, *, amount=1):
    """0x8E79..0x9102: add by class or edit/remove a one-based player group.

    Increase/decrease defaults to one troop; larger adjustments are bounded.
    Zero-quantity groups can be refilled or removed. Creating a new empty
    group is rejected instead of consuming one of the twenty group slots.
    """
    integer(amount, "Troop adjustment", minimum=1, maximum=32767)
    setup = deepcopy(setup);groups = setup["friendly_groups"];reserve = setup["friendly_reserve"]
    if action == "add":
        integer(selection, "Ground troop class", minimum=1, maximum=4);kind = selection-1
        if len(groups) >= 20:raise GameError("Ground force already has twenty groups.")
        quantity = min(reserve[kind], rules["group_limits"][kind])
        if quantity <= 0:raise GameError("No troops of this class remain in reserve.")
        groups.append([selection, *struct.pack("<h", quantity)]+[0]*36);reserve[kind] -= quantity
    elif action in ("remove", "increase", "decrease"):
        integer(selection, "Ground group", minimum=1, maximum=len(groups));row = groups[selection-1]
        kind = row[0]-1;quantity = struct.unpack("<h", bytes(row[1:3]))[0]
        if action == "remove":
            reserve[kind] += quantity;groups.pop(selection-1)
        else:
            change = max(0,min(amount, reserve[kind], rules["group_limits"][kind]-quantity)) if action == "increase" else -min(amount, quantity)
            row[1:3] = struct.pack("<h", quantity+change);reserve[kind] -= change
    else:raise GameError("Unknown ground group command.")
    return setup
