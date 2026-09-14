"""Bounded space saves, typed participants and safe motion-table references."""
from collections import Counter
import struct
from ..core import GameError, integer
from .ground_validation import _keys, _array
from .space_combat import RULE_START, RULE_END
from .space_roster import build_space_battle


def validate_space_rules(rules):
    _keys(rules, ("bytes",), "space rules")
    _array(rules["bytes"], RULE_END-RULE_START, "space rule bytes")
    table = bytes(rules["bytes"])
    def byte(at):return table[at-RULE_START]
    for hull in range(1, 5):
        integer(struct.unpack_from("<i", table, 0x5D4+4*hull-RULE_START)[0],
                "Space hull health", minimum=1, maximum=32767)
        for at in (0x7A6+2*hull, 0x7AE+2*hull):
            integer(struct.unpack_from("<h", table, at-RULE_START)[0], "Space movement wait", maximum=32767)
        integer(byte(0x7CB+hull), "Space explosion length", maximum=4)
    directions = {byte(0x72E+9*region+1+index) for region in range(1, 10) for index in range(8)}
    for direction in directions:
        integer(direction, "Space next direction", maximum=8)
        variant = byte(0x6E7+direction)
        integer(variant, "Space path variant", maximum=2)
        for pattern in range(2, 8):
            path = table[variant*120+(pattern-1)*20:variant*120+pattern*20]
            if len(path) != 20 or path[-1] != 0:raise GameError("Space path has no bounded terminator.")
            for code in path:
                integer(code, "Space path code", maximum=9)
                integer(byte(0x6E6+direction*9+code), "Space movement direction", maximum=9)
    for region in range(1, 10):
        for index in range(8):integer(byte(0x72E+9*region+1+index), "Space next direction", maximum=8)


def _origin(origin, world_ids):
    if not isinstance(origin, dict):raise GameError("Invalid space participant origin.")
    source = origin.get("source")
    if source == "player":
        _keys(origin, ("source", "bank", "slot"), "space fleet origin")
        if origin["bank"] not in ("moving", "local"):raise GameError("Invalid space fleet bank.")
        integer(origin["slot"], "Space fleet slot", minimum=1,
                maximum=32 if origin["bank"] == "moving" else 32+len(world_ids))
    elif source == "alien":
        _keys(origin, ("source", "race", "slot"), "space alien origin")
        integer(origin["race"], "Space alien race", minimum=2, maximum=12)
        integer(origin["slot"], "Space alien slot", minimum=1, maximum=7)
    elif source == "world":
        _keys(origin, ("source", "world"), "space world origin")
        if not isinstance(origin["world"], str) or origin["world"] not in world_ids:
            raise GameError("Unknown space participant world.")
    else:raise GameError("Unknown space participant source.")


def _signature(units):
    return Counter((tuple(sorted(unit["origin"].items())), tuple(unit["raw"][:4])) for unit in units)


