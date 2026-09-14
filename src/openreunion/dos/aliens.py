"""Recovered alien fleet orders and world consequences.

These helpers are building blocks for the remaining story/battle dispatcher.
They do not themselves advance the recovered client's campaign clock.
"""
from copy import deepcopy
import struct

from ..core import GameError,integer
from .campaign import random_bounded
from .catalog import DATA_FILE_OFFSET
from .navigation import depart
from .rules import i16
from .savefile import SaveBlocks

RACE_BASE=0x6BCE
RACE_SIZE=228
FLEET_SIZE=27


def read_civilizations(data):
    """Retain all seven fleet slots, including dormant story reinforcements."""
    blocks=SaveBlocks(data)
    rows=[list(blocks.read(RACE_BASE+RACE_SIZE*i,RACE_SIZE)) for i in range(11)]
    validate_civilizations(rows)
    return rows


def validate_civilizations(rows):
    if not isinstance(rows,list) or len(rows)!=11:raise GameError("Expected eleven civilization records.")
    for row in rows:
        if not isinstance(row,list) or len(row)!=RACE_SIZE:raise GameError("Invalid civilization record.")
        for value in row:integer(value,"Civilization byte",maximum=255)
        integer(row[38],"Civilization fleet count",maximum=7)


def fleet_at(civilization,index):
    integer(index,"Alien fleet slot",minimum=1,maximum=7)
    start=39+FLEET_SIZE*(index-1)
    return list(civilization[start:start+FLEET_SIZE])


def store_fleet(civilization,index,row):
    integer(index,"Alien fleet slot",minimum=1,maximum=7)
    if not isinstance(row,list) or len(row)!=FLEET_SIZE:raise GameError("Invalid alien fleet record.")
    for value in row:integer(value,"Alien fleet byte",maximum=255)
    start=39+FLEET_SIZE*(index-1)
    civilization[start:start+FLEET_SIZE]=row


def route_fleet(row,destination,seed):
    """0x1F41B..0x1F4D6: assign destination and a single travel countdown."""
    row=list(row)
    if row[8:11]==list(destination):return row,seed
    base,spread=(50,20) if row[8]!=destination[0] else (20,10) if row[9]!=destination[1] else (6,5)
    seed,roll=random_bounded(seed,spread)
    row[3:5]=struct.pack("<H",base+roll)
    row[8:11]=destination;row[2]=2;row[5:8]=[0,0,0]
    return row,seed


def attack_order(row,destination,delay_factor,mission,seed,*,force_kind=False):
    """0x1E986..0x1EA23: route, delayed action and optional kind replacement.

    The original force wrapper copies the mission into byte zero. Its extra
    final argument is unused; no alternate meaning is invented here.
    """
    row,seed=route_fleet(row,destination,seed)
    seed,roll=random_bounded(seed,100-delay_factor)
    row[5:7]=struct.pack("<h",i16(5+roll));row[7]=mission&255
    if force_kind:row[0]=row[7]
    return row,seed


def reset_world(raw,*,erase_population=True):
    """0x1E887..0x1E986: clear ownership/colony and eight military stocks."""
    raw=list(raw)
    for index in (0,1,4,5,6,7):raw[index]=0
    if erase_population:
        for index in (10,11,13,14,15,16,17,18,19):raw[index]=0
    raw[27:59]=[0]*32
    return raw


def read_alien_rules(data):
    base=DATA_FILE_OFFSET
    def block(at):return list(data[base+at:base+at+8])
    return {"morgrul_base":block(0x890),"morgrul_early_base":block(0x898),"morgrul_spread":block(0x8A0),
            "lisonian_base":block(0x8A8),"lisonian_spread":block(0x8B0),
            "undorling_base":block(0x8B8),"undorling_spread":block(0x8C0),
            "earth_base":block(0x8C8),"earth_spread":block(0x8D0)}


def settle_world(raw,owner,seed,rules,*,morgrul_late=False):
    """0x1ED44..0x1EF5D, correcting missing Undorling/Earthling stock offsets.

    The early Morgrul override still consumes both original eight-roll passes.
    All eight quantities use distinct unsigned 32-bit fields at 27..58.
    """
    raw=reset_world(raw)
    raw[0]=owner;raw[6]=1;raw[8:10]=[0,0]
    seed,roll=random_bounded(seed,3000);raw[13:17]=struct.pack("<I",2000+roll)
    raw[17:20]=[20,3,30]
    passes=[]
    if owner==3:
        passes.append((rules["morgrul_base"],rules["morgrul_spread"]))
        if not morgrul_late:passes.append((rules["morgrul_early_base"],rules["morgrul_spread"]))
    for race,key in ((7,"lisonian"),(8,"undorling"),(12,"earth")):
        if owner==race:passes.append((rules[key+"_base"],rules[key+"_spread"]))
    for bases,spreads in passes:
        for index,(base,spread) in enumerate(zip(bases,spreads)):
            seed,roll=random_bounded(seed,spread)
            raw[27+4*index:31+4*index]=struct.pack("<I",base+roll)
    return raw,seed


def unload_fleet(row,raw,owner):
    """0x1F0D0..0x1F203: merge an alien fleet into its owned world's stocks."""
    row=list(row);raw=list(raw)
    if raw[0]==owner:
        for index,quantity in enumerate(struct.unpack("<8H",bytes(row[11:27]))):
            at=27+4*index;total=struct.unpack_from("<I",bytes(raw),at)[0]+quantity
            integer(total,"Alien military stock",maximum=2**32-1)
            raw[at:at+4]=struct.pack("<I",total)
    row[2]=0
    return row,raw


def destroy_civilization(civilizations,worlds,owner):
    """0x1F654..0x1F7E9: erase owned worlds and the counted fleet slots."""
    civilizations=deepcopy(civilizations);worlds=deepcopy(worlds)
    race=civilizations[owner-2]
    race[15:19]=[0]*4;race[27]=255;race[28:32]=[0]*4;race[32:38]=[255]*6
    for world in worlds.values():
        if world["raw"][0]==owner:world["raw"]=reset_world(world["raw"])
    for index in range(1,race[38]+1):store_fleet(race,index,[0]*FLEET_SIZE)
    race[38]=0
    return civilizations,worlds


def system_disaster(civilizations,worlds,buildings,fleets,seed):
    """0x1F7E9..0x1F9DE: system-four catastrophe and incoming-fleet recall.

    Native removal uses each actual fleet bank, avoiding the original global
    selected-bank count used by its compaction helper.
    """
    civilizations=deepcopy(civilizations);worlds=deepcopy(worlds);fleets=deepcopy(fleets)
    buildings=[list(row) for row in buildings if row[1]!=4]
    for identity,world in worlds.items():
        if identity.split(":")[0]=="4":world["raw"]=reset_world(world["raw"])
    for race in civilizations:
        for index in range(1,race[38]+1):
            if fleet_at(race,index)[8]==4:store_fleet(race,index,[0]*FLEET_SIZE)
    retained=[]
    for row in fleets["moving"]:
        if row[19]==4:
            if row[22]<=2:continue
            row,seed=depart(row,(1,5,0),seed)
        retained.append(row)
    fleets["moving"]=retained
    fleets["local"]=[row for row in fleets["local"] if row[19]!=4]
    return civilizations,worlds,buildings,fleets,seed
