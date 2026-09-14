"""Bounded persisted battle records, phase invariants and recovered rule tables."""
import struct
from ..core import GameError, integer


def _keys(value, keys, label):
    if not isinstance(value,dict) or set(value)!=set(keys):raise GameError("Invalid "+label+" fields.")


def _array(value, count, label, minimum=0, maximum=255):
    if not isinstance(value,list) or len(value)!=count:raise GameError("Invalid "+label+" length.")
    for item in value:integer(item,label,minimum=minimum,maximum=maximum)


def read_battle_rules(data):
    from .ground_setup import read_ground_rules
    from .ground_geometry import read_ground_motion
    from .ground_attacks import read_ground_attack_rules
    from .ground_movement import read_ground_movement_rules
    from .ground_controls import read_ground_control_rules
    from .aliens import read_alien_rules
    from .space_combat import read_space_rules
    result={"ground_setup":read_ground_rules(data),"ground_motion":read_ground_motion(data),
        "ground_attacks":read_ground_attack_rules(data),"ground_movement":read_ground_movement_rules(data),
        "ground_controls":read_ground_control_rules(data),"aliens":read_alien_rules(data),"space":read_space_rules(data)}
    validate_battle_rules(result)
    return result


def validate_battle_rules(rules):
    _keys(rules,("ground_setup","ground_motion","ground_attacks","ground_movement","ground_controls","aliens","space"),"battle rules")
    setup=rules["ground_setup"]
    _keys(setup,("equipment_weights","primary","secondary","group_limits"),"ground setup rules")
    _array(setup["equipment_weights"],3,"equipment weight",maximum=2**31-1)
    for key in ("primary","secondary"):_array(setup[key],4,key,maximum=65535)
    _array(setup["group_limits"],4,"group limits",minimum=1,maximum=32767)
    motion=rules["ground_motion"];_keys(motion,("x","y"),"ground motion")
    for key in ("x","y"):_array(motion[key],5,"motion",minimum=-1,maximum=1)
    if motion!={"x":[0,-1,0,1,0],"y":[0,0,-1,0,1]}:raise GameError("Unsupported ground direction convention.")
    attack=rules["ground_attacks"];_keys(attack,("cooldowns","target_coefficients","animation_lengths"),"ground attack rules")
    _array(attack["cooldowns"],4,"cooldowns",minimum=1,maximum=32767)
    _array(attack["target_coefficients"],5,"target coefficients",maximum=32767)
    _array(attack["animation_lengths"],9,"animation lengths",minimum=1)
    _keys(rules["ground_movement"],("waits",),"ground movement rules")
    _array(rules["ground_movement"]["waits"],4,"movement waits")
    _keys(rules["ground_controls"],("base_offsets",),"ground control rules")
    offsets=rules["ground_controls"]["base_offsets"]
    if not isinstance(offsets,list) or len(offsets)!=2:raise GameError("Invalid base offsets.")
    for row in offsets:_array(row,2,"base offset",maximum=32)
    names=("morgrul_base","morgrul_early_base","morgrul_spread","lisonian_base","lisonian_spread",
           "undorling_base","undorling_spread","earth_base","earth_spread")
    _keys(rules["aliens"],names,"alien rules")
    for row in rules["aliens"].values():_array(row,8,"alien force table")
    from .space_combat import RULE_START,RULE_END
    _keys(rules["space"],("bytes",),"space rules")
    _array(rules["space"]["bytes"],RULE_END-RULE_START,"space rule bytes")


