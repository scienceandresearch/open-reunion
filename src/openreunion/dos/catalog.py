"""Version-specific executable tables, with offsets traced in RESEARCH.md."""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import struct

from ..core import GameError, integer

SUPPORTED_HASHES = {
    "83616d76f05f18621faf6438aa38e69f0e0b4e45b5b60f084a091d2943f9011b",
    "a3eefbddfabde0d26c6ac1e30086f8ddef7132ef32d494c8ea14045fc496c43e",
    "339aa4ad1ab2a8f51e4544699e144877300dbc58a465a7ff6f2fec72d396416d",
}
DATA_FILE_OFFSET = 0x3F2F0
PRODUCT_FILE_OFFSET = 0x4509C
PRODUCT_SAVE_OFFSET = 0x312F
PRODUCT_SIZE = 53
PRODUCT_COUNT = 35
ORE_KEYS = ("detoxin", "energon", "kremir", "lepitium", "raenium", "texon")
SUBJECTS = ("math", "physics", "electronics", "artificial_intelligence")


def pascal(data, offset, capacity):
    if not 0 <= offset < len(data) or not 0 < data[offset] <= capacity:
        raise GameError(f"Invalid Pascal string at {offset:#x}.")
    raw = data[offset+1:offset+1+data[offset]]
    if len(raw) != data[offset] or any(b < 32 or b > 126 for b in raw):
        raise GameError(f"Invalid English string at {offset:#x}.")
    return raw.decode("ascii").strip()


@dataclass
class ProductRecord:
    id: int
    name: str
    research_state: int
    research_duration: int
    research_remaining: int
    price: int
    stock: int
    queued: int
    base_work: int
    work_remaining: int
    manufacturable: int
    special_ship: int
    ore_costs: dict[str, int]
    requirements: dict[str, int]

    def to_dict(self):
        return asdict(self)


def read_products(data, offset=PRODUCT_FILE_OFFSET):
    if offset < 0 or len(data) < offset + PRODUCT_COUNT * PRODUCT_SIZE:
        raise GameError("Truncated 35-record research/production table.")
    products = []
    for i in range(PRODUCT_COUNT):
        at = offset + i * PRODUCT_SIZE
        name = pascal(data, at, 16)
        state, duration, remaining = struct.unpack_from("<Hhh", data, at+17)
        price = struct.unpack_from("<I", data, at+23)[0]
        stock, queued, work, work_remaining = struct.unpack_from("<hhhh", data, at+27)
        products.append(ProductRecord(i+1, name, state, duration, remaining, price, stock,
                                      queued, work, work_remaining, data[at+35], data[at+36],
                                      dict(zip(ORE_KEYS, struct.unpack_from("<6H", data, at+37))),
                                      dict(zip(SUBJECTS, data[at+49:at+53]))))
    if products[0].name != "Nuclear gen" or products[1].name != "Miner droid" or products[-1].name not in ("Energy shield", "Energy Ihield"):
        raise GameError("Unrecognized DOS product table.")
    return products


def read_buildings(data):
    result = []
    for i in range(25):
        offset = 0x45882 + 63*i
        result.append({"id": i+1, "name": pascal(data, offset, 14), "file_offset": hex(offset),
                       "price": struct.unpack_from("<I", data, offset+39)[0],
                       "width": data[offset+45], "height": data[offset+46],
                       "tile_ids": list(data[offset+47:offset+63]),
                       "unclassified_fields_hex": data[offset+15:offset+39].hex(),
                       "unclassified_43_44": list(data[offset+43:offset+45])})
    return result


