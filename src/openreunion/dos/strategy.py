"""Canonical campaign records and temporary views for recovered routines."""
from copy import deepcopy
from ..core import GameError, integer
from .aliens import read_civilizations, validate_civilizations, fleet_at, store_fleet
from .story import FLAGS as STORY_FLAGS, TIMERS as STORY_TIMERS, count_observatories
from .space_outcome import FLAGS as SPACE_FLAGS
from .ground_outcome import FLAGS as GROUND_FLAGS
from .navigation import FLAGS as NAV_FLAGS, TIMERS as NAV_TIMERS
from .savefile import SaveBlocks

FLAG_FIELDS = {"5d4c": "carrier_failure_reported", "5d62": "hyperspace_allowed"}
TIMER_FIELDS = {"5d4a": "carrier_failure_remaining", "5d52": "research_block_remaining"}
FLAGS = {f"{at:x}" for at in (*STORY_FLAGS, *SPACE_FLAGS, *GROUND_FLAGS, *NAV_FLAGS)}-set(FLAG_FIELDS)-{"23c"}
TIMERS = {f"{at:x}" for at in (*STORY_TIMERS, *NAV_TIMERS)}-set(TIMER_FIELDS)


def imported_strategy(data):
    blocks = SaveBlocks(data)
    return {"civilizations": read_civilizations(data),"system_observatories":[blocks.number(0x481E+2*i,"h") for i in range(8)],
            "flags": {key: blocks.number(int(key, 16), "B") for key in sorted(FLAGS)},
            "timers": {key: blocks.number(int(key, 16), "h") for key in sorted(TIMERS)}}


def validate_strategy(campaign):
    validate_civilizations(campaign["civilizations"])
    for key, expected, minimum, maximum in (("flags", FLAGS, 0, 255), ("timers", TIMERS, -32768, 32767)):
        if not isinstance(campaign[key], dict) or set(campaign[key]) != expected:
            raise GameError("Incomplete canonical campaign "+key+".")
        for value in campaign[key].values():integer(value, "Campaign "+key, minimum=minimum, maximum=maximum)


def relations(campaign):
    return [row[27] if row[27] < 128 else row[27]-256 for row in campaign["civilizations"]]


def navigation_view(campaign):
    """An ephemeral legacy view; no abbreviated alien records are persisted."""
    result = deepcopy(campaign);result["alien_status"] = relations(campaign)
    result["navigation"].update(flags=deepcopy(campaign["flags"]), timers=deepcopy(campaign["timers"]),
        alien_fleets=[[fleet_at(row, slot) for slot in range(1, row[38]+1)] for row in campaign["civilizations"]])
    return result


def commit_navigation(campaign, view):
    campaign["rng"] = view["rng"];campaign["idea_timers"] = list(view["idea_timers"])
    nav = view["navigation"]
    campaign["navigation"] = {key: deepcopy(nav[key]) for key in ("planet_visibility", "encounter", "ending")}
    campaign["flags"] = {key: nav["flags"][key] for key in FLAGS}
    campaign["timers"] = {key: nav["timers"][key] for key in TIMERS}
    for row, status, fleets in zip(campaign["civilizations"], view["alien_status"], nav["alien_fleets"]):
        row[27] = status & 255;row[38] = len(fleets)
        for slot, fleet in enumerate(fleets, 1):store_fleet(row, slot, fleet)


def campaign_work(state):
    """Flatten canonical fields for the independently recovered dispatchers."""
    campaign = state["campaign"]
    work = {key: deepcopy(state[key]) for key in ("resources", "products", "worlds", "buildings", "fleets", "known_systems", "ground_encounter", "space_encounter")}
    work.update({key: deepcopy(campaign[key]) for key in ("rng", "idea_timers", "civilizations", "flags", "timers", "training_remaining", "training_role")})
    work["flags"].update({key: int(campaign[field]) for key, field in FLAG_FIELDS.items()})
    work["flags"]["23c"] = campaign["navigation"]["ending"]
    work["timers"].update({key: campaign[field] for key, field in TIMER_FIELDS.items()})
    work.update(training_phase=campaign["training"]["phase"], encounter=list(campaign["navigation"]["encounter"]),
        system_observatories=list(campaign["system_observatories"]), developer_rank=state["ranks"]["developer"],
        developer_level=state["levels"]["developer"], hunter_allowed=campaign["capabilities"]["hunter"])
    work.update(bar=deepcopy(campaign["bar"]),date=list(state["date"]),planet_visibility=list(campaign["navigation"]["planet_visibility"]))
    return work


def commit_campaign_work(state, work):
    for key in ("resources", "products", "worlds", "buildings", "fleets", "known_systems", "ground_encounter", "space_encounter"):
        state[key] = deepcopy(work[key])
    campaign = state["campaign"]
    campaign["bar"] = deepcopy(work["bar"])
    campaign["navigation"]["planet_visibility"]=list(work["planet_visibility"])
    for key in ("rng", "idea_timers", "civilizations", "training_remaining", "training_role"):
        campaign[key] = deepcopy(work[key])
    campaign["flags"] = {key: work["flags"][key] for key in FLAGS}
    campaign["timers"] = {key: work["timers"][key] for key in TIMERS}
    for key, field in FLAG_FIELDS.items():campaign[field] = bool(work["flags"][key])
    for key, field in TIMER_FIELDS.items():campaign[field] = work["timers"][key]
    campaign["navigation"]["ending"] = work["flags"]["23c"]
    campaign["navigation"]["encounter"] = list(work["encounter"])
    campaign["training"]["phase"] = work["training_phase"]
    campaign["capabilities"]["hunter"] = work["hunter_allowed"]
