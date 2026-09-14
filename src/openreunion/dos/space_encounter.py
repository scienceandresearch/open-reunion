"""Campaign transactions for space combat and its ground-assault handoff."""
from copy import deepcopy
from ..core import GameError, integer
from .space_roster import build_space_battle
from .space_combat import space_tick, survivor_roster
from .space_casualties import apply_casualties
from .space_outcome import space_outcome
from .ground_encounter import open_ground_encounter
from .space_presentation import space_snapshot_plan


def _require(state, phase):
    encounter = state.get("space_encounter")
    if not isinstance(encounter, dict) or encounter.get("phase") != phase:
        raise GameError(f"Space battle is not in the {phase} phase.")
    return encounter


def open_space_encounter(state, destination, fighter_level, rules, *, player_attacking,
                         ground_requested=False, conquering_owner=None, search_ruins=False, cinema_rules=None):
    for key in ("space_encounter", "ground_encounter"):
        if (state.get(key) or {}).get("phase", "closed") != "closed":
            raise GameError("A battle is already active.")
    for flag in (player_attacking, ground_requested, search_ruins):
        if type(flag) is not bool:raise GameError("Invalid space battle context.")
    if conquering_owner is not None or ground_requested and not player_attacking:
        integer(conquering_owner, "Conquering civilization", minimum=2, maximum=12)
    if not isinstance(destination, (list, tuple)) or len(destination) != 3:
        raise GameError("Invalid space battle destination.")
    for value in destination:integer(value, "Battle coordinate", maximum=255)
    battle = build_space_battle(state["fleets"], state["civilizations"], state["worlds"],
                               destination, fighter_level, state["rng"], rules)
    state = deepcopy(state)
    state["space_encounter"] = {"phase": "fighting", "destination": list(destination),
        "player_attacking": player_attacking, "ground_requested": ground_requested,
        "conquering_owner": conquering_owner, "search_ruins": search_ruins,
        "initial_seed": state["rng"], "fighter_level": fighter_level, "battle": battle,
        "retreated": False, "player_won": False, "losses": None, "next_phase": None,
        "radar": space_snapshot_plan(battle, rules), "cinema": None}
    state["rng"] = battle["rng"]
    if cinema_rules is not None:
        # DOS initializes the screen with one numerical frame, then selects
        # the first cinematic. This draw order affects the shared random seed.
        calls=[];battle=space_tick(battle,rules,render_calls=calls)
        state["space_encounter"].update(battle=battle,radar=calls);state["rng"]=battle["rng"]
        if battle["done"]:_show_result(state)
        from .space_cinema import start_cinema
        controller,seed=start_cinema(state["rng"],cinema_rules)
        state["space_encounter"]["cinema"]={"controller":controller,"view":{"picture":None,"clears":[],"black":False}}
        state["rng"]=battle["rng"]=seed
    return state


def _show_result(state):
    encounter = _require(state, "fighting");battle = encounter["battle"]
    if not battle["done"]:raise GameError("Space battle has not finished.")
    # 0x17608..0x17627: write casualties, then test surviving FRIENDLY ships.
    # An empty battle is a loss; retreat overrides a surviving friendly force.
    state["fleets"], state["civilizations"], state["worlds"], encounter["losses"] = apply_casualties(
        state["fleets"], state["civilizations"], state["worlds"], encounter["destination"], survivor_roster(battle))
    encounter["player_won"] = battle["friendly_count"] > 0 and not encounter["retreated"]
    encounter["phase"] = "result";state["rng"] = battle["rng"]


def tick_space_encounter(state, rules, *, render_calls=None, cinema_rules=None):
    _require(state, "fighting");state = deepcopy(state);encounter = state["space_encounter"]
    calls = []
    encounter["battle"] = space_tick(encounter["battle"], rules, render_calls=calls)
    if render_calls is not None:render_calls.extend(calls)
    if encounter["battle"]["frame"] == 1:encounter["radar"] = calls
    state["rng"] = encounter["battle"]["rng"]
    if encounter["battle"]["done"]:
        if encounter["cinema"] is not None:encounter["cinema"]["controller"]["sequence"]=0
        _show_result(state)
        return state, [{"kind": "control_layout", "id": 30}, {"kind": "space_result_requested"}]
    if encounter["cinema"] is not None:
        if cinema_rules is None:raise GameError("Cinematic rules are required to continue this battle.")
        from .space_cinema import cinema_tick,advance_cinema_view
        cinematic=encounter["cinema"]
        cinematic["controller"],seed,events=cinema_tick(cinematic["controller"],state["rng"],cinema_rules)
        cinematic["view"]=advance_cinema_view(cinematic["view"],events)
        state["rng"]=encounter["battle"]["rng"]=seed
        return state,events
    return state, []


def retreat_space_encounter(state):
    _require(state, "fighting");state = deepcopy(state);encounter = state["space_encounter"]
    encounter["retreated"] = True;encounter["battle"]["done"] = True
    if encounter["cinema"] is not None:encounter["cinema"]["controller"]["sequence"]=0
    _show_result(state)
    return state, [{"kind": "control_layout", "id": 30}, {"kind": "space_result_requested"}]


def acknowledge_space_result(state, ground_rules):
    encounter = _require(state, "result")
    state, phase, events = space_outcome(state, encounter["destination"],
        player_won=encounter["player_won"], player_attacking=encounter["player_attacking"],
        ground_requested=encounter["ground_requested"])
    state["space_encounter"]["phase"] = "closed"
    state["space_encounter"]["next_phase"] = phase
    if phase == "ground_setup":
        state = open_ground_encounter(state, encounter["destination"], ground_rules,
            player_attacking=encounter["player_attacking"], conquering_owner=encounter["conquering_owner"],
            search_ruins=encounter["search_ruins"])
    return state, phase, events