def validate_space_encounter(encounter, state, rules, cinema_rules=None):
    if encounter is None:return
    if rules is None:raise GameError("Space battle tables are missing; re-extract the catalog.")
    validate_space_rules(rules)
    _keys(encounter, ("phase", "destination", "player_attacking", "ground_requested", "conquering_owner",
        "search_ruins", "initial_seed", "fighter_level", "battle", "retreated", "player_won", "losses", "next_phase", "radar", "cinema"), "space encounter")
    if encounter["cinema"] is not None:
        if cinema_rules is None:raise GameError("Saved battle needs cinematic tables; re-extract the content.")
        from .space_cinema import validate_cinema,validate_cinema_view
        _keys(encounter["cinema"],("controller","view"),"battle cinematic")
        validate_cinema(encounter["cinema"]["controller"],cinema_rules)
        validate_cinema_view(encounter["cinema"]["view"],cinema_rules)
    from .space_presentation import validate_radar_calls
    validate_radar_calls(encounter["radar"], rules)
    phase = encounter["phase"]
    if not isinstance(phase, str) or phase not in ("fighting", "result", "closed"):
        raise GameError("Invalid space encounter phase.")
    if phase=="fighting" and encounter["cinema"] is not None and not encounter["cinema"]["controller"]["sequence"]:
        raise GameError("An active cinematic battle has no sequence.")
    _array(encounter["destination"], 3, "space destination")
    if ":".join(map(str, encounter["destination"])) not in state["worlds"]:
        raise GameError("Unknown space battle destination.")
    for key in ("player_attacking", "ground_requested", "search_ruins", "retreated", "player_won"):
        if type(encounter[key]) is not bool:raise GameError("Invalid space encounter flag.")
    owner = encounter["conquering_owner"]
    if owner is not None or encounter["ground_requested"] and not encounter["player_attacking"]:
        integer(owner, "Conquering civilization", minimum=2, maximum=12)
    integer(encounter["initial_seed"], "Initial space seed", maximum=2**32-1)
    integer(encounter["fighter_level"], "Space commander level", maximum=32767)
    next_phase = "ground_setup" if encounter["ground_requested"] and encounter["player_won"] == encounter["player_attacking"] else "starmap"
    if encounter["next_phase"] != (next_phase if phase == "closed" else None):
        raise GameError("Space battle continuation disagrees with its result.")
    if phase == "fighting":
        if encounter["losses"] is not None or encounter["retreated"] or encounter["player_won"]:
            raise GameError("An active space battle already has a result.")
    else:
        _keys(encounter["losses"], ("friendly", "hostile"), "space casualties")
        for row in encounter["losses"].values():_array(row, 4, "space casualties", maximum=2**63-1)
    battle = encounter["battle"]
    directions = {rules["bytes"][0x72E+9*region+1+index-RULE_START]
                  for region in range(1, 10) for index in range(8)}
    _keys(battle, ("rng", "frame", "done", "explosions", "instant_kill", "friendly", "hostile",
                  "friendly_count", "hostile_count"), "space battle")
    for key in ("done", "explosions", "instant_kill"):
        if type(battle[key]) is not bool:raise GameError("Invalid space battle flag.")
    integer(battle["rng"], "Space battle seed", maximum=2**32-1)
    integer(battle["frame"], "Space battle frame", maximum=4)
    if phase != "closed" and battle["rng"] != state["campaign"]["rng"]:
        raise GameError("Space battle and campaign seeds disagree.")
    if battle["instant_kill"] and not state["assisted"]:
        raise GameError("An instant battle victory requires an assisted campaign.")
    if battle["done"] != (phase != "fighting"):raise GameError("Space completion and phase disagree.")
    for side in ("friendly", "hostile"):
        units = battle[side]
        if not isinstance(units, list) or len(units) > 500:raise GameError("Space roster exceeds 500 ships.")
        count = battle[side+"_count"];integer(count, "Active space ships", maximum=len(units))
        for index, unit in enumerate(units):
            _keys(unit, ("raw", "origin"), "space ship")
            raw = unit["raw"];_array(raw, 12, "space ship bytes");_origin(unit["origin"], state["worlds"])
            integer(raw[1], "Space hull", minimum=1, maximum=4)
            hp = struct.unpack("<h", bytes(raw[4:6]))[0]
            maximum_hp = struct.unpack_from("<i", bytes(rules["bytes"]), 0x5D4+4*raw[1]-RULE_START)[0]
            if (hp > 0) != (index < count) or hp > maximum_hp:raise GameError("Space health and active roster disagree.")
            integer(raw[8], "Space pattern", minimum=2, maximum=7)
            integer(raw[9], "Space direction", maximum=8)
            if raw[9] not in directions:raise GameError("Space ship has an unreachable direction.")
            if index < count:integer(raw[10], "Space path step", maximum=18)
            else:
                length = rules["bytes"][0x7CB+raw[1]-RULE_START]
                integer(raw[10], "Space explosion step", minimum=1, maximum=length+1)
                if phase != "fighting" and not encounter["retreated"] and raw[10] <= length:
                    raise GameError("Space result precedes an explosion.")
    if phase != "fighting":
        if encounter["player_won"] != (battle["friendly_count"] > 0 and not encounter["retreated"]):
            raise GameError("Space winner disagrees with surviving ships.")
        if not encounter["retreated"] and (battle["explosions"] or battle["friendly_count"] and battle["hostile_count"]):
            raise GameError("Space result precedes combat completion.")
    else:
        if encounter["fighter_level"] != state["levels"]["fighter"]:
            raise GameError("Space commander changed during combat.")
        original = build_space_battle(state["fleets"], state["campaign"]["civilizations"], state["worlds"],
            encounter["destination"], encounter["fighter_level"], encounter["initial_seed"], rules)
        for side in ("friendly", "hostile"):
            if _signature(original[side]) != _signature(battle[side]):
                raise GameError("Space roster disagrees with campaign forces.")
        if battle["frame"] == 0 and battle != dict(original, instant_kill=battle["instant_kill"]):
            raise GameError("Space battle changed before its first frame.")
    if phase != "closed":
        if state["campaign_phase"] != "starmap":raise GameError("A terminal campaign has an active space battle.")
        if (state["ground_encounter"] or {}).get("phase", "closed") != "closed":
            raise GameError("Space and ground battles cannot run simultaneously.")
