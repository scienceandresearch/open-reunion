"""Recovered ordered story timers, pending full campaign/client integration.

The dispatcher work record retains DS-addressed flags/timers and complete
civilization records. Presentation requests are returned in executable order;
the client must queue and acknowledge them rather than discard them.
"""
from copy import deepcopy

from .aliens import (attack_order, destroy_civilization, fleet_at, route_fleet,
                     settle_world, store_fleet, system_disaster)
from .campaign import random_bounded, schedule_idea
from .savefile import SaveBlocks


FLAGS = tuple(int(value, 16) for value in (
    "5d3e 5d3f 5d48 5d4c 5d50 5d56 5d5a 5d5e 5d62 5d66 5d6c 5d6d "
    "5d70 5d71 5d74 5d75 5d78 5d7c 5d80 5d84 5d88 5d90 5d94 5d95 5d98 1b5 1eb"
).split())
TIMERS = tuple(int(value, 16) for value in (
    "5d40 5d4a 5d4e 5d52 5d54 5d58 5d5c 5d60 5d64 5d6a 5d6e "
    "5d72 5d76 5d7a 5d7e 5d82 5d86 5d8a 5d8e 5d92 5d96"
).split())


def read_story_fields(data):
    """Import every field used by the timer and scripted-response dispatchers."""
    blocks = SaveBlocks(data)
    return {
        "flags": {f"{at:x}": blocks.number(at, "B") for at in FLAGS},
        "timers": {f"{at:x}": blocks.number(at, "h") for at in TIMERS},
        "encounter": [blocks.number(at) for at in (0x5D42, 0x5D44, 0x5D46)],
        "system_observatories": [blocks.number(0x481E + 2*i, "h") for i in range(8)],
    }


def count_observatories(buildings):
    """0x124F8..0x12571: count completed type-six buildings per system.

    The story prerequisite at DS 0x4824 is this count for system four,
    not a colony count or a visibility flag. Power and staffing are not tested.
    """
    counts = [0]*8
    for row in buildings:
        if row[0] == 6 and row[6] == 0:
            counts[row[1]-1] += 1
    return counts


