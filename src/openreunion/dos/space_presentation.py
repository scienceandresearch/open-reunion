"""Original space radar scanlines and read-only ship/explosion draw requests."""
import struct
from ..core import GameError, integer
from .ground_validation import _keys, _array
from .space_combat import RULE_START


def read_space_presentation(data):
    """Read the straight-line copy geometry at file 0x31797..0x31E50.

    This parses only the five instruction forms used by that blitter. It does
    not execute arbitrary code or need a disassembler at extraction/runtime.
    """
    if len(data) < 0x31E53:raise GameError("Truncated radar geometry.")
    position = 0x31797;source = destination = count = 0;spans = []
    while position < 0x31E50:
        op = data[position:position+2]
        if op in (b"\x81\xc6", b"\x81\xc7", b"\x83\xc6", b"\x83\xc7"):
            wide = op[0] == 0x81
            value = struct.unpack_from("<h" if wide else "<b", data, position+2)[0]
            if op[1] == 0xC6:source += value
            else:destination += value
            position += 4 if wide else 3
        elif data[position] == 0xB9:
            count = struct.unpack_from("<H", data, position+1)[0];position += 3
        elif op == b"\xf3\xa5" or data[position] == 0xA4:
            size = count*2 if op == b"\xf3\xa5" else 1
            if spans and spans[-1][0]+spans[-1][2] == source and spans[-1][1]+spans[-1][2] == destination:
                spans[-1][2] += size
            else:spans.append([source, destination, size])
            source += size;destination += size;position += 2 if op == b"\xf3\xa5" else 1
            if op == b"\xf3\xa5":count = 0
        else:raise GameError(f"Unsupported radar geometry instruction at {position:#x}.")
    result = {"radar_spans": spans};validate_space_presentation(result);return result


def validate_space_presentation(presentation):
    _keys(presentation, ("radar_spans",), "space presentation")
    spans = presentation["radar_spans"]
    if not isinstance(spans, list) or not 1 <= len(spans) <= 151:raise GameError("Invalid radar scanlines.")
    previous = -1
    for span in spans:
        _array(span, 3, "radar scanline", maximum=320*151-1)
        source, destination, count = span
        integer(count, "Radar scanline width", minimum=1, maximum=160)
        if source+count > 160*151 or destination+count > 320*151:
            raise GameError("Radar scanline escapes its viewport.")
        if source%160+count > 160 or destination%320+count > 160 or destination <= previous:
            raise GameError("Radar scanlines overlap or cross the display boundary.")
        previous = destination+count-1


def space_snapshot_plan(battle, rules):
    """Redraw a saved snapshot without consuming a frame or random draw.

    Running frames supply requests from the actual simulation draw points.
    Old saves without recorded draws use their current positions and remaining
    explosion steps. Completed explosions are never revived by another death.
    """
    calls = []
    for side in ("friendly", "hostile"):
        for unit in battle[side][:battle[side+"_count"]]:
            raw = unit["raw"]
            calls.append({"kind": "ship", "side": side, "hull": raw[1], "x": raw[6], "y": raw[7]})
    if battle["explosions"]:
        for side in ("friendly", "hostile"):
            for unit in battle[side][battle[side+"_count"]:]:
                raw = unit["raw"];step = raw[10]
                if 1 <= step <= rules["bytes"][0x7CB+raw[1]-RULE_START]:
                    calls.append({"kind": "explosion", "hull": raw[1], "step": step, "x": raw[6], "y": raw[7]})
    return calls


def validate_radar_calls(calls, rules):
    if not isinstance(calls, list) or len(calls) > 2000:raise GameError("Invalid saved radar frame.")
    for call in calls:
        if not isinstance(call, dict):raise GameError("Invalid radar sprite.")
        kind = call.get("kind")
        _keys(call, ("kind", "hull", "x", "y", "side" if kind == "ship" else "step"), "radar sprite")
        for key in ("x", "y"):integer(call[key], "Radar position", maximum=255)
        integer(call["hull"], "Radar hull", minimum=1, maximum=4)
        if kind == "ship":
            if call["side"] not in ("friendly", "hostile"):raise GameError("Invalid radar side.")
        elif kind == "explosion":
            integer(call["step"], "Radar explosion step", minimum=1,
                    maximum=min(4, rules["bytes"][0x7CB+call["hull"]-RULE_START]))
        else:raise GameError("Unknown radar sprite.")
