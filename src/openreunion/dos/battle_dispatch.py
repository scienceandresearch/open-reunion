"""Player attack eligibility and requests, recovered from DC98..DFC6.

The starmap roster at 2C232..2C4A8 establishes location and status first.
Requests carry identities instead of mutable selected-world DOS pointers.
"""
from ..core import GameError, integer
from .aliens import fleet_at


def _signed(value):
    return value if value < 128 else value-256


def player_attack_request(state, fleet_index, *, target_race=None, target_slot=None):
    """Validate an attack without changing diplomacy, RNG or campaign records.

    Omit the alien identity to assault the Army's exact world. A fleet attack
    engages the primary-wide space roster, with no subsequent ground request.
    DOS's displayed state-3 groups cannot enter the combat roster; reject them
    here, as well as fleets still traveling to their stored destination.
    """
    integer(fleet_index, "Fleet index", maximum=len(state["fleets"]["moving"])-1)
    army = state["fleets"]["moving"][fleet_index]
    if army[0] != 1:
        raise GameError("Select an Army fleet to attack.")
    if army[22] not in (1, 2):
        raise GameError("The Army must arrive before attacking.")
    if state["levels"]["fighter"] == 0:
        raise GameError("Hire a fighter commander before attacking.")
    civilizations = state["campaign"]["civilizations"]
    if target_race is None and target_slot is None:
        destination = list(army[19:22])
        world = state["worlds"].get(":".join(map(str, destination)))
        if world is None:
            raise GameError("The Army is not at a known world.")
        owner = world["raw"][0]
        if not 2 <= owner <= 12:
            raise GameError("An assault requires an alien-owned world.")
        if _signed(world["raw"][12]) < 40:
            raise GameError("Survey this world further before ordering an assault.")
        if _signed(civilizations[owner-2][27]) >= 6:
            raise GameError("This civilization is allied; an attack is unavailable.")
        if state["ranks"]["fighter"] <= 1:
            raise GameError("A ground assault requires a rank 2 or 3 fighter commander.")
        return {"destination": destination, "hostile_race": owner, "ground_requested": True}
    integer(target_race, "Target civilization", minimum=2, maximum=12)
    civilization = civilizations[target_race-2]
    integer(target_slot, "Alien fleet slot", minimum=1, maximum=civilization[38])
    target = fleet_at(civilization, target_slot)
    if target[0] <= 1 or target[2] != 1 or target[8:10] != army[19:21]:
        raise GameError("Select a stationary alien fleet around the Army's planet.")
    if _signed(civilization[27]) >= 6:
        raise GameError("This civilization is allied; an attack is unavailable.")
    destination = [*army[19:21], 0]
    if ":".join(map(str, destination)) not in state["worlds"]:
        raise GameError("The target planet is unknown.")
    return {"destination": destination, "hostile_race": target_race, "ground_requested": False}