def story_hour(state, rules):
    """0x14157..0x147F6: one complete timer pass, after idea discovery.

    Returns (new work record, ordered (kind, id) presentation requests).
    No player choices or battles execute here. Attack helpers issue orders;
    the separate alien movement/action dispatcher must resolve them later.
    """
    state = deepcopy(state)
    flags, timers = state["flags"], state["timers"]
    products = state["products"]
    events = []

    def roll(base, spread):
        state["rng"], value = random_bounded(state["rng"], spread)
        return base + value

    def expires(timer, flag=None, condition=True):
        if condition and (flag is None or not flags[flag]) and timers[timer] > 0:
            timers[timer] -= 1
            return timers[timer] == 0
        return False

    def relationship(race):
        value = state["civilizations"][race-2][27]
        return value if value < 128 else value-256

    def notice(number):
        events.append(("message", number))

    def dialog(number):
        events.append(("dialog", number))

    def scene(number):
        events.append(("scene", number))

    def route(race, slot, destination):
        civilization = state["civilizations"][race-2]
        row, state["rng"] = route_fleet(fleet_at(civilization, slot), destination, state["rng"])
        store_fleet(civilization, slot, row)

    def attack(race, slot, force=False):
        civilization = state["civilizations"][race-2]
        row, state["rng"] = attack_order(fleet_at(civilization, slot), (1, 5, 0),
                                         civilization[16], 2, state["rng"], force_kind=force)
        store_fleet(civilization, slot, row)
        if force:
            # DOS activates the dormant slot's kind but omits the counted
            # fleet bound. Movement and battle dispatch would never visit it.
            civilization[38] = max(civilization[38], slot)

    def encounter(race, slot, base, spread):
        timers["5d40"] = roll(base, spread)
        state["encounter"] = [race, slot, 2]

    def destroy(race):
        state["civilizations"], state["worlds"] = destroy_civilization(
            state["civilizations"], state["worlds"], race)

    if expires("5d4a", "5d4c"):
        flags["5d4c"] = 1
        schedule_idea(state, products, 4, 10, 10)
        scene(9)

    if expires("5d4e", "5d50", state["developer_rank"] > 0 and relationship(2) > 2
               and not (state["training_remaining"] != 0 and state["training_role"] == 4)):
        if products[7]["research_state"] == 5:
            dialog(2)
        else:
            notice(6)

    if expires("5d52"):
        notice(8)
        # The return completes a still-locked invention; the earlier partial
        # counter port omitted this reward. Other research states are retained.
        if products[8]["research_state"] == 0:
            products[8]["research_state"] = 5
            products[8]["research_remaining"] = 0

    if expires("5d54", "5d56", relationship(2) > 2):
        if products[7]["research_state"] == 5:
            notice(9)
            dialog(3)
        else:
            notice(6)
        flags["5d56"] = 1

    if expires("5d58", "5d5a", relationship(2) == 0 or relationship(2) > 2):
        if products[7]["research_state"] == 5:
            notice(10)
            dialog(4)
        else:
            notice(6)
        flags["5d5a"] = 1
        if not flags["5d5e"]:
            timers["5d5c"] = roll(200, 50)
        route(3, 1, (1, 7, 0))

    if expires("5d5c", "5d5e"):
        if relationship(2) > 0:
            notice(11)
            scene(1)
        destroy(2)
        raw, state["rng"] = settle_world(state["worlds"]["1:7:0"]["raw"], 3, state["rng"],
                                          rules, morgrul_late=bool(flags["5d6c"]))
        state["worlds"]["1:7:0"]["raw"] = raw
        for flag, timer, base, spread in (("5d66", "5d64", 600, 50),
                                         ("5d62", "5d60", 300, 50),
                                         ("5d6c", "5d6a", 1800, 200)):
            if not flags[flag]:
                timers[timer] = roll(base, spread)
        flags["5d5e"] = 1
        state["training_phase"] = 2

    if expires("5d64", "5d66"):
        attack(3, 1)
        flags["5d66"] = 1

    if expires("5d60", "5d62", products[13]["research_state"] > 0 and state["developer_level"] > 0
               and timers["5d52"] == 0 and state["training_role"] != 4):
        notice(30)
        flags["5d62"] = 1

    if expires("5d6a", "5d6c"):
        attack(3, 2)
        flags["5d6c"] = flags["5d6d"] = 1
        if not flags["5d74"]:
            timers["5d72"] = roll(1100, 50)
        if not flags["5d70"]:
            timers["5d6e"] = roll(100, 20)

    if expires("5d6e", "5d70", products[11]["research_state"] == 5):
        notice(17)
        flags["5d70"] = flags["5d71"] = 1

    if expires("5d72", "5d74"):
        attack(3, 3)
        flags["5d74"] = flags["5d75"] = 1
        if not flags["5d88"]:
            timers["5d86"] = roll(50, 50)
        encounter(3, 6, 8000, 500)

    if expires("5d76", "5d78"):
        # Consume the contact's one-shot event, but honor the prison bargain.
        # DOS ignores its saved diversion latch and restores the canceled plan.
        flags["5d78"] = 1
        if not flags["5d3f"]:
            flags["5d3e"] = 1
            if not flags["5d7c"]:
                timers["5d7a"] = roll(4000, 50)
            route(4, 2, (2, 5, 0))

    if expires("5d7a", "5d7c"):
        flags["5d7c"] = 1
        flags["5d3e"] = 0
        if not flags["5d80"]:
            timers["5d7e"] = roll(300, 50)
        state["civilizations"][2][27] = 2
        route(3, 4, (2, 5, 0))
        notice(24)
        destroy(5)

    if expires("5d7e", "5d80"):
        flags["5d80"] = 1
        attack(3, 4)
        attack(4, 2)

    if expires("5d82", "5d84", relationship(5) > 2):
        flags["5d84"] = 1
        dialog(7)

    if expires("5d86", "5d88"):
        flags["5d88"] = 1
        notice(20)

    if expires("5d8a", condition=state["known_systems"][2] >= 128):
        state["known_systems"][2] = 0
        notice(37)

    if expires("5d92", "5d94", state["system_observatories"][3] > 0):
        flags["5d94"] = flags["5d95"] = 1
        notice(25)
        if not flags["5d90"]:
            timers["5d8e"] = roll(1000, 100)

    if expires("5d8e", "5d90"):
        flags["5d90"] = 1
        timers["5d92"] = 0
        notice(27)
        scene(7)
        (state["civilizations"], state["worlds"], state["buildings"], state["fleets"], state["rng"]) = system_disaster(
            state["civilizations"], state["worlds"], state["buildings"], state["fleets"], state["rng"])

    if expires("5d96", "5d98"):
        attack(7, 1)
        flags["5d98"] = 1
        encounter(8, 1, 1000, 500)

    if expires("5d40"):
        race, slot, _ = state["encounter"]
        if relationship(race) == 2:
            attack(race, slot, True)
        # Scheduling changes this shared record. Keep original sequential
        # tests: a just-created follow-up must not trigger a later chain early.
        timers["5d40"] = 0
        for race, slot, next_race, next_slot, base, spread in (
            (3, 6, 3, 7, 4500, 100), (7, 6, 7, 7, 3000, 500),
            (7, 5, 7, 6, 1500, 500), (8, 1, 7, 5, 1000, 500),
            (12, 4, 12, 5, 2000, 500), (12, 3, 12, 4, 2000, 500),
        ):
            if state["encounter"][:2] == [race, slot]:
                encounter(next_race, next_slot, base, spread)

    return state, events
