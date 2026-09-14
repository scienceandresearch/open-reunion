"""Recovered colony calculations. Original signed arithmetic is explicit."""
import struct

from ..core import GameError, integer
from .rules import i16
from .campaign import random_bounded, schedule_idea

MESSAGE_OFFSETS=(0x8AB,0x8E6,0x8E8,0x91F,0x945,0x96D,0x9A0,0x9E9,0xA0D,0xA2B,0xA4C,0xA73,0xA96,0xAD5)
TAX_LABELS=('None','Very low','Low','Normal','High','Difficult','Very difficult','Oppressing')


def can_change_tax(raw):
    """8C4C..8C6A: tax arrows are offered only for an owned active colony."""
    return raw[0]==1 and raw[6]!=0


def set_tax_level(raw,level):
    """8CC8..8D16: native direct selection of the original eight tax levels.

    Original +/- controls clamp 0..7. Selecting a level has the same final
    world write; income and morale effects remain in the daily colony pass.
    """
    integer(level,'Tax level',maximum=7)
    if not can_change_tax(raw):raise GameError('Taxes can be changed only at an owned active colony.')
    raw=list(raw);raw[18]=level
    return raw


def read_colony_messages(data):
    result={}
    for offset in MESSAGE_OFFSETS:
        at=0x10380+offset
        result[str(offset)]=data[at+1:at+1+data[at]].decode("ascii")
    return result


def i32(value):
    value &= 0xFFFFFFFF
    return value-0x100000000 if value & 0x80000000 else value


