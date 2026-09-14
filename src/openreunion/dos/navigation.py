"""Recovered fleet travel, first contact and landing discoveries."""
import struct
from ..core import GameError,integer
from .campaign import random_bounded,schedule_idea
from .rules import i16
from .savefile import SaveBlocks

# Unmapped story fields keep their DS address until their timed dispatchers are recovered.
FLAGS=(0x5D48,0x5D50,0x5D56,0x5D5A,0x5D5E,0x5D71,0x5D78,0x5D84,0x5D90,0x5D94,0x5D95,0x5D98)
TIMERS=(0x5D40,0x5D4E,0x5D54,0x5D58,0x5D5C,0x5D76,0x5D82,0x5D8E,0x5D92,0x5D96)


def imported_navigation(data):
    blocks=SaveBlocks(data)
    fleets=[]
    for i in range(11):
        row=blocks.read(0x6BCE+228*i,228)
        count=row[38]
        if count>7:raise GameError("Invalid original alien fleet count.")
        fleets.append([list(row[39+27*j:66+27*j]) for j in range(count)])
    return {"planet_visibility":list(blocks.read(0x47D6,64)),"alien_fleets":fleets,
            "flags":{f"{a:x}":blocks.number(a,"B") for a in FLAGS},
            "timers":{f"{a:x}":blocks.number(a,"h") for a in TIMERS},
            "encounter":[blocks.number(a) for a in (0x5D42,0x5D44,0x5D46)],
            "ending":blocks.number(0x23C,"B")}


def validate_navigation(nav):
    if not isinstance(nav,dict) or set(nav)!={"planet_visibility","alien_fleets","flags","timers","encounter","ending"}:
        raise GameError("Invalid navigation state; reimport the original save.")
    for key,count,maximum in (("planet_visibility",64,255),("encounter",3,65535)):
        if not isinstance(nav[key],list) or len(nav[key])!=count:raise GameError("Invalid navigation table.")
        for v in nav[key]:integer(v,key,maximum=maximum)
    integer(nav["ending"],"Ending state",maximum=255)
    for key,addresses,minimum,maximum in (("flags",FLAGS,0,255),("timers",TIMERS,-32768,32767)):
        if not isinstance(nav[key],dict) or set(nav[key])!={f"{a:x}" for a in addresses}:raise GameError("Invalid travel story fields.")
        for v in nav[key].values():integer(v,key,minimum=minimum,maximum=maximum)
    if not isinstance(nav["alien_fleets"],list) or len(nav["alien_fleets"])!=11:raise GameError("Invalid alien fleets.")
    for rows in nav["alien_fleets"]:
        if not isinstance(rows,list) or len(rows)>7:raise GameError("Invalid alien fleet count.")
        for row in rows:
            if not isinstance(row,list) or len(row)!=27:raise GameError("Invalid alien fleet record.")
            for v in row:integer(v,"Alien fleet byte",maximum=255)


def ship_count(row,catalog):
    # 0x21E6B: Army ground troops cannot move independently; Pirate uses both banks.
    categories=[c for c in catalog["fleet_rules"][row[0]-1]["categories"] if c["id"]!=3]
    counts=[struct.unpack_from("<h",bytes(row),29+40*(c["bank"]-1)+10*i)[0]
            for c in categories for i in range(len(c["hulls"]))]
    if any(v<0 for v in counts):raise GameError("Negative ship count.")
    return sum(counts)


def interstellar_capable(row,products,pilot_rank,destination_system):
    """0xE1A0..0xE21B: ship capability and pilot qualification."""
    word=lambda at:struct.unpack_from("<h",bytes(row),at)[0]
    capable=(row[0] in (1,3) and (word(49)>0 or word(59)>0) or row[0]==2 and word(59)>0
             or row[0]==4 and (products[13]["research_state"]==5 or products[14]["research_state"]==5))
    return bool(capable and (row[0]==4 or pilot_rank==3 or pilot_rank==2 and row[19]<=3 and destination_system<=3))


def depart(row,destination,seed):
    """0x1F4D6..0x1F5C3; location words become the destination immediately."""
    row=list(row)
    if tuple(row[19:22])==tuple(destination):return row,seed
    if row[19]!=destination[0]:
        seed,a=random_bounded(seed,50);seed,b=random_bounded(seed,50)
        timers=(200+a,1,200+b);status=6
    else:
        other_primary=row[20]!=destination[1]
        seed,roll=random_bounded(seed,50 if other_primary else 20)
        timers=(0,0,(150 if other_primary else 80)+roll);status=4
    row[19:23]=[*destination,status];row[23:29]=struct.pack("<3h",*timers)
    return row,seed


def travel_hour(row,pilot_level):
    """0x12EAB..0x12F4B. Exactly one leg advances per hour."""
    row=list(row)
    if row[22] not in (4,5,6):return row,False
    a,b,c=struct.unpack_from("<3h",bytes(row),23)
    if a>0:a=i16(a-pilot_level-1)
    elif b>0:b-=1
    elif c>0:c=i16(c-pilot_level-1)
    a,b,c=max(a,0),max(b,0),max(c,0)
    row[23:29]=struct.pack("<3h",a,b,c)
    if c==0:row[22]=2
    elif b==0:row[22]=4
    elif a==0:row[22]=5
    return row,c==0


def remaining_hours(row,pilot_level):
    if row[22] not in (4,5,6):return 0
    a,b,c=struct.unpack_from("<3h",bytes(row),23);speed=pilot_level+1
    if c<=0:return 1
    return (max(a,0)+speed-1)//speed+max(b,0)+(c+speed-1)//speed


