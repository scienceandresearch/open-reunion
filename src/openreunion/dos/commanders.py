"""Commander experience and university training recovered from DOS routines."""
from ..core import GameError, integer
from .campaign import random_bounded
from .catalog import DATA_FILE_OFFSET, SUBJECTS, pascal

ROLES = ("pilot", "builder", "fighter", "developer")
COURSES = ("Mathematics + physics", "Physics + electronics",
           "Mathematics + electronics", "Artificial intelligence")


def read_training_rules(data):
    base = DATA_FILE_OFFSET
    return {"level_caps":list(data[base+0x57E4:base+0x57F0]),
            "skill_caps":[list(data[base+0x57F0+12*i:base+0x57FC+12*i]) for i in range(1,7)],
            "course_gains":[list(data[base+0x12A+4*i:base+0x12E+4*i]) for i in range(4)],
            "level_gain":int.from_bytes(data[0x13F83:0x13F85],"little"),
            "completion_text":pascal(data,0x13ED1,255)}


def validate_training_rules(rules):
    if not isinstance(rules,dict) or set(rules)!={"level_caps","skill_caps","course_gains","level_gain","completion_text"}:
        raise GameError("Incomplete commander training rules; re-extract original content.")
    def vector(row,count,maximum):
        if not isinstance(row,list) or len(row)!=count:raise GameError("Invalid training table.")
        for value in row:integer(value,"Training table value",maximum=maximum)
    vector(rules["level_caps"],12,90)
    for key,count,size in (("skill_caps",6,12),("course_gains",4,4)):
        if not isinstance(rules[key],list) or len(rules[key])!=count:raise GameError("Invalid training table.")
        for row in rules[key]:vector(row,size,255)
    integer(rules["level_gain"],"Training level gain",maximum=255)
    text=rules["completion_text"]
    if not isinstance(text,str) or not 1<=len(text)<=255 or not text.isascii() or not text.isprintable():
        raise GameError("Invalid training completion message.")


def validate_training(training):
    if not isinstance(training,dict) or set(training)!={"course","phase","quote"}:
        raise GameError("Invalid commander training state.")
    integer(training["course"],"Training course",maximum=4)
    integer(training["phase"],"Training story phase",minimum=1,maximum=6)
    quote=training["quote"]
    if quote is not None:
        if not isinstance(quote,dict) or set(quote)!={"role","rank","course","cost"} or quote["role"] not in ROLES:
            raise GameError("Invalid university quote.")
        integer(quote["rank"],"Quoted rank",minimum=1,maximum=3)
        integer(quote["course"],"Quoted course",minimum=1 if quote["role"]=="developer" else 0,
                maximum=4 if quote["role"]=="developer" else 0)
        integer(quote["cost"],"University price",maximum=99000)


def skill_limits(rules,phase,rank):
    return rules["skill_caps"][phase-1][4*(rank-1):4*rank]


def training_available(rules,levels,ranks,skills,phase,role,course):
    """Dialog gates 0xE4F0..0xE693; caller checks hiring and university occupancy."""
    rank=ranks[role]
    if not rank:return False
    if role!="developer":
        return levels[role]<rules["level_caps"][3*ROLES.index(role)+rank-1]
    caps=skill_limits(rules,phase,rank)
    return any(gain and skills[key]<cap for gain,key,cap in zip(rules["course_gains"][course-1],SUBJECTS,caps))


def training_quote(level,seed):
    """0xEC1C..0xEC4E: asking for a quote consumes one Random(10)."""
    seed,roll=random_bounded(seed,10)
    return ((level+roll)&65535)*1000,seed


def training_purchase(credits,cost,seed):
    """0xE526..0xE570, with a native unsigned-money guard."""
    if credits<cost:raise GameError("Insufficient credits for this training quote.")
    seed,roll=random_bounded(seed,20)
    return credits-cost,50+roll,seed


def commander_hour(levels,ranks,skills,campaign,rules):
    """Mutate active levels/skills in original role order; return completed role.

    0x13F03..0x14087 runs after daily colonies, before construction and travel.
    Even commanders already at their cap consume the hourly random draw.
    Candidate hiring values are separate and do not gain experience.
    """
    for index,role in enumerate(ROLES):
        rank=ranks[role]
        if rank:
            campaign["rng"],roll=random_bounded(campaign["rng"],100)
            if roll==0 and levels[role]<rules["level_caps"][3*index+rank-1]:levels[role]+=1
    active=campaign["training_role"]
    if not active:return None
    if campaign["training_remaining"]>0:campaign["training_remaining"]-=1
    if campaign["training_remaining"]!=0:return None
    role=ROLES[active-1];rank=ranks[role]
    campaign["rng"],roll=random_bounded(campaign["rng"],4)
    levels[role]=min((levels[role]+rules["level_gain"]+roll)&65535,rules["level_caps"][3*(active-1)+rank-1])
    if role=="developer":
        training=campaign["training"]
        caps=skill_limits(rules,training["phase"],rank)
        for key,gain,cap in zip(SUBJECTS,rules["course_gains"][training["course"]-1],caps):
            skills[key]=min((skills[key]+gain)&65535,cap)
    campaign["training_role"]=0
    return role
