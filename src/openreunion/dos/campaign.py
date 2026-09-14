"""Recovered research discoveries and survey progression; additional events follow."""
import struct

from ..core import GameError, integer

from .rules import i16
from .savefile import SaveBlocks


def random_bounded(seed,limit):
    """Borland Random(word), file 0x3F003 and seed step 0x3F060."""
    seed=(seed*0x08088405+1)&0xFFFFFFFF
    return seed,(seed*(limit&0xFFFF))>>32


def imported_campaign(data):
    from .bar import read_bar
    from .navigation import imported_navigation
    from .strategy import imported_strategy
    blocks=SaveBlocks(data)
    return {"bar":read_bar(data),"rng":1994,"idea_timers":list(struct.unpack("<35h",blocks.read(0x91A0,70))),
            "commander_levels":list(struct.unpack("<12H",blocks.read(0x57CC,24))),
            "developer_skill_choices":list(blocks.read(0x57F0,12)),
            "research_block_remaining":blocks.number(0x5D52,"h"),
            "training_remaining":blocks.number(0x5D9C,"h"),"training_role":blocks.number(0x5D9E),
            "training":{"course":blocks.number(0x5DA0),"phase":blocks.number(0x91EA),"quote":None},
            "carrier_failure_remaining":blocks.number(0x5D4A,"h"),"carrier_failure_reported":bool(blocks.number(0x5D4C,"B")),
            "hyperspace_allowed":bool(blocks.number(0x5D62,"B")),
            "capabilities":{"transport":blocks.number(0xA2D4,"B"),"hunter":blocks.number(0xA2D6,"B"),
                            "transfer":blocks.number(0xA2D7,"B"),"pirate":blocks.number(0xA2D8,"B"),"carrier":blocks.number(0xA2D9,"B")},
            "navigation":{key: value for key,value in imported_navigation(data).items() if key in ("planet_visibility","encounter","ending")},
            **imported_strategy(data)}


def validate_campaign(campaign):
    keys={"rng","idea_timers","research_block_remaining","training_remaining","training_role",
          "carrier_failure_remaining","carrier_failure_reported","hyperspace_allowed","capabilities","civilizations","flags","timers",
          "commander_levels","developer_skill_choices","navigation","training","system_observatories","bar"}
    if not isinstance(campaign,dict) or set(campaign)!=keys:
        raise GameError("Invalid campaign fields.")
    from .strategy import validate_strategy, navigation_view
    from .navigation import validate_navigation, FLAGS, TIMERS
    validate_strategy(campaign)
    from .bar import validate_bar
    validate_bar(campaign["bar"])
    nav=campaign["navigation"]
    if not isinstance(nav,dict) or set(nav)!={"planet_visibility","encounter","ending"}:
        raise GameError("Invalid canonical navigation state.")
    view=navigation_view(campaign)["navigation"]
    view["flags"]={f"{key:x}":view["flags"][f"{key:x}"] for key in FLAGS}
    view["timers"]={f"{key:x}":view["timers"][f"{key:x}"] for key in TIMERS}
    validate_navigation(view)
    from .commanders import validate_training
    validate_training(campaign["training"])
    integer(campaign["rng"],"Random seed",maximum=2**32-1)
    for key in ("research_block_remaining","training_remaining","carrier_failure_remaining"):
        integer(campaign[key],key,maximum=32767)
    integer(campaign["training_role"],"Training role",maximum=4)
    for key in ("carrier_failure_reported","hyperspace_allowed"):
        if type(campaign[key]) is not bool:
            raise GameError("Invalid campaign flag.")
    for key,count,minimum,maximum in (("idea_timers",35,-1,32767),
                                     ("system_observatories",8,0,1000),
                                     ("commander_levels",12,0,90),("developer_skill_choices",12,0,255)):
        if not isinstance(campaign[key],list) or len(campaign[key])!=count:
            raise GameError(f"Invalid {key} table.")
        for value in campaign[key]:
            integer(value,key,minimum=minimum,maximum=maximum)
    if not isinstance(campaign["capabilities"],dict) or set(campaign["capabilities"])!={"transport","hunter","transfer","pirate","carrier"}:
        raise GameError("Invalid capability table.")
    for value in campaign["capabilities"].values():
        integer(value,"Capability",maximum=1)


