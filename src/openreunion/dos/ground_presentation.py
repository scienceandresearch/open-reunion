"""Recovered ground sprite selection and placement, independent of drawing.

Plans consume the post-animation battle snapshot. Coordinates use the original
320-pixel screen width and a 151-pixel battlefield viewport beginning at y=49.
Rendering a snapshot never advances animation, combat or the random generator.
"""
import struct
from ..core import GameError, integer
from .catalog import DATA_FILE_OFFSET
from .ground_battle import ground_group
from .ground_geometry import pixel_position


def read_ground_presentation(data):
    animations = [list(struct.unpack_from("<3H", data, DATA_FILE_OFFSET+0x82+6*i)) for i in range(9)]
    names = []
    for kind in range(1, 6):
        at = DATA_FILE_OFFSET+0x5A13+9*kind
        names.append(data[at+1:at+1+data[at]].decode("ascii").strip())
    result = {"animations": animations, "names": names}
    validate_ground_presentation(result)
    return result


def validate_ground_presentation(rules):
    if not isinstance(rules, dict) or set(rules)!={"animations", "names"}:
        raise GameError("Invalid ground presentation tables.")
    rows = rules["animations"]
    if not isinstance(rows, list) or len(rows)!=9:raise GameError("Invalid ground animation table.")
    for row in rows:
        if not isinstance(row, list) or len(row)!=3:raise GameError("Invalid ground animation row.")
        for value, label, maximum in zip(row, ("Animation frame", "Animation bank", "Animation length"), (20, 4, 20)):
            integer(value, label, minimum=1, maximum=maximum)
        if row[0]+row[2]-1>20:raise GameError("Ground animation exceeds its sprite bank.")
    names = rules["names"]
    if not isinstance(names, list) or len(names)!=5:raise GameError("Invalid ground unit names.")
    if any(not isinstance(name, str) or not 1<=len(name)<=8 or not name.isascii() or not name.isprintable() for name in names):
        raise GameError("Invalid ground unit name.")


def ground_render_plan(battle, motion, presentation, controls):
    """0xAAF0..0xABD5, 0xAC32..0xB012 and selection helper 0xA85C.

    Return ordered sprite calls after the recovered animation state update.
    Correct the original's persistent intact base art after destruction; its
    existing explosion still plays. Bases never enter troop attack/movement loops.
    """
    calls = []
    def sprite(atlas, frame, bank, x, y, direction=1):
        calls.append({"atlas": atlas, "frame": frame, "bank": bank, "x": x, "y": y, "direction": direction})
    def base(source, x, width, transparent=True):
        calls.append({"atlas": "terrain", "source": source, "x": x, "y": 67,
                      "width": width, "height": width, "transparent": transparent})
    quantity = lambda row: struct.unpack("<h", bytes(row[1:3]))[0]
    if quantity(battle["friendly_special"])>0:
        if battle["player_attacking"]:base([64, 33], 64, 16)
        else:base([64, 0], 64, 32, False)
    if quantity(battle["hostile_special"])>0:
        if battle["player_attacking"]:base([192, 0], 288, 32)
        else:base([132, 33], 304, 16)
    animations = presentation["animations"]
    for side, bank in (("friendly", 1), ("hostile", 2)):
        for row in battle[side+"_groups"]:
            alive = quantity(row)>0;kind = row[12]
            if not alive and kind==0:continue
            frame, sprite_bank = 1+5*(row[0]-1), bank
            if kind:
                start, sprite_bank, length = animations[kind]
                frame = start+length-row[13]
                if side=="hostile":
                    if kind<=4:sprite_bank += 1
                    if kind==5:frame += 9
            x, y = pixel_position(row, motion)
            if kind in (7, 8):
                if alive or row[13]>5:sprite("units", 1+5*(row[0]-1), bank, x, y, row[8])
                sprite("effects", frame, sprite_bank, x, y)
            elif alive:sprite("units", frame, sprite_bank, x, y, row[8])
    for side_index, side in enumerate(("friendly", "hostile")):
        row = battle[side+"_special"];kind = row[12]
        if kind not in (7, 8):continue
        start, bank, length = animations[kind]
        offset = controls["base_offsets"][int(battle["player_attacking"])][side_index]
        sprite("effects", start+length-row[13], bank, 64+16*row[4]+offset, 3+16*row[5]+offset)
    selected_side = "friendly" if battle["selected_friendly"] else "hostile"
    index = battle["selected_group"]
    row = ground_group(battle, selected_side, index)
    if row is not None and (index!=21 or quantity(row)>0):
        def selected_position(record, selected_index, side):
            x, y = pixel_position(record, motion)
            offset = controls["base_offsets"][int(battle["player_attacking"])][int(side=="hostile")] if selected_index==21 else 0
            return x+offset, y+offset
        sprite("effects", 15, 1 if selected_side=="friendly" else 2, *selected_position(row, index, selected_side))
        if selected_side=="friendly":
            if row[15]==2:sprite("effects", 16, 2, 64+16*row[16], 3+16*row[17])
            if row[15]==3:
                target = ground_group(battle, "hostile", row[16])
                # DOS reads before the array on target zero. Stale target
                # overlays must not invent a marker at an unrelated location.
                if target is not None and (row[16]!=21 or quantity(target)>0):sprite("effects", 16, 1, *selected_position(target, row[16], "hostile"))
    for side in ("friendly", "hostile"):
        for row in battle[side+"_projectiles"]:
            sx, sy, ex, ey, step, duration, heading, _ = struct.unpack("<7hI", bytes(row))
            if duration<=0:raise GameError("Cannot render a zero-duration projectile.")
            divide = lambda value: (abs(value)//duration)*(1 if value>=0 else -1)
            calls.append({"atlas": "projectiles", "heading": heading,
                          "x": sx+divide((ex-sx)*step), "y": sy+divide((ey-sy)*step)})
    return calls
