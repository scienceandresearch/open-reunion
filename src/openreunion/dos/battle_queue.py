"""Saved alien requests; completed hourly passes never overwrite battle identity."""
from ..core import GameError, integer
from .aliens import fleet_at


def validate_battle_requests(state):
    requests=state["battle_requests"]
    if not isinstance(requests,list) or len(requests)>77:
        raise GameError("Invalid pending battle queue.")
    seen=set()
    for request in requests:
        if not isinstance(request,dict) or set(request)!={"race","slot","world","ground","special"}:
            raise GameError("Invalid pending battle request.")
        integer(request["race"],"Attacking civilization",minimum=2,maximum=12)
        integer(request["slot"],"Attacking fleet slot",minimum=1,maximum=7)
        world=request["world"]
        if not isinstance(world,list) or len(world)!=3:
            raise GameError("Invalid pending battle destination.")
        for value in world:integer(value,"Battle coordinate",maximum=255)
        if ":".join(map(str,world)) not in state["worlds"]:
            raise GameError("Unknown pending battle world.")
        if any(type(request[key]) is not bool for key in ("ground","special")):
            raise GameError("Invalid pending battle mode.")
        identity=(request["race"],request["slot"])
        if identity in seen:raise GameError("Duplicate pending alien fleet attack.")
        seen.add(identity)
    active=any((state[key] or {}).get("phase","closed")!="closed" for key in ("space_encounter","ground_encounter"))
    waiting=state.get('active_scene') is not None or bool(state['presentation_requests'])
    if requests and (not active and not waiting and state["active_dialog"] is None or state["campaign_phase"]!="starmap"):
        raise GameError("Pending battles require an ongoing campaign encounter.")


def current_battle_request(state,request):
    """Recheck after earlier combat may have withdrawn or destroyed this fleet.

    An expired mission was already consumed by alien_hour. No timer advances
    and no relationship change is invented here. A former ground target that
    has ceased to be player-owned can still have a qualifying space defense.
    """
    civilization=state["campaign"]["civilizations"][request["race"]-2]
    if request["slot"]>civilization[38]:return None
    row=fleet_at(civilization,request["slot"])
    if row[2]!=1 or row[8:11]!=request["world"]:return None
    world=state["worlds"][":".join(map(str,request["world"]))]["raw"]
    ground=request["ground"] and world[0]==1
    defenders=any(player[0] in (1,3) and player[19:21]==request["world"][:2]
                  and player[22] in (1,2) for player in state["fleets"]["moving"])
    if not ground and not defenders:return None
    return {**request,"world":list(request["world"]),"ground":ground}