def schedule_idea(campaign,products,product_id,base,spread):
    """0x1F9DE: only a locked product with the -1 sentinel is scheduled."""
    index=product_id-1
    if products[index]["research_state"]==0 and campaign["idea_timers"][index]==-1:
        campaign["rng"],roll=random_bounded(campaign["rng"],spread)
        campaign["idea_timers"][index]=i16(base+roll)


def discovery_tick(campaign,products,developer_level):
    """0x14087..0x14156: returns discovered product IDs and message IDs."""
    discovered,messages=[],[]
    if developer_level<=0 or campaign["research_block_remaining"]!=0 or (campaign["training_remaining"]!=0 and campaign["training_role"]==4):
        return discovered,messages
    for index,left in enumerate(campaign["idea_timers"]):
        if left<=0:
            continue
        left-=1
        if index==14 and products[8]["research_state"]!=5 and left==0:
            left=10
        if index==33 and left==50:
            messages.append(33)
        if left==0:
            products[index]["research_state"]=1
            discovered.append(index+1)
        campaign["idea_timers"][index]=left
    return discovered,messages


def research_completed(campaign,products,product_id):
    """Gameplay branches 0x10991..0x10A33; returns original MESSAGE.TXT IDs."""
    messages=[]
    if product_id==5:
        schedule_idea(campaign,products,6,30,10)
        messages.append(3)
    if product_id==14:
        schedule_idea(campaign,products,15,50,70)
        messages.append(12)
    if product_id==13:
        schedule_idea(campaign,products,15,200,30)
    if product_id==23:
        schedule_idea(campaign,products,24,50,70)
        messages.append(22)
    if product_id in (4,6):
        campaign["capabilities"]["transport"]=1
    if product_id==10:
        campaign["capabilities"]["hunter"]=1
    if product_id==6:
        campaign["capabilities"]["transfer"]=1
    if product_id==4:
        campaign["capabilities"]["carrier"]=1
    return messages


def campaign_counters_tick(campaign,products):
    """Recovered early satellite failure and scientist-return counters."""
    messages=[]
    if not campaign["carrier_failure_reported"] and campaign["carrier_failure_remaining"]>0:
        campaign["carrier_failure_remaining"]-=1
        if campaign["carrier_failure_remaining"]==0:
            campaign["carrier_failure_reported"]=True
            schedule_idea(campaign,products,4,10,10)
            # DOS requests scene 9 here; screen dispatch 0x7F18..0x7F25 emits
            # MESSAGE.TXT record 1 before that scene plays.
            messages.append(1)
    if campaign["research_block_remaining"]>0:
        campaign["research_block_remaining"]-=1
        if campaign["research_block_remaining"]==0:
            messages.append(8)
            # 0x14209 calls the locked-only completion helper for product 9.
            if products[8]["research_state"]==0:
                products[8]["research_state"]=5
                products[8]["research_remaining"]=0
    return messages


def survey_step(raw,seed,alien_status=0):
    """Daily survey arithmetic 0x11B25..0x11BC8, before discovery side effects."""
    raw=list(raw)
    satellite=raw[8] if raw[8]<128 else raw[8]-256
    if satellite<0:
        satellite+=10
        raw[8]=satellite&255
    increment=0
    if satellite>0:
        seed,roll=random_bounded(seed,5)
        increment=roll+2
    if raw[10]>0 and raw[0]==1:
        seed,roll=random_bounded(seed,5)
        increment=roll+3
    if raw[6]!=0 and raw[0]==1:
        seed,roll=random_bounded(seed,5)
        increment=roll+4
    if raw[0]>=2 and alien_status==0 and (raw[12] if raw[12]<128 else raw[12]-256)>=31:
        increment=0
    progress=(raw[12]+increment)&255
    if (progress if progress<128 else progress-256)>60:
        progress=60
    raw[12]=progress
    return raw,seed,increment
