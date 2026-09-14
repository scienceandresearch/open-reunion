"""Saved fleet records, local storage and orbital payload consumption."""
import struct

from ..core import GameError,integer
from .savefile import SaveBlocks

PAYLOADS={"miner_station":(2,(37,47,57,67)),"solar_satellite":(4,(37,)),"survey_satellite":(4,(31,)),
          "spy_satellite":(4,(33,)),"spy_ship":(4,(35,))}


def payload_slots(fleets,identity,kind):
    """0x1E248/0x1E431: orbit includes the primary and all of its moons."""
    if kind not in PAYLOADS:
        raise GameError("Unknown orbital payload.")
    fleet_type,offsets=PAYLOADS[kind]
    return [(index,offset) for index,row in enumerate(fleets["moving"])
            if row[0]==fleet_type and row[19:21]==list(identity[:2]) and row[22] in (1,2)
            for offset in offsets]


def payload_count(fleets,identity,kind):
    return sum(struct.unpack_from("<h",bytes(fleets["moving"][index]),offset)[0]
               for index,offset in payload_slots(fleets,identity,kind))


def consume_payload(fleets,identity,kind,quantity=1,preferred=None):
    """0x1E2DC/0x1E4D7: selected fleet first, then record/subtype order.

    Reject malformed negative cargo and shortages before making any writes.
    DOS's negative-stock subtraction instead drains extra units elsewhere.
    """
    integer(quantity,"Deployment quantity",minimum=1,maximum=2**31-1)
    slots=payload_slots(fleets,identity,kind)
    if preferred is not None:
        integer(preferred,"Fleet index",maximum=len(fleets["moving"])-1)
        slots.sort(key=lambda slot:slot[0]!=preferred)
    stocks=[struct.unpack_from("<h",bytes(fleets["moving"][i]),at)[0] for i,at in slots]
    if any(stock<0 for stock in stocks):
        raise GameError("An orbiting fleet has invalid negative payload stock.")
    if sum(stocks)<quantity:
        raise GameError("Not enough payload is available in a stationary fleet at this planet.")
    for (index,offset),stock in zip(slots,stocks):
        used=min(stock,quantity)
        fleets["moving"][index][offset:offset+2]=struct.pack("<h",stock-used)
        quantity-=used
        if not quantity:
            break


def read_fleets(data):
    blocks=SaveBlocks(data)
    raw=blocks.read(0xA2D0,10304,pointer=True)
    result={}
    for bank,name,address in ((0,"moving",0xA2C4),(1,"local",0xA2C6)):
        count=blocks.number(address)
        if count>32:
            raise GameError("Invalid original fleet count.")
        result[name]=[list(raw[bank*5152+i*161:bank*5152+(i+1)*161]) for i in range(count)]
    return result


def validate_fleets(fleets,*,local_limit=32):
    if not isinstance(fleets,dict) or set(fleets)!={"moving","local"}:
        raise GameError("Invalid fleet banks.")
    for key,rows in fleets.items():
        if not isinstance(rows,list) or len(rows)>(local_limit if key=="local" else 32):
            raise GameError("Invalid fleet count.")
        for row in rows:
            if not isinstance(row,list) or len(row)!=161:
                raise GameError("Invalid fleet record.")
            for value in row:
                integer(value,"Fleet byte",maximum=255)


def roster_layout(fleets):
    """Identity-relevant bank layout; moving types never change after creation.

    Moving groups are appended or removed by current commands. Local groups
    belong to a fixed world. Names, inventories and moving positions are edits
    to a group and do not change which group an index identifies.
    """
    return (tuple(row[0] for row in fleets["moving"]),
            tuple((row[0],tuple(row[19:22])) for row in fleets["local"]))


def local_record(fleets,identity):
    """0x2204F: the last matching local fleet supplies storage capacity."""
    return next((row for row in reversed(fleets["local"]) if row[19:22]==list(identity)),None)


def storage_limit(fleets,identity,buildings=()):
    row=local_record(fleets,identity)
    if row is None:
        # Outposts do not get a local-defense row until colonization. Derive
        # their capacity from the same completed-building rule as allocation.
        return (sum({11:20,4:10,5:5,25:10}.get(b[0],0) for b in buildings
                    if b[1:4]==list(identity) and b[6]==0)&65535)*1000
    return struct.unpack_from("<H",bytes(row),159)[0]*1000


def update_capacity(fleets,identity,capacity):
    row=local_record(fleets,identity)
    if row is not None:
        row[159:161]=struct.pack("<H",capacity)
