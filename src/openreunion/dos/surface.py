"""Original surface occupancy, construction setup and placement requirements."""
from pathlib import Path
import struct

from ..core import GameError,integer
from .campaign import random_bounded


def read_surface_rules(data):
    base=0x3F2F0
    groups=list(struct.unpack_from("<11H",data,base+0x1A3A))
    return {"groups":groups,"editable":list(data[base+0x1A50:base+0x1A5B]),
            "blocked_hex":[data[base+0xCA6+group*240:base+0xCA6+group*240+256].hex() for group in range(1,12)]}


def read_surface_maps(root):
    from ..legacy import TerrainMap
    result={}
    for path in sorted((Path(root)/"MAP").glob("MAP*.MAP")):
        terrain=TerrainMap.read(path)
        result[path.name]={"width":terrain.width,"height":terrain.height,"tiles_hex":bytes(terrain.tiles).hex()}
    return result


def validate_surface(catalog):
    rules=catalog["surface_rules"]
    if set(rules)!={"groups","editable","blocked_hex"} or any(len(rules[key])!=11 for key in rules):
        raise GameError("Invalid surface rules.")
    for group in rules["groups"]:
        integer(group,"Terrain group",minimum=1,maximum=11)
    for value in rules["editable"]:
        integer(value,"Surface access",maximum=1)
    if any(not isinstance(mask,str) or len(bytes.fromhex(mask))!=256 for mask in rules["blocked_hex"]):
        raise GameError("Invalid terrain collision table.")
    for name,terrain in catalog.get("surface_maps",{}).items():
        if not isinstance(name,str) or not name.startswith("MAP") or not name.endswith(".MAP") or any(c not in "MAP0123456789_." for c in name):
            raise GameError("Invalid terrain map name.")
        if set(terrain)!={"width","height","tiles_hex"}:
            raise GameError("Invalid terrain map record.")
        for key in ("width","height"):
            integer(terrain[key],"Map size",minimum=1,maximum=90 if key=="width" else 60)
        if not isinstance(terrain["tiles_hex"],str) or len(bytes.fromhex(terrain["tiles_hex"]))!=terrain["width"]*terrain["height"]:
            raise GameError("Invalid terrain map payload.")


def surface_map(catalog,raw):
    name=f"MAP{raw[21]}_{raw[22]}.MAP"
    terrain=catalog.get("surface_maps",{}).get(name)
    if terrain is None:
        raise GameError(f"Surface map {name} is unavailable; re-extract original content.")
    return terrain


def surface_editable(catalog,raw):
    """6049..606F: an owned colony on a supported construction terrain."""
    rules=catalog.get('surface_rules')
    return bool(raw[0]==1 and raw[6] and rules and 1<=raw[21]<=11
                and rules['editable'][rules['groups'][raw[21]-1]-1])


def surface_revealed(raw):
    """2587C..258BA, also preview/radar: active support, not survey percentage.

    Positive signed satellite byte means a landed survey/spy satellite; negative
    values are transit. Ordinary survey satellites cannot survive alien landing.
    Bar force intelligence does not reveal terrain.
    """
    return bool(raw[0]==1 and (raw[6] or raw[10]) or 0<raw[8]<128 or raw[9])


def footprint(definition,x,y):
    # The original has a fixed four-wide tile array, including transparent holes.
    return [(x+dx,y+dy) for dx in range(definition["width"]) for dy in range(definition["height"])
            if definition["tile_ids"][dy*4+dx]!=255]


def occupancy(catalog,raw,buildings,identity,*,allow_unplaced=False):
    terrain=surface_map(catalog,raw)
    width,height=terrain["width"],terrain["height"]
    group=catalog["surface_rules"]["groups"][raw[21]-1]
    mask=bytes.fromhex(catalog["surface_rules"]["blocked_hex"][group-1])
    blocked=[bool(mask[tile]) for tile in bytes.fromhex(terrain["tiles_hex"])]
    definitions={d["id"]:d for d in catalog["buildings"]}
    for row in buildings:
        if row[1:4]!=list(identity):
            continue
        if row[4]==255 or row[5]==255:
            if allow_unplaced:
                continue
            raise GameError("This colony has a building awaiting a free surface position.")
        definition=definitions.get(row[0])
        if definition is None:
            raise GameError("Unknown building in surface records.")
        for x,y in footprint(definition,row[4],row[5]):
            if 1<=x<=width and 1<=y<=height:
                blocked[(y-1)*width+x-1]=True
    return width,height,blocked


def automatic_position(definition,width,height,blocked):
    """0x261A5 order, followed by a complete in-bounds rectangle search.

    The original radius bound omits edges of rectangular maps and can miss
    every site on a map exactly the size of the building. Retain its preferred
    positions, then cover the remaining sites before reporting no space.
    """
    dw,dh=definition["width"],definition["height"]
    cx,cy=(width+1-dw)//2,(height+1-dh)//2
    def fits(x,y):
        return (1<=x and 1<=y and x+dw-1<=width and y+dh-1<=height and
                all(not blocked[(yy-1)*width+xx-1] for xx in range(x,x+dw) for yy in range(y,y+dh)))
    for radius in range(max(cx,0)):
        for xx in range(cx-radius,cx+radius+1):
            for yy in (cy-radius,cy+radius):
                if fits(xx,yy):
                    return xx,yy
        for yy in range(cy-radius,cy+radius+1):
            for xx in (cx-radius,cx+radius):
                if fits(xx,yy):
                    return xx,yy
    for yy in range(1,height-dh+2):
        for xx in range(1,width-dw+2):
            if fits(xx,yy):
                return xx,yy
    return None


def place_unpositioned(catalog,raw,buildings,identity,*,require_all=True):
    width,height,blocked=occupancy(catalog,raw,buildings,identity,allow_unplaced=True)
    definitions={d["id"]:d for d in catalog["buildings"]}
    for row in buildings:
        if row[1:4]!=list(identity) or row[4:6]!=[255,255]:
            continue
        definition=definitions.get(row[0])
        if definition is None:
            raise GameError("Unknown unplaced building type.")
        position=automatic_position(definition,width,height,blocked)
        if position is None:
            if require_all:
                raise GameError("No free surface position is available for an imported or deployed building.")
            continue
        row[4:6]=position
        for x,y in footprint(definition,*position):
            blocked[(y-1)*width+x-1]=True


def placement_fits(definition,x,y,width,height,blocked):
    return (x>=1 and y>=1 and x+definition["width"]-1<=width and y+definition["height"]-1<=height
            and all(not blocked[(cy-1)*width+cx-1] for cx,cy in footprint(definition,x,y)))


def building_available(definition,raw,products,builder_level):
    fields=bytes.fromhex(definition["unclassified_fields_hex"])
    kind=definition["id"]
    if kind==4 and raw[3]==0 or kind==5 and (raw[3]==0 or raw[59]<10):
        return False
    research,level=fields[0],fields[1]
    unlocked=(research==0 and builder_level>=level) or (research>0 and products[research-1]["research_state"]==5)
    return unlocked and 1<=raw[21]<=11 and fields[raw[21]+4]>0


def new_building(definition,identity,x,y,terrain_type,seed):
    factor=bytes.fromhex(definition["unclassified_fields_hex"])[terrain_type+4]
    if factor==0:
        raise GameError("This structure cannot be built on this terrain.")
    seed,work=random_bounded(seed,60)
    seed,condition=random_bounded(seed,80)
    return [definition["id"],*identity,x,y,100+work,(factor*40+condition)&255,0,0,0,0,0,0],seed