def read_catalog(path):
    from .control_layouts import read_layouts
    from .control_panel import read_buttons
    from .control_slide import read_steps
    from .battle_results import read_characters
    from .story_cinema import read_rules as read_story_rules
    from .commanders import read_training_rules
    from .cargo import read_cargo_rules
    from .equipment import read_fleet_rules
    from .surface import read_surface_rules
    from .settlement import read_options
    from .worlds import read_world_catalog
    from .colony import read_colony_messages
    from .ground_validation import read_battle_rules
    from .ground_presentation import read_ground_presentation
    from .space_presentation import read_space_presentation
    with Path(path).open("rb") as stream:
        data = stream.read(288993)
    if len(data) != 288992:
        raise GameError("Unsupported executable size.")
    digest = hashlib.sha256(data).hexdigest()
    if digest not in SUPPORTED_HASHES:
        raise GameError("Executable is not one of the three inspected English builds. Audit its layout before importing.")
    ore_names = [pascal(data, 0x44D6C+9*i, 8) for i in range(6)]
    commanders = []
    for i in range(12):
        commanders.append({"role": ("pilot", "builder", "fighter", "developer")[i//3], "rank": i%3+1,
                           "name": pascal(data, 0x44B34+19*i, 18),
                           "hire_price": struct.unpack_from("<I", data, 0x44A8C+4*i)[0],
                           "level": struct.unpack_from("<H", data, 0x44ABC+2*i)[0],
                           "level_limit_candidate": data[0x44AD4+i],
                           "skills": dict(zip(SUBJECTS, data[0x44AE0+4*(i%3):0x44AE4+4*(i%3)])) if i//3 == 3 else {},
                           "name_offset": hex(0x44B34+19*i), "price_offset": hex(0x44A8C+4*i)})
    return {"profile": "reunion-english-288992", "sha256": digest,
            "system_names":[pascal(data,DATA_FILE_OFFSET+0x5B65+9*system,8) for system in range(1,9)],
            "alien_names":[pascal(data,DATA_FILE_OFFSET+0x6BCE+228*i,14) for i in range(11)],
            "ore_names": dict(zip(ORE_KEYS, ore_names)), "products": [p.to_dict() for p in read_products(data)],
            "buildings": read_buildings(data), "commanders": commanders,"worlds":read_world_catalog(data),"colony_messages":read_colony_messages(data),
            "surface_rules":read_surface_rules(data),
            "settlement_options":read_options(data),
            "fleet_rules":read_fleet_rules(data),
            "cargo_rules":read_cargo_rules(data),
            "training_rules":read_training_rules(data),
            "battle_rules":read_battle_rules(data),
            "ground_presentation":read_ground_presentation(data),
            "space_presentation":read_space_presentation(data),
            "story_cinema":read_story_rules(data),
            "control_layouts":read_layouts(data),
            "control_buttons":read_buttons(data),
            "control_slide":read_steps(data),
            "character_set":read_characters(data),
            "initial_state_observed": {"credits": 120000, "production_workforce": 10, "date": [2927, 8, 13, 23]},
            "notice": "Recovered tables and selected routines, not a complete campaign implementation."}


def load_catalog(path):
    """Load an extracted catalog with bounded inputs and checked runtime fields."""
    from ..persistence import _unique_object
    from .worlds import validate_world_catalog
    from .colony import MESSAGE_OFFSETS
    with Path(path).open("rb") as stream:
        data = stream.read(1024*1024+1)
    if len(data)>1024*1024:
        raise GameError("Catalog exceeds size limit.")
    try:
        catalog = json.loads(data,object_pairs_hook=_unique_object)
        if not isinstance(catalog,dict) or catalog.get("sha256") not in SUPPORTED_HASHES:
            raise GameError("Unknown extracted catalog profile.")
        if "pirate_messages" in catalog:
            messages=catalog["pirate_messages"]
            if not isinstance(messages,list) or len(messages)!=10 or any(not isinstance(s,str) or len(s)>255 for s in messages):
                raise GameError("Invalid pirate announcement text.")
        if "bar_dialogs" in catalog:
            from .bar_dialogs import validate_rules
            validate_rules(catalog["bar_dialogs"])
        if 'commander_advice' in catalog:
            from .advice import validate_rules as validate_advice
            validate_advice(catalog['commander_advice'])
        if catalog["ore_names"] != dict(zip(ORE_KEYS,("Detoxin","Energon","Kremir","Lepitium","Raenium","Texon"))):
            raise GameError("Invalid catalog ore-name mapping.")
        if len(catalog["products"]) != 35 or len(catalog["commanders"]) != 12 or len(catalog["buildings"]) != 25:
            raise GameError("Incomplete catalog.")
        for i,p in enumerate(catalog["products"],1):
            if set(p) != set(ProductRecord.__dataclass_fields__) or p["id"] != i:
                raise GameError("Invalid product record structure.")
            if not isinstance(p["name"],str) or not 1<=len(p["name"])<=16 or not p["name"].isascii() or not p["name"].isprintable():
                raise GameError("Invalid product name.")
            for key,value in p.items():
                if key not in ("name","ore_costs","requirements"):
                    integer(value,key,maximum=2**32-1 if key=="price" else 32767)
            for key,maximum in (("research_state",5),("research_remaining",10000),("manufacturable",1),("special_ship",1)):
                integer(p[key],key,maximum=maximum)
            for key,keys,maximum in (("ore_costs",ORE_KEYS,65535),("requirements",SUBJECTS,255)):
                if set(p[key]) != set(keys):
                    raise GameError("Invalid product cost or skill keys.")
                for value in p[key].values():
                    integer(value,key,maximum=maximum)
        for i,c in enumerate(catalog["commanders"]):
            if c["role"] != ("pilot","builder","fighter","developer")[i//3] or c["rank"] != i%3+1:
                raise GameError("Invalid commander identity.")
            integer(c["rank"],"Rank",minimum=1,maximum=3)
            integer(c["level"],"Level",maximum=90)
            integer(c["hire_price"],"Hire price",maximum=2**32-1)
            if not isinstance(c["name"],str) or not 1<=len(c["name"])<=18:
                raise GameError("Invalid commander name.")
            if set(c["skills"]) != (set(SUBJECTS) if i//3==3 else set()):
                raise GameError("Invalid commander skills.")
            for value in c["skills"].values():
                integer(value,"Skill",maximum=255)
        for i,b in enumerate(catalog["buildings"],1):
            integer(b["id"],"Building ID",minimum=1,maximum=25)
            if b["id"]!=i or not isinstance(b["name"],str) or not 1<=len(b["name"])<=14:
                raise GameError("Invalid building identity.")
            integer(b["price"],"Building price",maximum=2**32-1)
            for key in ("width","height"):
                integer(b[key],"Building footprint",minimum=1,maximum=4)
            if not isinstance(b["tile_ids"],list) or len(b["tile_ids"])!=16:
                raise GameError("Invalid building tiles.")
            for tile in b["tile_ids"]:
                integer(tile,"Building tile",maximum=255)
            if not isinstance(b["unclassified_fields_hex"],str) or len(bytes.fromhex(b["unclassified_fields_hex"]))!=24:
                raise GameError("Invalid building rule bytes.")
            fields=bytes.fromhex(b["unclassified_fields_hex"])
            integer(fields[0],"Building research prerequisite",maximum=35)
            integer(fields[1],"Builder requirement",maximum=3)
            if not isinstance(b["unclassified_43_44"],list) or len(b["unclassified_43_44"])!=2:
                raise GameError("Invalid building priority bytes.")
            for value in b["unclassified_43_44"]:
                integer(value,"Building priority byte",maximum=255)
        if not isinstance(catalog["colony_messages"],dict) or set(catalog["colony_messages"])!={str(offset) for offset in MESSAGE_OFFSETS}:
            raise GameError("Incomplete colony message catalog; re-extract original content.")
        for message in catalog["colony_messages"].values():
            if not isinstance(message,str) or not 1<=len(message)<=255 or not message.isascii() or not message.isprintable():
                raise GameError("Invalid colony message text.")
        if not isinstance(catalog["system_names"],list) or len(catalog["system_names"])!=8:
            raise GameError("Incomplete star-system names.")
        for name in catalog["system_names"]:
            if not isinstance(name,str) or not 1<=len(name)<=8 or not name.isascii() or not name.isprintable():
                raise GameError("Invalid star-system name.")
        if not isinstance(catalog["alien_names"],list) or len(catalog["alien_names"])!=11:
            raise GameError("Incomplete civilization names.")
        for name in catalog["alien_names"]:
            if not isinstance(name,str) or not 1<=len(name)<=14 or not name.isascii() or not name.isprintable():
                raise GameError("Invalid civilization name.")
        validate_world_catalog(catalog["worlds"])
        from .commanders import validate_training_rules
        validate_training_rules(catalog["training_rules"])
        from .equipment import validate_fleet_rules
        validate_fleet_rules(catalog["fleet_rules"])
        from .cargo import validate_cargo_rules
        validate_cargo_rules(catalog["cargo_rules"])
        from .surface import validate_surface
        validate_surface(catalog)
        if "battle_rules" in catalog:
            from .ground_validation import validate_battle_rules
            validate_battle_rules(catalog["battle_rules"])
        if "space_presentation" in catalog:
            from .space_presentation import validate_space_presentation
            validate_space_presentation(catalog["space_presentation"])
        if "space_cinema" in catalog:
            from .space_cinema import validate_cinema_rules
            validate_cinema_rules(catalog["space_cinema"])
        if 'story_cinema' in catalog:
            from .story_cinema import validate_rules as validate_story_rules
            validate_story_rules(catalog['story_cinema'])
        if 'control_layouts' in catalog:
            from .control_layouts import validate_layouts
            validate_layouts(catalog['control_layouts'])
        if 'control_buttons' in catalog:
            from .control_panel import validate_buttons
            validate_buttons(catalog['control_buttons'])
        if 'character_set' in catalog:
            from .battle_results import validate_characters
            validate_characters(catalog['character_set'])
        if 'control_slide' in catalog:
            from .control_slide import validate_steps
            validate_steps(catalog['control_slide'])
        if "dialogs" in catalog:
            from .dialogs import validate_definition
            if not isinstance(catalog["dialogs"],dict) or set(catalog["dialogs"])!={str(i) for i in range(2,11)}:
                raise GameError("Incomplete scripted conversations.")
            for key,definition in catalog["dialogs"].items():
                validate_definition(definition)
                if str(definition["id"])!=key:raise GameError("Mismatched conversation ID.")
        if "ground_presentation" in catalog:
            from .ground_presentation import validate_ground_presentation
            validate_ground_presentation(catalog["ground_presentation"])
            if "battle_rules" in catalog and [row[2] for row in catalog["ground_presentation"]["animations"]]!=catalog["battle_rules"]["ground_attacks"]["animation_lengths"]:
                raise GameError("Ground sprite and simulation animation tables disagree.")
        if not isinstance(catalog["settlement_options"],list) or len(catalog["settlement_options"])!=6:
            raise GameError("Invalid colony bundle options.")
        for kind in catalog["settlement_options"]:
            integer(kind,"Colony bundle building",minimum=1,maximum=25)
        return catalog
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError) as exc:
        raise GameError(f"Invalid extracted catalog: {exc}") from exc
