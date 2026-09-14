"""Ground frame troop movement, queued orders and occupancy reservations."""
from copy import deepcopy
import struct
from ..core import GameError
from .catalog import DATA_FILE_OFFSET
from .ground_geometry import can_attack
from .ground_pathfinding import ground_path_direction
from .ground_battle import ground_group


def read_ground_movement_rules(data):
    return {"waits": list(struct.unpack_from("<4H", data, DATA_FILE_OFFSET+0x80))}


def ground_movement_pass(battle, motion, rules):
    """0xBF77..0xC447: copied battle with pixel steps and reserved cells.

    Both the current and next cell belong to a moving troop. Friendly groups
    always move first, regardless of the randomized order of the attack pass.
    """
    battle = deepcopy(battle);board = battle["board"]
    inside = lambda cell: 0 <= cell[0] < 16 and 0 <= cell[1] < 9
    adjacent = lambda row: (row[4]+motion["x"][row[8]], row[5]+motion["y"][row[8]])
    occupant = lambda cell: board[cell[0]][cell[1]] if inside(cell) else -1
    battle.setdefault("pending_direction", 0)
    for side_index, side in enumerate(("friendly", "hostile")):
        for index, row in enumerate(battle[side+"_groups"], 1):
            if struct.unpack("<h", bytes(row[1:3]))[0] <= 0:continue
            if not inside(row[4:6]) or not 1 <= row[8] <= 4:
                raise GameError("Ground troop has an invalid position or direction.")
            own_id = 100*side_index+index;next_cell = adjacent(row);next_occupant = occupant(next_cell)
            if row[11] > 0:row[11] -= 1;continue
            # A corrupt saved moving state must not wrap a byte coordinate or
            # write beyond the battlefield when completing its next pixel step.
            if row[9] and not inside(next_cell):row[9] = 0;row[10] = 0
            if row[9] and next_occupant not in (0, own_id) and row[15] <= 1:continue
            if next_occupant in (0, own_id):row[10] += 1
            if row[10] == 16 or not row[9]:
                board[row[4]][row[5]] = 0
                if row[9]:
                    board[next_cell[0]][next_cell[1]] = 0
                    row[4:6] = next_cell
                row[9] = 1
                if row[15] == 1:
                    if row[18] > 20:raise GameError("Ground movement queue exceeds twenty directions.")
                    if row[18] > 0:
                        length = row[18];row[19:18+length] = row[20:19+length];row[18] -= 1
                    battle["pending_direction"] = row[19] if row[18] else 0
                if row[15] == 2:
                    battle["pending_direction"] = ground_path_direction(board, row[4:6], row[16:18])
                    if row[4:6] == row[16:18]:row[15] = 1
                if row[15] == 3:
                    target = ground_group(battle, "hostile" if side == "friendly" else "friendly", row[16])
                    if target is None:
                        row[15] = 1;battle["pending_direction"] = 0
                    else:
                        battle["pending_direction"] = ground_path_direction(board, row[4:6], target[4:6])
                        step = row[10];row[10] = max(0, step-1)
                        if can_attack(row, target, motion):row[9] = 0
                        row[10] = step
                direction = battle["pending_direction"]
                if direction > 0:
                    if direction > 4:raise GameError("Invalid queued ground movement direction.")
                    row[8] = direction
                else:row[9] = 0
                next_cell = adjacent(row)
                if row[9] and occupant(next_cell) not in (0, own_id):row[9] = 0
                board[row[4]][row[5]] = own_id
                if row[9]:board[next_cell[0]][next_cell[1]] = own_id
                row[10] = 0
            row[11] = rules["waits"][row[0]-1]
    return battle