def validate_ground_encounter(encounter, worlds, rules, campaign_rng):
    if encounter is None:return
    if rules is None:raise GameError("Battle tables are missing; re-extract the catalog.")
    validate_battle_rules(rules)
    _keys(encounter,("phase","destination","player_attacking","conquering_owner","search_ruins","battle","losses","next_phase"),"ground encounter")
    phase=encounter["phase"]
    if not isinstance(phase,str) or phase not in ("setup","fighting","result","closed"):raise GameError("Invalid ground encounter phase.")
    destination=encounter["destination"]
    _array(destination,3,"battle destination")
    if ":".join(map(str,destination)) not in worlds:raise GameError("Unknown saved battle world.")
    for key in ("player_attacking","search_ruins"):
        if type(encounter[key]) is not bool:raise GameError("Invalid battle context flag.")
    owner=encounter["conquering_owner"]
    if not encounter["player_attacking"] or owner is not None:integer(owner,"Conquering civilization",minimum=2,maximum=12)
    if phase=="closed":
        if encounter["next_phase"] not in ("starmap","defeat","victory"):raise GameError("Invalid closed battle continuation.")
    elif encounter["next_phase"] is not None:raise GameError("Unacknowledged battle has a campaign outcome.")
    setup=phase=="setup";battle=encounter["battle"]
    pool_keys={side+"_"+field for side in ("friendly","hostile") for field in ("totals","primary","secondary","reserve","groups")}
    live_keys={"board","done","counter","instant_kill","player_attacking","friendly_special","hostile_special","rng",
               "player_won","retreated","control_mode","selected_group","selected_friendly","pending_direction","friendly_projectiles","hostile_projectiles"}
    _keys(battle,pool_keys if setup else pool_keys|live_keys,"ground battle")
    live={};group_counts={}
    for side in ("friendly","hostile"):
        for field in ("totals","primary","secondary","reserve"):
            _array(battle[side+"_"+field],4,"ground "+field,maximum=2**63-1)
        groups=battle[side+"_groups"]
        if not isinstance(groups,list) or len(groups)>20:raise GameError("Ground battle exceeds twenty groups.")
        group_counts[side]=len(groups);live[side]=list(battle[side+"_reserve"])
        for row in groups:
            _array(row,39,"ground group")
            integer(row[0],"Ground class",minimum=1,maximum=4)
            qty=struct.unpack("<h",bytes(row[1:3]))[0]
            integer(qty,"Ground quantity",maximum=rules["ground_setup"]["group_limits"][row[0]-1])
            live[side][row[0]-1]+=qty
            if not setup:_validate_live_group(row,rules)
            elif side=="hostile":
                integer(row[8],"Setup direction",maximum=4);integer(row[9],"Setup moving flag",maximum=1)
                integer(row[10],"Setup subcell step",maximum=15)
        totals=battle[side+"_totals"]
        if any(a>b or setup and a!=b for a,b in zip(live[side],totals)):
            raise GameError("Saved battle troops and reserves do not match original totals.")
    if phase in ("setup","fighting"):
        if encounter["losses"] is not None:raise GameError("Battle losses have already been applied.")
    else:
        _keys(encounter["losses"],("friendly","hostile"),"ground losses")
        for side in ("friendly","hostile"):
            _array(encounter["losses"][side],4,"ground losses",maximum=2**63-1)
            if encounter["losses"][side]!=[a-b for a,b in zip(battle[side+"_totals"],live[side])]:
                raise GameError("Saved ground losses disagree with survivors.")
    if setup:return
    for key in ("done","instant_kill","player_attacking","player_won","retreated","selected_friendly"):
        if type(battle[key]) is not bool:raise GameError("Invalid ground battle flag.")
    if battle["player_attacking"]!=encounter["player_attacking"]:raise GameError("Ground battle changed sides.")
    if battle["done"]!=(phase in ("result","closed")):raise GameError("Battle completion and phase disagree.")
    if battle["retreated"] and (phase=="fighting" or battle["player_won"]):raise GameError("Invalid saved retreat result.")
    if phase in ("result","closed") and not battle["retreated"]:
        dead={side:all(struct.unpack("<h",bytes(row[1:3]))[0]==0 for row in battle[side+"_groups"]) for side in ("friendly","hostile")}
        if not any(dead.values()) and not battle["instant_kill"]:raise GameError("Ground result has no completed battle.")
        won=dead["hostile"] if any(dead.values()) else True
        if battle["player_won"]!=won:raise GameError("Ground winner disagrees with surviving forces.")
        for side in ("friendly","hostile"):
            if battle[side+"_projectiles"] or any(struct.unpack("<h",bytes(row[1:3]))[0]==0 and row[13]>0 for row in battle[side+"_groups"]):
                raise GameError("Ground result precedes pending impacts or death animations.")
    integer(battle["rng"],"Battle seed",maximum=2**32-1)
    if phase!="closed" and battle["rng"]!=campaign_rng:raise GameError("Battle and campaign random seeds disagree.")
    integer(battle["counter"],"Battle counter",maximum=65535)
    integer(battle["control_mode"],"Ground mode",minimum=1,maximum=4)
    integer(battle["pending_direction"],"Pending direction",maximum=4)
    index=battle["selected_group"];integer(index,"Selected group",maximum=21)
    selected_side="friendly" if battle["selected_friendly"] else "hostile"
    if index not in (0,21) and index>group_counts[selected_side]:raise GameError("Saved selection refers to a missing group.")
    board=battle["board"]
    if not isinstance(board,list) or len(board)!=16:raise GameError("Invalid ground board width.")
    valid={0,21,121}|set(range(1,group_counts["friendly"]+1))|set(range(101,101+group_counts["hostile"]))
    for column in board:
        _array(column,9,"ground board column")
        if any(code not in valid for code in column):raise GameError("Ground board refers to a missing group.")
    for side in ("friendly","hostile"):
        row=battle[side+"_special"];_array(row,39,"ground base")
        if row[0]!=5:raise GameError("Invalid special ground class.")
        integer(struct.unpack("<h",bytes(row[1:3]))[0],"Base quantity",maximum=1)
        _validate_live_group(row,rules,special=True)
        rows=battle[side+"_projectiles"]
        if not isinstance(rows,list) or len(rows)>128:raise GameError("Too many saved ground projectiles.")
        for row in rows:
            _array(row,18,"ground projectile")
            _,_,_,_,step,duration,heading,_=struct.unpack("<7hI",bytes(row))
            integer(duration,"Projectile duration",minimum=1,maximum=128)
            integer(step,"Projectile step",minimum=1,maximum=duration)
            integer(heading,"Projectile heading",maximum=15)


def _validate_live_group(row,rules,*,special=False):
    integer(row[4],"Ground column",maximum=15);integer(row[5],"Ground row",maximum=8)
    integer(row[8],"Ground direction",maximum=4);integer(row[9],"Ground moving flag",maximum=1)
    integer(row[10],"Ground subcell step",maximum=15)
    integer(struct.unpack("<h",bytes(row[6:8]))[0],"Ground cooldown",maximum=32767)
    integer(row[12],"Ground animation",maximum=8)
    integer(row[13],"Ground animation remaining",maximum=rules["ground_attacks"]["animation_lengths"][row[12]] if row[12] else 0)
    integer(row[14],"Ground animation wait",maximum=3)
    integer(row[15],"Ground order",minimum=0 if special else 1,maximum=3)
    if row[15]==2:
        integer(row[16],"Ground destination column",maximum=15);integer(row[17],"Ground destination row",maximum=8)
    if row[15]==3:integer(row[16],"Ground pursuit target",maximum=21)
    integer(row[18],"Ground path queue length",maximum=20)
    for direction in row[19:19+row[18]]:integer(direction,"Queued direction",minimum=1,maximum=4)