def advance_fleet(row,campaign,products,known_systems,worlds,pilot_level):
    if row[22] not in (4,5,6):return list(row),[]
    events=[];a,b,_=struct.unpack_from("<3h",bytes(row),23)
    if a==0 and b==1 and not campaign["navigation"]["flags"]["5d48"]:
        events.extend((("message",34),("scene",2)));campaign["navigation"]["flags"]["5d48"]=1
    row,arrived=travel_hour(row,pilot_level)
    if arrived:
        row,notices=arrival(row,campaign,products,known_systems,worlds);events.extend(notices)
    return row,events


def unlock(products,product):
    if products[product-1]["research_state"]==0:products[product-1]["research_state"]=3


def contact(campaign,products,race):
    """0x1E670..0x1E887. Returns message/dialog requests and timed consequences."""
    if not 2<=race<=12 or campaign["alien_status"][race-2]>0:return []
    nav=campaign["navigation"];flags=nav["flags"];timers=nav["timers"];events=[]
    campaign["alien_status"][race-2]=6 if race in (4,11) else 2 if race in (3,7,8,9,10,12) else 4
    def roll(base,spread):
        campaign["rng"],value=random_bounded(campaign["rng"],spread)
        return i16(base+value)
    communicator=products[7]["research_state"]==0 and campaign["idea_timers"][7]==-1
    if race==2:
        if communicator:
            schedule_idea(campaign,products,8,20,20);events.append(("message",5))
        if not flags["5d50"]:timers["5d4e"]=roll(650,70)
        if not flags["5d56"]:timers["5d54"]=roll(timers["5d4e"]+720,50)
        if not flags["5d5a"]:timers["5d58"]=roll(timers["5d54"]+1220,100)
        if not flags["5d5e"]:timers["5d5c"]=roll(timers["5d58"]+100,20)
    if race==3 and communicator:events.append(("message",5))
    if race==4:
        events.extend((("message",15),("dialog",5)))
        if not flags["5d78"]:timers["5d76"]=roll(1500,500)
    if race==5 and not flags["5d84"]:timers["5d82"]=roll(20,20)
    if race in (7,8,9,10) and not flags["5d98"] and timers["5d96"]<=0:
        events.append(("message",28));timers["5d96"]=roll(200,50)
    if race==11:events.extend((("message",29),("dialog",10)))
    if race==12:
        events.append(("message",38));nav["encounter"]=[12,3,2];timers["5d40"]=roll(1000,200)
    return events


def arrival(row,campaign,products,known_systems,worlds):
    """Gameplay branches of 0x12F4B..0x13562, excluding presentation callbacks."""
    row=list(row);nav=campaign["navigation"];flags=nav["flags"];timers=nav["timers"];events=[]
    system,planet,moon=row[19:22]
    if flags["5d71"] and (system,planet,moon)==(2,1,0):
        events.extend((("message",18),("dialog",6)));unlock(products,19);flags["5d71"]=0
    if planet==0:
        visibility=nav["planet_visibility"]
        if known_systems[system-1]==0:
            known_systems[system-1]=1
            for p in range(1,9):
                if visibility[8*(system-1)+p-1]==255:
                    visibility[8*(system-1)+p-1]=0;planet=p;moon=0
            if system==4:
                if not flags["5d94"]:timers["5d92"]=50
                schedule_idea(campaign,products,27,150,70)
        else:
            for p in range(1,9):
                if visibility[8*(system-1)+p-1]<128:planet=p;moon=0
        row[20:22]=[planet,moon]
    if planet>0 and nav["planet_visibility"][8*(system-1)+planet-1]==0:
        nav["planet_visibility"][8*(system-1)+planet-1]=1
    raw=worlds.get(f"{system}:{planet}:{moon}",{}).get("raw")
    if row[0]==1 and (system,planet,moon)==(8,3,0):nav["ending"]=2
    if raw is not None and planet>0 and row[0]!=4:
        if 2<=raw[0]<=12 and campaign["alien_status"][raw[0]-2]==0:
            events.extend(contact(campaign,products,raw[0]))
        for race,groups in enumerate(nav["alien_fleets"],2):
            if campaign["alien_status"][race-2]!=0:continue
            for group in groups:
                if group[2]==1 and group[8:11]==[system,planet,moon]:
                    events.extend(contact(campaign,products,race))
    if raw is not None and flags["5d95"] and system==4 and raw[6] and raw[0] in (1,6):
        flags["5d95"]=0;events.extend((("dialog",9),("message",45)))
        if not flags["5d90"]:
            campaign["rng"],roll=random_bounded(campaign["rng"],10);timers["5d8e"]=560+roll
    return row,events


def orbit_toggle(row,raw,campaign,products):
    """0x17AC0..0x17BC9 after eligibility; changes state 1 <-> 2."""
    row=list(row);raw=list(raw);events=[]
    if (raw[12] if raw[12]<128 else raw[12]-256)<6:raw[12]=6
    row[22]=3-row[22];identity=tuple(row[19:22])
    if identity==(1,7,0) and raw[0]!=2 and products[11]["research_state"]==0:
        events.append(("message",13));unlock(products,12)
    events.extend(surface_discoveries(identity,campaign,products))
    return row,raw,events


def surface_discoveries(identity,campaign,products):
    """Special-location finds shared by fleet landing and survey satellites."""
    identity=tuple(identity);events=[]
    if identity==(3,2,1) and products[21]["research_state"]==0:
        events.extend((("message",21),("scene",4)));unlock(products,22);unlock(products,23)
    if identity==(7,1,0) and products[30]["research_state"]==0:
        events.extend((("message",31),("scene",6)));unlock(products,31);unlock(products,32)
        schedule_idea(campaign,products,34,100,20)
    return events
