"""Original scripted conversation graphs and transactional answer effects."""
from copy import deepcopy
import struct
from ..core import GameError,integer
from .aliens import fleet_at,store_fleet,route_fleet
from .campaign import random_bounded
from .catalog import DATA_FILE_OFFSET


def read_dialog_graphs(data):
    """0x23719..0x2373A: four-byte rows selected by the answer's node code.

    Script IDs 2..10 have tables. ID 1 belongs to a different conversation
    system: its apparent pointer is the end of script 10's table.
    """
    pointers=[]
    for script in range(2,11):
        offset,segment=struct.unpack_from("<HH",data,DATA_FILE_OFFSET+0xCDE+4*script)
        pointers.append(0x4AE0+16*segment+offset)
    pointers.append(DATA_FILE_OFFSET+0xCE6)
    graphs={}
    for script,start,stop in zip(range(2,11),pointers,pointers[1:]):
        if not 0<=start<stop<=len(data) or (stop-start)%4 or stop-start>400:
            raise GameError("Invalid original conversation graph pointers.")
        rows=[]
        for at in range(start,stop,4):
            count=data[at]
            if not 1<=count<=3:raise GameError("Invalid original conversation choice count.")
            rows.append(list(data[at+1:at+count+1]))
        graphs[str(script)]=rows
    return graphs


def conversation(script,graphs,questions,answers):
    """Attach decoded KERDES/VALASZ .AT records to the executable graph."""
    integer(script,"Script",minimum=2,maximum=10)
    def records(lines):
        result=[]
        for line in lines:
            if not isinstance(line,str):raise GameError("Invalid conversation text.")
            if not line:result.append(None);continue
            if len(line)<3 or not line[:2].isascii() or not line[:2].isdigit() or line[2]!=" ":
                raise GameError("Conversation line lacks its two-digit routing code.")
            result.append({"next":int(line[:2]),"text":line[3:].replace("|","\n")})
        return result
    result={"id":script,"nodes":deepcopy(graphs[str(script)]),"questions":records(questions),"answers":records(answers)}
    for row in result["nodes"]:
        for choice in row:
            if not 1<=choice<=len(result["questions"]) or result["questions"][choice-1] is None:
                raise GameError("Conversation graph refers to a missing question.")
    for question in result["questions"]:
        if question is not None and (not 1<=question["next"]<=len(result["answers"]) or result["answers"][question["next"]-1] is None):
            raise GameError("Conversation refers to a missing answer.")
    for answer in result["answers"]:
        if answer is not None and not 0<=answer["next"]<len(result["nodes"]):
            raise GameError("Conversation answer refers to a missing node.")
    return result


def start_conversation(definition):
    return {"script":definition["id"],"node":1,"answer":0,"closed":False}


def validate_definition(definition):
    if not isinstance(definition,dict) or set(definition)!={"id","nodes","questions","answers"}:
        raise GameError("Invalid conversation definition.")
    integer(definition["id"],"Script",minimum=2,maximum=10)
    for key in ("nodes","questions","answers"):
        if not isinstance(definition[key],list) or not 1<=len(definition[key])<=100:
            raise GameError("Invalid conversation table.")
    if len(definition["nodes"])<2:raise GameError("Conversation has no starting node.")
    for key,maximum in (("questions",len(definition["answers"])),("answers",len(definition["nodes"])-1)):
        for record in definition[key]:
            if record is None:continue
            if not isinstance(record,dict) or set(record)!={"next","text"}:
                raise GameError("Invalid conversation text record.")
            integer(record["next"],"Text routing code",minimum=1 if key=="questions" else 0,maximum=maximum)
            if not isinstance(record["text"],str) or len(record["text"])>255:raise GameError("Invalid conversation text.")
            if key=="questions" and definition["answers"][record["next"]-1] is None:
                raise GameError("Conversation has a missing answer.")
    for node in definition["nodes"]:
        if not isinstance(node,list) or not 1<=len(node)<=3:raise GameError("Invalid conversation choices.")
        for choice in node:
            integer(choice,"Question",minimum=1,maximum=len(definition["questions"]))
            if definition["questions"][choice-1] is None:raise GameError("Conversation has a missing question.")
    if definition["answers"][0] is None:raise GameError("Conversation has no opening text.")


