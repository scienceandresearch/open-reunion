"""Recovered cargo weights, transport capacity and depot transfers."""
import struct
from ..core import GameError,integer


def read_cargo_rules(data):
    ds=0x3F2F0
    return {"hull_capacity":list(struct.unpack_from("<4i",data,ds+0x84A)),
            "items":[{"slot":i,"product":data[ds+0x807+i] if data[ds+0x807+i]<128 else None,
                      "weight":struct.unpack_from("<i",data,ds+0x812+4*i)[0]} for i in range(1,14)]}


def validate_cargo_rules(rules):
    if not isinstance(rules,dict) or set(rules)!={"hull_capacity","items"}:
        raise GameError("Incomplete cargo rules; re-extract the original content.")
    if not isinstance(rules["hull_capacity"],list) or len(rules["hull_capacity"])!=4:
        raise GameError("Invalid transport capacity table.")
    for value in rules["hull_capacity"]:integer(value,"Hull capacity",maximum=2**31-1)
    if not isinstance(rules["items"],list) or len(rules["items"])!=13:
        raise GameError("Invalid stored-item table.")
    for i,item in enumerate(rules["items"],1):
        if not isinstance(item,dict) or set(item)!={"slot","product","weight"} or type(item["slot"]) is not int or item["slot"]!=i:
            raise GameError("Invalid cargo slot.")
        if item["product"] is not None:integer(item["product"],"Cargo product",minimum=1,maximum=35)
        integer(item["weight"],"Cargo weight",maximum=2**31-1)


def cargo_capacity(row,catalog):
    """0x1A8DA..0x1A913, with Pirate trade-bank correction."""
    if row[0] not in (2,3):return 0
    category=next((c for c in catalog["fleet_rules"][row[0]-1]["categories"] if c["id"]==2),None)
    if category is None:raise GameError("Missing transport category; re-extract the original content.")
    at=29+40*(category["bank"]-1)
    counts=[struct.unpack_from("<h",bytes(row),at+10*i)[0] for i in range(4)]
    if any(c<0 for c in counts):raise GameError("Negative transport hull count.")
    return sum(c*w for c,w in zip(counts,catalog["cargo_rules"]["hull_capacity"]))


def cargo_used(row,rules):
    """0x1A913..0x1A979: stored-item weight plus the six ore quantities."""
    stocks=struct.unpack_from("<13h",bytes(row),133)
    if any(c<0 for c in stocks):raise GameError("Negative stored cargo count.")
    return sum(struct.unpack_from("<6I",bytes(row),109))+sum(c*item["weight"] for c,item in zip(stocks,rules["items"]))


def ore_transfer_limit(ship_stock,depot_stock,capacity,used,storage,loading):
    """0x1A3AF..0x1A493 / 0x1A5A0..0x1A6BA, without negative transfers."""
    return max(0,min(depot_stock,capacity-used,storage-ship_stock) if loading else min(ship_stock,storage-depot_stock))


def transfer_ore(row,depot,ore,quantity,capacity,used,storage):
    row=list(row);depot=list(depot)
    ship_stock=struct.unpack_from("<I",bytes(row),109+4*ore)[0]
    limit=ore_transfer_limit(ship_stock,depot[ore],capacity,used,storage,quantity>0)
    if not quantity or abs(quantity)>limit:
        raise GameError("The ore transfer exceeds available stock or storage capacity.")
    ship_stock+=quantity;depot[ore]-=quantity
    integer(ship_stock,"Ship ore",maximum=2**32-1)
    integer(depot[ore],"Depot ore",maximum=2**32-1)
    row[109+4*ore:113+4*ore]=struct.pack("<I",ship_stock)
    return row,depot


def transfer_item(row,slot,stock,quantity,weight,capacity,used):
    row=list(row)
    at=131+2*slot
    carried=struct.unpack_from("<h",bytes(row),at)[0]
    if carried<0 or stock<0:raise GameError("Negative stored cargo count.")
    if (not quantity or quantity>stock or -quantity>carried or
            quantity>0 and quantity*weight>capacity-used):
        raise GameError("The item transfer exceeds available stock or cargo capacity.")
    carried+=quantity;stock-=quantity
    integer(carried,"Carried items",maximum=32767)
    integer(stock,"Depot items",maximum=32767)
    row[at:at+2]=struct.pack("<h",carried)
    return row,stock


def item_transfer_limit(carried,stock,weight,capacity,used,loading,queued=0):
    """Maximum repeated item transfers, retaining inventory overflow guards."""
    if carried<0 or stock<0:raise GameError("Negative stored cargo count.")
    if not loading:return max(0,min(carried,32767-stock-queued))
    if capacity<used:return 0
    limit=min(stock,32767-carried)
    return max(0,min(limit,(capacity-used)//weight) if weight else limit)