def trunc_div(value,divisor):
    if not divisor:
        raise GameError("Original colony calculation has a zero divisor.")
    return (abs(value)//abs(divisor))*(-1 if (value<0)!=(divisor<0) else 1)


def scaled(value,numerator,denominator):
    return i32(trunc_div(i32(value*numerator),denominator))


def i8(value):
    value &= 255
    return value-256 if value&128 else value


def daily_tax(raw):
    """0x117E2..0x1187E: original Real48 expression followed by Round.

    For normal colony ranges the integral product is exact in Real48. Preserve
    nearest rounding with halves away from zero, without binary float drift.
    """
    population=struct.unpack_from("<i",bytes(raw),13)[0]
    numerator=population*i8(raw[18])*i8(raw[17])*(i8(raw[19])+40)
    if abs(numerator)>=2**39:
        raise GameError("Colony tax exceeds the verified exact Real48 integer range.")
    return ((abs(numerator)+100000)//200000)*(-1 if numerator<0 else 1)


def population_capacity(population,morale,housing,food,medical,care_multiplier,university_count):
    """0x11699..0x117E1, after daily service/hazard effects."""
    capacity=scaled(housing,i8(morale)+200,230)
    if population>food:
        capacity=min(capacity,i32(food+5000))
    capacity=min(capacity,i32(trunc_div(medical,care_multiplier)+5000),200000)
    if i8(morale)<30:
        capacity=trunc_div(capacity,2)
    if i8(morale)<20:
        capacity=min(capacity,trunc_div(population,2))
    if i8(morale)<10:
        capacity=500
    if university_count==0:
        capacity=min(capacity,80000)
    return capacity


def population_step(raw,capacity,target_morale):
    """0x118AD..0x119B0, after daily service/hazard effects."""
    raw=list(raw)
    population=struct.unpack_from("<i",bytes(raw),13)[0]
    if capacity>population:
        growth=scaled(i32(capacity-population),scaled(population,1000,capacity),capacity)
    else:
        growth=scaled(i32(capacity-population),1000,population)
    raw[13:17]=struct.pack("<I",(population+growth)&0xFFFFFFFF)
    raw[19]=(raw[19]+trunc_div(i16(target_morale-i8(raw[19])),10))&255
    if i8(raw[19])<target_morale:
        raw[19]=(raw[19]+1)&255
    if i8(raw[19])>target_morale:
        raw[19]=(raw[19]-3)&255
    raw[19]=max(0,min(69,i8(raw[19])))
    return raw


def building_counts(buildings,identity):
    """DS 0x7920..0x79E7: completed buildings counted by operating flag/type."""
    counts=[[0]*25 for _ in range(2)]
    for row in buildings:
        if row[1:4]==list(identity) and row[6]==0:
            if not 1<=row[0]<=25 or row[8] not in (0,1):
                raise GameError("Invalid completed building type or operating flag.")
            counts[row[8]][row[0]-1]+=1
    return counts


def clear_colony(raw,buildings,identity):
    """World/building part of 0x1E887 and 0x1EC25; fleet cleanup follows later."""
    for index in [0,1,4,5,6,7,10,11,*range(13,20),*range(27,59)]:
        raw[index]=0
    buildings[:]=[row for row in buildings if row[1:4]!=list(identity)]


def colony_day(raw,buildings,identity,campaign,products,*,screen=0):
    """Daily colony branch 0x1109C..0x11AED, before power and surveys.

    Returns earned tax, original embedded-message offsets and loss state.
    The original selected-world droid write is corrected to the affected world.
    Fleet cleanup and the game's defeat screen remain separate integrations.
    """
    notices=[]
    lost=False
    counts=building_counts(buildings,identity)[1]
    count=lambda kind:counts[kind-1]
    def roll(limit):
        campaign["rng"],result=random_bounded(campaign["rng"],limit)
        return result
    def population():
        return struct.unpack_from("<i",bytes(raw),13)[0]
    def deaths(amount):
        raw[13:17]=struct.pack("<I",(population()-amount)&0xFFFFFFFF)
    def warning(chance,offset):
        if roll(chance)==0:
            notices.append(offset)
    def lose():
        nonlocal lost
        clear_colony(raw,buildings,identity)
        lost=True
    target=(7-i8(raw[18]))*10
    housing=10000+count(7)*7000
    food=20000+count(21)*20000+count(16)*8000
    medical=20000+count(15)*20000
    if 0<i8(raw[20])<100:
        raw[20]-=1
    care=2 if raw[20]==0 else 1
    if raw[20]==0 and count(24)==0:
        warning(5,0x8AB)
        target=min(target-10,25)
    if i32(care*population())>medical:
        warning(5,0x8E8)
        target=min(target-10,25)
        deaths(200)
    for threshold,penalty in ((30000,10),(60000,10),(100000,20),(150000,20)):
        if population()>threshold:
            target-=penalty
    target+=10*sum(count(kind)>0 for kind in (8,9,10,14))
    for threshold,kind,offset in ((50000,9,0x91F),(70000,13,0x945)):
        if population()>threshold and count(kind)==0:
            warning(5,offset)
            target-=20
    if identity[1]<=2 and count(19)==0:
        if roll(5)==0:
            deaths(500+roll(trunc_div(population(),4)))
            schedule_idea(campaign,products,30,50,25)
            notices.append(0x96D)
        target-=40
    if raw[20]==100 and products[27]["research_state"]<5 and screen!=20 and roll(10)==0:
        selected=None
        for index,row in enumerate(buildings):
            if row[1:4]==list(identity) and row[6]==0 and row[0]!=1 and roll(10)==0:
                selected=index
        if selected is not None:
            del buildings[selected]
            mines=sum(row[1:4]==list(identity) and row[6]==0 and row[0] in (4,25) for row in buildings)
            if raw[10]>mines:
                raw[10]-=1
            deaths(roll(trunc_div(population(),20)))
            schedule_idea(campaign,products,28,250,100)
            raw[19]=(raw[19]-10)&255
            notices.append(0x9A0)
        else:
            notices.append(0x9E9)
        target-=30
    if population()>food:
        warning(3,0xA2B)
        target=min(target-15,25)
        raw[19]=(raw[19]-2)&255
    if population()>housing:
        warning(3,0xA4C)
        target=min(target-10,25)
        raw[19]=(raw[19]-2)&255
    target=max(target,0)
    capacity=population_capacity(population(),raw[19],housing,food,medical,care,count(13))
    tax=daily_tax(raw)
    if roll(i8(raw[17])**2)<100:
        raw[17]=(raw[17]+1)&255
    if i8(raw[17])>60:
        raw[17]=60
    raw[:]=population_step(raw,capacity,target)
    unrest=struct.unpack_from("<i",bytes(raw),51)[0]
    if i8(raw[19])<10:
        unrest=min(i32(unrest+1),5)
        if unrest==5 and roll(3)<2:
            unrest=4
        raw[51:55]=struct.pack("<I",unrest&0xFFFFFFFF)
        if unrest==5:
            notices.append(0xA73)
            lose()
        else:
            notices.append(0xA96)
    else:
        raw[51:55]=bytes(4)
    if population()<1000:
        notices.append(0xAD5)
        lose()
    return {"tax":tax,"notices":notices,"lost":lost,"target_morale":target,"capacity":capacity}


def building_rules(definition):
    """Interpret the recovered fields in the original 63-byte building table."""
    raw=bytes.fromhex(definition["unclassified_fields_hex"])
    return {"category":raw[2],"workers":struct.unpack_from("<h",raw,16)[0],
            "power":struct.unpack_from("<i",raw,18)[0],"output":struct.unpack_from("<h",raw,22)[0],
            "priority":definition["unclassified_43_44"][0]}


def industrial_output(buildings,definitions,identity):
    """Actual Builder Plant capacity, without the DOS word-product overflow.

    Keep the original two percentage truncations. Derive capacity from saved
    building condition/performance so old wrapped world caches are harmless.
    The full result is not limited by the legacy world's two-byte cache.
    """
    plant=next((d for d in definitions if d['id']==22),None)
    if plant is None:return 0
    base=building_rules(plant)['output']
    return sum((row[7]*base//100)*row[13]//100 for row in buildings
               if row[0]==22 and row[1:4]==list(identity) and row[6]==0 and row[8])


def allocate_colony(raw,buildings,definitions,identity):
    """0x2D8D4..0x2E004: staffing, power shedding and per-building performance.

    Mutates only completed buildings at this world and its industrial-output
    word. Returns the capacity written to the original local defense record,
    used by the session's local defense record. Builder Plant multiplication
    uses wide arithmetic; all other allocation and shedding rules are retained.
    """
    rules={definition["id"]:building_rules(definition) for definition in definitions}
    local=[row for row in buildings if row[1:4]==list(identity) and row[6]==0]
    capacity=0
    for row in local:
        if row[0] not in rules:
            raise GameError("Unknown building type in colony allocation.")
        row[8]=1
        capacity=(capacity+{11:20,4:10,5:5,25:10}.get(row[0],0))&65535
    population=struct.unpack_from("<i",bytes(raw),13)[0] or 1

    def totals():
        active=[row for row in local if row[8]]
        workers=max(population,i32(sum(rules[row[0]]["workers"] for row in active)))
        production=0
        demand=0
        for row in active:
            rule=rules[row[0]]
            if rule["category"] in (1,8):
                production=i32(production+scaled(scaled(rule["output"],population,workers),row[7],100))
            demand=i32(demand+scaled(rule["power"],population,workers))
        production=i32(production+raw[11]*10000) or 1
        return workers,production,max(demand,production)

    workers,production,demand=totals()
    disabled=[]
    while i32(production*2)<demand:
        candidates=[row for row in local if row[8]]
        if not candidates:
            raise GameError("Colony power shedding cannot make further progress.")
        # <= in the DOS scan means the last tied minimum priority is disabled.
        selected=min(range(len(candidates)),key=lambda i:(rules[candidates[i][0]]["priority"],-i))
        row=candidates[selected]
        row[8]=0
        disabled.append(row[0])
        workers,production,demand=totals()

    for row in local:
        if not row[8]:
            continue  # DOS retains prior worker/power/performance bytes here.
        rule=rules[row[0]]
        assigned=scaled(rule["workers"],population,workers)
        energy=scaled(rule["power"],production,demand)
        row[9:11]=struct.pack("<H",assigned&65535)
        row[11:13]=struct.pack("<H",energy&65535)
        performance=scaled(100,population,workers) if rule["category"] in (1,8) else scaled(scaled(100,production,demand),population,workers)
        row[13]=performance&255
    output=industrial_output(local,definitions,identity)
    # Preserve the legacy record shape. Construction uses the full derived
    # output, never this bounded compatibility cache.
    raw[4:6]=struct.pack("<H",min(65535,output))
    return {"population":population,"worker_demand":workers,"power_supply":production,
            "power_demand":demand,"industrial_output":output,"defense_capacity":capacity,"disabled_types":disabled}