def validate_dialog_state(definition,current):
    if not isinstance(current,dict) or set(current)!={"script","node","answer","closed"}:
        raise GameError("Invalid saved conversation state.")
    integer(current["script"],"Script",minimum=2,maximum=10)
    integer(current["node"],"Conversation node",maximum=len(definition["nodes"])-1)
    integer(current["answer"],"Conversation answer",maximum=len(definition["answers"]))
    if current["script"]!=definition["id"] or type(current["closed"]) is not bool or current["closed"]!=(current["node"]==0):
        raise GameError("Inconsistent saved conversation state.")
    if current["answer"]:
        answer=definition["answers"][current["answer"]-1]
        if answer is None or answer["next"]!=current["node"]:raise GameError("Saved conversation answer does not match its node.")
    elif current["node"]!=1:raise GameError("Conversation must begin at its first node.")


def choose_answer(definition,current,question):
    """Follow a displayed question to its answer text and next choice node."""
    validate_dialog_state(definition,current)
    if current["closed"]:raise GameError("This conversation is not active.")
    integer(question,"Question",minimum=1,maximum=len(definition["questions"]))
    node=current["node"]
    if not 1<=node<len(definition["nodes"]) or question not in definition["nodes"][node]:
        raise GameError("That response is not offered at this point.")
    answer=definition["questions"][question-1]["next"]
    node=definition["answers"][answer-1]["next"]
    return {"script":definition["id"],"node":node,"answer":answer,"closed":node==0}


def response_effect(state,script,question):
    """0x8005..0x8211, with explicit transaction/offer corrections.

    State here is a dispatcher work record: rng, flags/timers keyed by DS
    hex address, products, resources, complete civilizations and known_systems.
    The caller must validate the question against its current conversation.
    """
    state=deepcopy(state)
    flags,timers=state["flags"],state["timers"]
    products,resources=state["products"],state["resources"]
    def reward(product,complete):
        row=products[product-1]
        if row["research_state"]==0:
            row["research_state"]=5 if complete else 3
            if complete:row["research_remaining"]=0
    def spend(resource,amount):
        if resources[resource]<amount:raise GameError(f"This bargain requires {amount:,} {resource}.")
        resources[resource]-=amount
    if script==2:
        if question==4:
            flags["5d50"]=1;state["rng"],roll=random_bounded(state["rng"],30);timers["5d52"]=60+roll
        if question in (5,6):flags["5d50"]=1;timers["5d52"]=0
    if script==3 and question==6:
        spend("credits",16000);reward(14,False)
    if script==4 and question in (4,5):
        reward(10,True);reward(11,True);state["hunter_allowed"]=1
    if script==5 and question==4:
        quantity=products[15]["stock"]+10;integer(quantity,"Reward stock",maximum=32767)
        integer(quantity+products[15].get("queued",0),"Reward and pending stock",maximum=32767)
        reward(16,False);products[15]["stock"]=quantity
    if script==6:
        # DOS applies the diversion while merely asking about the plan (q2),
        # including the branch that subsequently refuses and kills the captives.
        # Commit it with the accepted false-warning/release bargain instead.
        if question==5:
            flags["5d3f"]=1;timers["5d7a"]=0
            race=state["civilizations"][2]
            row,state["rng"]=route_fleet(fleet_at(race,2),(3,3,0),state["rng"]);store_fleet(race,2,row)
        if question==5 and not flags["5d74"] and timers["5d72"]>0:
            total=timers["5d72"]+250;integer(total,"Delayed attack",maximum=32767);timers["5d72"]=total
    if script==7:
        # The original text names Energon for all three bargains. DOS writes
        # Kremir instead; its technology offer also takes half the entire stock.
        if question in (5,8):
            amount=min(resources["energon"],10000)
            total=resources["credits"]+amount*(10 if question==5 else 12)
            integer(total,"Trade credits",maximum=2**32-1)
            spend("energon",amount);resources["credits"]=total
        if question==9:
            spend("energon",10000);reward(21,True)
    if script==9 and question==3:
        flags["1b5"]=2;state["civilizations"][4][27]=6
    if script==10 and question==6:
        state["known_systems"][7]=0;reward(35,True);flags["1eb"]=2
    return state


def respond(definition,current,state,question):
    """Apply a valid offered choice atomically and return pending closing notices.

    Present those notices only after the player acknowledges the final answer.
    """
    updated=choose_answer(definition,current,question)
    result=response_effect(state,definition["id"],question)
    messages=closing_messages(definition["id"],result["flags"]) if updated["closed"] else []
    return updated,result,messages


def closing_messages(script,flags):
    """0x8245..0x8268: notices emitted after the final answer is acknowledged."""
    return [46] if script==9 and flags["1b5"]==2 else [48] if script==6 else []
