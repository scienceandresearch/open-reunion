"""Original planet identities and saved records, addressed through DOS tables."""
import struct

from ..core import GameError, integer
from .catalog import DATA_FILE_OFFSET, ORE_KEYS, pascal
from .savefile import SaveBlocks

NAME_BASES=(0x1A9C,0x248A,0x2860,0x2DF8,0x3038,0x3470,0x3B86,0x3D56)
DETAIL_BASES=(0x1C3C,0x2526,0x294A,0x2E54,0x30E2,0x359C,0x3BC8,0x3EF6)
COUNTS=(32,12,18,7,13,23,5,32)


def world_message_label(catalog,definition):
    """257B:346D with the caller's 50-character destination limit."""
    if "system_names" not in catalog:
        return definition["name"] # original-free synthetic session fixtures
    primary=next(w for w in catalog["worlds"] if w["system"]==definition["system"] and w["planet"]==definition["planet"] and w["moon"]==0)
    label=catalog["system_names"][definition["system"]-1]+" system,planet "+primary["name"]
    if definition["moon"]:
        label+=",moon "+definition["name"]
    return label[:50]


def validate_world_catalog(worlds):
    if not isinstance(worlds,list) or len(worlds)!=sum(COUNTS):
        raise GameError("The catalog must contain all 142 worlds.")
    seen=set()
    at=0
    for system,count in enumerate(COUNTS,1):
        for index in range(1,count+1):
            world=worlds[at]
            at+=1
            if not isinstance(world,dict) or set(world)!={"id","system","planet","moon","index","name","name_address","address","orbital_display_bytes"}:
                raise GameError("Invalid world definition.")
            for key,minimum,maximum in (("system",1,8),("planet",1,8),("moon",0,8),("index",1,32),
                                        ("name_address",0,65535),("address",0,65535)):
                integer(world[key],key,minimum=minimum,maximum=maximum)
            if (world["system"],world["index"],world["address"],world["name_address"])!=(system,index,DETAIL_BASES[system-1]+65*(index-1),NAME_BASES[system-1]+13*(index-1)):
                raise GameError("World addresses do not match the supported DOS layout.")
            if world["id"]!=f"{system}:{world['planet']}:{world['moon']}" or world["id"] in seen:
                raise GameError("Invalid or duplicate world identity.")
            seen.add(world["id"])
            if not isinstance(world["name"],str) or not 1<=len(world["name"])<=9 or not world["name"].isascii() or not world["name"].isprintable():
                raise GameError("Invalid world name.")
            if not isinstance(world["orbital_display_bytes"],list) or len(world["orbital_display_bytes"])!=3:
                raise GameError("Invalid orbital display record.")
            for value in world["orbital_display_bytes"]:
                integer(value,"Orbital display byte",maximum=255)


def read_world_catalog(data):
    result=[]
    for system,(names,details,count) in enumerate(zip(NAME_BASES,DETAIL_BASES,COUNTS),1):
        primary_count=struct.unpack_from("<H",data,DATA_FILE_OFFSET+0x4774+2*system)[0]
        moon_table=struct.unpack_from("<H",data,DATA_FILE_OFFSET+0x4732+4*system)[0]
        identities={i:(i,0) for i in range(1,primary_count+1)}
        for planet in range(1,primary_count+1):
            at=DATA_FILE_OFFSET+moon_table+9*(planet-1)
            if data[at]>8:
                raise GameError("Invalid moon count.")
            for moon,index in enumerate(data[at+1:at+1+data[at]],1):
                if index in identities:
                    raise GameError("Duplicate planet/moon record.")
                identities[index]=(planet,moon)
        if set(identities)!=set(range(1,count+1)):
            raise GameError("Incomplete world identity table.")
        for index in range(1,count+1):
            planet,moon=identities[index]
            at=DATA_FILE_OFFSET+names+13*(index-1)
            result.append({"id":f"{system}:{planet}:{moon}","system":system,"planet":planet,"moon":moon,"index":index,
                           "name":pascal(data,at,9),"name_address":names+13*(index-1),"address":details+65*(index-1),
                           "orbital_display_bytes":list(data[at+10:at+13])})
    return result


def read_world_state(saved,catalog):
    blocks=SaveBlocks(saved)
    result={}
    for definition in catalog["worlds"]:
        raw=blocks.read(definition["address"],65)
        # Keep unclassified bytes to permit lossless future semantic migrations.
        # They are never used as invented gameplay rules.
        result[definition["id"]]={"raw":list(raw)}
    buildings=blocks.read(0xA2BC,14000,pointer=True)
    count=blocks.number(0xA2C0)
    if count>1000:
        raise GameError("Invalid original building count.")
    return result,[list(buildings[14*i:14*(i+1)]) for i in range(count)]


FORCE_PRODUCTS=(10,16,23,33,17,21,26,32)


def force_intelligence(raw,civilizations,bar=None):
    """2B901..2BAA7: spy ship or returned forces mission; known weapon types only.

    Alien world force stocks are unsigned, matching native battle rosters.
    Invalid/non-alien owners cannot index a civilization, even with a stray spy flag.
    """
    owner=raw[0]
    if not 2<=owner<=12:return None
    if not raw[9] and (bar is None or bar['intelligence'][owner-1]!=2):return None
    civilization=civilizations[owner-2]
    stocks=struct.unpack_from('<8I',bytes(raw),27)
    return {product:count for i,(product,count) in enumerate(zip(FORCE_PRODUCTS,stocks)) if civilization[19+i]}


def describe_world(record):
    raw=bytes(record["raw"])
    return {"owner":raw[0],"colony":bool(raw[6]),"satellite":struct.unpack_from("<b",raw,8)[0],
            "survey_progress":raw[12],"population":struct.unpack_from("<I",raw,13)[0],
            "tax_level":raw[18],"morale":raw[19],"terrain_type":raw[21],"terrain_variant":raw[22],
            "ores":dict(zip(ORE_KEYS,struct.unpack_from("<6I",raw,27))),
            "ore_abundance":dict(zip(ORE_KEYS,raw[59:65]))}
