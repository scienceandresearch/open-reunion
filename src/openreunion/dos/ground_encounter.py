"""Transactional setup, combat, result and acknowledgment for ground battles.

This adapter owns the boundary between campaign records and the headless battle.
The playable session/save schema adapter can call these same operations.
"""
from copy import deepcopy
from ..core import GameError, integer
from .ground_setup import build_ground_setup, edit_ground_groups
from .ground_battle import initialize_ground_battle
from .ground_controls import ground_input
from .ground_frame import ground_frame
from .ground_casualties import apply_ground_casualties
from .ground_outcome import ground_outcome


def _require(state, phase):
    encounter = state.get("ground_encounter")
    if not isinstance(encounter, dict) or encounter.get("phase") != phase:
        raise GameError(f"Ground battle is not in the {phase} phase.")
    return encounter


def open_ground_encounter(state, destination, rules, *, player_attacking,
                          conquering_owner=None, search_ruins=False):
    if (state.get("ground_encounter") or {}).get("phase", "closed") != "closed":
        raise GameError("A ground battle is already active.")
    if type(player_attacking) is not bool or type(search_ruins) is not bool:
        raise GameError("Invalid ground battle context.")
    if not player_attacking or conquering_owner is not None:
        integer(conquering_owner, "Conquering civilization", minimum=2, maximum=12)
    setup = build_ground_setup(state["fleets"], state["civilizations"], state["worlds"], destination, rules)
    state = deepcopy(state)
    state["ground_encounter"] = {"phase": "setup", "destination": list(destination),
        "player_attacking": player_attacking, "conquering_owner": conquering_owner,
        "search_ruins": search_ruins, "battle": setup, "losses": None, "next_phase": None}
    return state


def edit_ground_encounter(state, rules, action, selection, *, amount=1):
    _require(state, "setup");state = deepcopy(state);encounter = state["ground_encounter"]
    encounter["battle"] = edit_ground_groups(encounter["battle"], rules, action, selection, amount=amount)
    return state


def start_ground_encounter(state, motion):
    _require(state, "setup");state = deepcopy(state);encounter = state["ground_encounter"]
    battle = initialize_ground_battle(encounter["battle"], motion, player_attacking=encounter["player_attacking"])
    battle.update(rng=state["rng"], player_won=False, retreated=False, control_mode=1,
                  selected_group=0, selected_friendly=True, pending_direction=0,
                  friendly_projectiles=[], hostile_projectiles=[])
    encounter["battle"] = battle;encounter["phase"] = "fighting"
    return state


def cancel_ground_encounter(state):
    """Original setup action 42 returns to the map without ground casualties."""
    encounter=_require(state,'setup')
    if not encounter['player_attacking']:
        raise GameError('A defending force cannot cancel the incoming assault.')
    state=deepcopy(state)
    state['ground_encounter']=None
    return state


def _show_ground_result(state):
    """0xCF7C result semantics: casualty writeback, then retreat suppresses win.

    Called only on the fighting-to-result transition. The original's allocation,
    drawing and loss-animation resources have no campaign side effects here.
    """
    encounter = _require(state, "fighting");battle = encounter["battle"]
    if not battle["done"]:raise GameError("Ground battle has not finished.")
    state["fleets"], state["civilizations"], state["worlds"], encounter["losses"] = apply_ground_casualties(
        state["fleets"], state["civilizations"], state["worlds"], encounter["destination"], battle)
    battle["player_won"] = bool(battle["player_won"] and not battle["retreated"])
    state["rng"] = battle["rng"];encounter["phase"] = "result"


def command_ground_encounter(state, motion, rules, action, *, x=None, y=None):
    _require(state, "fighting");state = deepcopy(state);encounter = state["ground_encounter"]
    available = any(row[0] == 18 and row[1:4] == encounter["destination"] and row[6] == 0 and row[8] == 1
                    for row in state["buildings"])
    encounter["battle"], events = ground_input(encounter["battle"], motion, rules, action,
                                               x=x, y=y, base_attack_available=available)
    if encounter["battle"]["done"]:_show_ground_result(state)
    return state, [{"kind": kind, **({} if kind == "ground_result_requested" else
                   {"id": value})} for kind, value in events]


def tick_ground_encounter(state, motion, attack_rules, movement_rules):
    _require(state, "fighting");state = deepcopy(state);encounter = state["ground_encounter"]
    # 0xABD5..0xABF8: mode two suspends simulation and consumes no RNG.
    if encounter["battle"]["control_mode"] == 2:return state, []
    encounter["battle"], events = ground_frame(encounter["battle"], motion, attack_rules, movement_rules)
    encounter["battle"]["retreated"] = False;state["rng"] = encounter["battle"]["rng"]
    if encounter["battle"]["done"]:
        _show_ground_result(state);events.append({"kind": "ground_result_requested"})
    return state, events


def acknowledge_ground_result(state, catalog, alien_rules):
    encounter = _require(state, "result");battle = encounter["battle"]
    state, phase, events = ground_outcome(state, encounter["destination"], catalog, alien_rules,
        player_won=battle["player_won"], player_attacking=encounter["player_attacking"],
        conquering_owner=encounter["conquering_owner"], search_ruins=encounter["search_ruins"])
    state["ground_encounter"]["phase"] = "closed";state["ground_encounter"]["next_phase"] = phase
    return state, phase, events
