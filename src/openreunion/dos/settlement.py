"""Recovered colony deployment records and settlement arithmetic."""
import struct

from ..core import GameError,integer
from .campaign import random_bounded
from .savefile import SaveBlocks


def read_options(data):
    return [struct.unpack_from("<H",data,0x3F2F0+0x6528+10*i)[0] for i in range(6)]


def read_deployments(data):
    blocks=SaveBlocks(data)
    count=blocks.number(0xA21A)
    if count>10:
        raise GameError("Invalid original colony deployment count.")
    raw=blocks.read(0xA21C,160)
    return [list(raw[16*i:16*(i+1)]) for i in range(count)]


def validate_deployments(rows):
    if not isinstance(rows,list) or len(rows)>10:
        raise GameError("Invalid colony deployment list.")
    for row in rows:
        if not isinstance(row,list) or len(row)!=16:
            raise GameError("Invalid colony deployment record.")
        for byte in row:
            integer(byte,"Deployment byte",maximum=255)
        integer(row[0],"Deployment active flag",maximum=1)


def can_settle(raw,rules,control_centre_researched,queue_count):
    return (control_centre_researched and not raw[6] and not raw[7] and 30<=raw[12]<128 and raw[2]!=0
            and raw[0]<2 and 1<=raw[21]<=11 and rules["editable"][rules["groups"][raw[21]-1]-1]!=0 and queue_count<10)


def start_settlement(raw,seed):
    raw[0]=1
    raw[12]=min(raw[12]+10,60)
    seed,roll=random_bounded(seed,2)
    raw[7]=roll+1
    return seed


def activate_bundle(row,seed):
    row[0]=1
    seed,roll=random_bounded(seed,10)
    delay=50+roll
    for index in range(6):
        offset=4+index*2
        if row[offset] or row[offset+1]:
            row[offset:offset+2]=struct.pack("<H",delay)
            seed,roll=random_bounded(seed,5)
            delay+=5+roll
    return seed


def settlement_population(raw,seed):
    raw[7],raw[6]=0,1
    seed,roll=random_bounded(seed,3000)
    population=struct.unpack_from("<I",bytes(raw),13)[0]+2000+roll
    integer(population,"Settlement population",maximum=2**32-1)
    raw[13:17]=struct.pack("<I",population)
    raw[17:20]=[20,3,30]
    raw[8]=0
    return seed


def deployment_step(row,options):
    """One active entry of 0x12935; returns buildings due this hour and completion."""
    if not row[0]:
        return [],False
    due=[]
    for index,kind in enumerate(options):
        offset=4+2*index
        left=row[offset]+256*row[offset+1]
        if left:
            left-=1
            row[offset:offset+2]=struct.pack("<H",left)
            if left==0:
                due.append(kind)
    return due,not any(row[4:16])
