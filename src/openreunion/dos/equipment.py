"""Executable fleet descriptors and hull/equipment transfer arithmetic."""
import struct
from ..core import GameError,integer


class EquipmentTransferLimit(GameError):
    """An expected stock/capacity boundary, suitable for inline UI feedback."""
    def __init__(self,notice):
        self.notice=notice
        super().__init__("The transfer exceeds available stock or the hull's equipment capacity.")


def read_fleet_rules(data):
    from .catalog import DATA_FILE_OFFSET,pascal
    result=[]
    for kind in range(1,6):
        categories=[]
        for category in range(1,5):
            if not data[DATA_FILE_OFFSET+0xB3B+20*kind+category]:
                continue
            offset,segment=struct.unpack_from("<HH",data,DATA_FILE_OFFSET+0xB3C+20*kind+4*category)
            base=0x4AE0+16*segment+offset
            components=[]
            for index in range(data[base+1]):
                at=base+2+14*index
                components.append({"product":data[at],"local_slot":data[at+1],"name":pascal(data,at+2,5)})
            hulls=[]
            for index in range(data[base]):
                at=base+58+25*index
                hulls.append({"product":data[at],"local_slot":data[at+1],"name":pascal(data,at+2,11),
                              "limits":list(data[at+21:at+21+len(components)])})
            categories.append({"id":category,"bank":data[DATA_FILE_OFFSET+0xBB9+4*kind+category],
                               "components":components,"hulls":hulls})
        result.append({"id":kind,"name":pascal(data,DATA_FILE_OFFSET+0x591A+14*kind,13),
                       "default_name":pascal(data,DATA_FILE_OFFSET+0x595D+17*kind,16),"categories":categories})
    return result


def validate_fleet_rules(rules):
    if not isinstance(rules,list) or len(rules)!=5:
        raise GameError("Incomplete fleet catalog; re-extract original content.")
    for kind,rule in enumerate(rules,1):
        if set(rule)!={"id","name","default_name","categories"} or rule["id"]!=kind:
            raise GameError("Invalid fleet type.")
        for key,limit in (("name",13),("default_name",17)):
            if not isinstance(rule[key],str) or not 1<=len(rule[key])<=limit or not rule[key].isascii() or not rule[key].isprintable():
                raise GameError("Invalid fleet label.")
        cats=rule["categories"]
        if not isinstance(cats,list) or not 1<=len(cats)<=4:
            raise GameError("Invalid fleet categories.")
        seen=set()
        banks=set()
        for cat in cats:
            if set(cat)!={"id","bank","components","hulls"}:
                raise GameError("Invalid fleet category fields.")
            integer(cat["id"],"Fleet category",minimum=1,maximum=4)
            integer(cat["bank"],"Equipment bank",minimum=1,maximum=2)
            if cat["id"] in seen or cat["bank"] in banks:
                raise GameError("Duplicate fleet category or bank.")
            seen.add(cat["id"]); banks.add(cat["bank"])
            for key in ("hulls","components"):
                if not isinstance(cat[key],list) or not 1<=len(cat[key])<=4:
                    raise GameError("Invalid equipment table.")
                for item in cat[key]:
                    if set(item)!=({"product","local_slot","name","limits"} if key=="hulls" else {"product","local_slot","name"}):
                        raise GameError("Invalid equipment fields.")
                    integer(item["product"],"Equipment product",minimum=1,maximum=35)
                    integer(item["local_slot"],"Equipment storage slot",maximum=13)
                    if not isinstance(item["name"],str) or not 1<=len(item["name"])<=11 or not item["name"].isascii() or not item["name"].isprintable():
                        raise GameError("Invalid equipment name.")
                    if key=="hulls":
                        if not isinstance(item["limits"],list) or len(item["limits"])!=len(cat["components"]):
                            raise GameError("Invalid equipment limits.")
                        for value in item["limits"]:
                            integer(value,"Equipment limit",maximum=255)


def new_fleet(kind,name):
    integer(kind,"Fleet type",minimum=1,maximum=4)
    row=rename_fleet([0]*161,name)
    row[0]=kind
    row[19:23]=[1,5,0,1]
    return row


def rename_fleet(row,name):
    """Replace the Pascal name field without changing the fleet's contents."""
    if not isinstance(name,str) or not 1<=len(name)<=17 or not name.isascii() or not name.isprintable():
        raise GameError("Fleet names must contain 1–17 printable ASCII characters.")
    row=list(row)
    row[1:19]=[len(name)]+[0]*17
    row[2:2+len(name)]=name.encode("ascii")
    return row


def equipment_step(row,category,hull,component,loading,stocks):
    """0x20775..0x2090A and 0x209FA..0x20B0F; one original click.

    Returns copies. Stock IDs refer to products, independently of the source
    being the home depot or local defense storage. False means a DOS no-op.
    """
    row=list(row)
    stocks=dict(stocks)
    offset=29+40*(category["bank"]-1)+10*(hull-1)
    words=list(struct.unpack_from("<5h",bytes(row),offset))
    if any(value<0 for value in words) or any(value<0 for value in stocks.values()):
        raise GameError("Negative hull, equipment or depot counts must be repaired before transfers.")
    hull_def=category["hulls"][hull-1]
    entry=hull_def if component==0 else category["components"][component-1]
    product=entry["product"]
    if loading:
        limit=1000 if component==0 else min(32767,hull_def["limits"][component-1]*words[0])
        if stocks[product]<=0 or words[component]>=limit or (component and row[0]==4 and sum(words[1:])>=words[0]):
            return row,stocks,False
        words[component]+=1
        stocks[product]-=1
    else:
        if words[component]<=0:
            return row,stocks,False
        words[component]-=1
        stocks[product]+=1
        if component==0:
            for i,item in enumerate(category["components"],1):
                excess=max(0,words[i]-hull_def["limits"][i-1]*words[0])
                words[i]-=excess
                stocks[item["product"]]+=excess
            # DOS only enforces individual limits here, leaving mixed satellite
            # payloads over capacity. Return excess from the last slot first.
            if row[0]==4:
                excess=max(0,sum(words[1:])-words[0])
                for i in range(len(category["components"]),0,-1):
                    returned=min(excess,words[i])
                    words[i]-=returned
                    stocks[category["components"][i-1]["product"]]+=returned
                    excess-=returned
    if any(value>32767 for value in stocks.values()):
        raise EquipmentTransferLimit("Depot full")
    for value in stocks.values():
        integer(value,"Depot stock",maximum=32767)
    for value in words:
        integer(value,"Fleet equipment count",maximum=32767)
    row[offset:offset+10]=struct.pack("<5h",*words)
    return row,stocks,True
