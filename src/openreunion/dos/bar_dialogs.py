"""Bar-specific .LOC dialogue graphs, dynamic choices and purchase effects."""
from copy import deepcopy
import struct

from ..core import GameError, integer
from .bar import agent_status
from .campaign import random_bounded
from .catalog import DATA_FILE_OFFSET

SOCIAL_FLAGS = tuple(f"{at:x}" for at in (*range(0x773E,0x774A),0x5D91,0x5D99))
RACE_QUESTIONS = {10:3,11:4,12:5,13:6,15:7,16:8,17:9,18:10,26:12}


def read_rules(data, text_reader):
    pointers=[]
    for agent in range(1,11):
        offset,segment=struct.unpack_from("<HH",data,DATA_FILE_OFFSET+0x3D6+4*agent)
        pointers.append(0x4AE0+16*segment+offset)
    pointers.append(DATA_FILE_OFFSET+0x3DA)
    definitions={}
    def records(lines):
        result=[]
        for line in lines:
            if not line:result.append(None);continue
            if len(line)<3 or not line[:2].isascii() or not line[:2].isdigit() or line[2]!=" ":
                raise GameError("Invalid bar dialogue routing code.")
            result.append({"next":int(line[:2]),"text":line[3:].replace("|","\n")})
        return result
    for agent,start,stop in zip(range(1,11),pointers,pointers[1:]):
        if not 0<=start<stop<=len(data) or (stop-start)%6 or stop-start>600:
            raise GameError("Invalid bar graph pointers.")
        nodes=[]
        for at in range(start,stop,6):
            count=data[at]
            if count>5:raise GameError("Invalid bar graph count.")
            nodes.append(list(data[at+1:at+1+count]))
        definitions[str(agent)]={"nodes":nodes,"questions":records(text_reader(f"KERDES{agent}.LOC")) if agent!=8 else [],
                                 "answers":records(text_reader(f"VALASZ{agent}.LOC")) if agent!=8 else []}
    result={"definitions":definitions,"prices":list(struct.unpack_from("<4I",data,DATA_FILE_OFFSET+0x414)),
        "multipliers":list(data[DATA_FILE_OFFSET+0x408:DATA_FILE_OFFSET+0x414]),
        "contracts":[s[3:].replace("|","\n") for s in text_reader("PIRATE.TXT")[10:20]],
        "quote_prefixes":[data[at+4:at+1+data[at]].decode("ascii") for at in (0x14DD0,0x14DE8)],
        "quote_suffix":data[0x14DE0:0x14DE0+data[0x14DDF]].decode("ascii"),
        "names":{str(agent):data[at+1:at+1+data[at]].decode("ascii") for agent,at in
                 ((1,0x4BE2),(2,0x4BFE),(7,0x4C0C),(9,0x4BF0))}}
    validate_rules(result);return result


def validate_rules(rules):
    if not isinstance(rules,dict) or set(rules)!={"definitions","prices","multipliers","contracts","quote_prefixes","quote_suffix","names"}:
        raise GameError("Invalid bar dialogue rules.")
    for key,size,maximum in (("prices",4,2**32-1),("multipliers",12,255)):
        values=rules[key]
        if not isinstance(values,list) or len(values)!=size:raise GameError("Invalid intelligence pricing table.")
        for value in values:integer(value,key,maximum=maximum)
    for key,size in (("contracts",10),("quote_prefixes",2)):
        if not isinstance(rules[key],list) or len(rules[key])!=size or any(not isinstance(s,str) or len(s)>255 for s in rules[key]):
            raise GameError("Invalid bar text table.")
    if not isinstance(rules["quote_suffix"],str) or len(rules["quote_suffix"])>30:raise GameError("Invalid quote suffix.")
    if not isinstance(rules["names"],dict) or set(rules["names"])!={"1","2","7","9"}:raise GameError("Invalid bar names.")
    for name in rules["names"].values():
        if not isinstance(name,str) or not 1<=len(name)<=13 or not name.isascii() or not name.isprintable():raise GameError("Invalid agent name.")
    definitions=rules["definitions"]
    if not isinstance(definitions,dict) or set(definitions)!={str(i) for i in range(1,11)}:raise GameError("Incomplete bar dialogues.")
    for key,definition in definitions.items():
        if not isinstance(definition,dict) or set(definition)!={"nodes","questions","answers"}:raise GameError("Invalid bar definition.")
        for field in definition:
            if not isinstance(definition[field],list) or len(definition[field])>100:raise GameError("Invalid bar text/graph size.")
        if len(definition["nodes"])<2:raise GameError("Bar conversation lacks an opening node.")
        if key=="8":
            if definition["questions"] or definition["answers"] or any(definition["nodes"][1:]):raise GameError("Unexpected placeholder conversation.")
            continue
        for field in ("questions","answers"):
            for record in definition[field]:
                if record is None:continue
                if not isinstance(record,dict) or set(record)!={"next","text"}:raise GameError("Invalid bar text record.")
                integer(record["next"],"Bar routing",minimum=1 if field=="questions" else 0,
                        maximum=len(definition["answers"]) if field=="questions" else len(definition["nodes"])-1)
                if not isinstance(record["text"],str) or len(record["text"])>255:raise GameError("Invalid bar text.")
                if field=="questions" and definition["answers"][record["next"]-1] is None:raise GameError("Missing bar answer.")
        for node in definition["nodes"]:
            if not isinstance(node,list) or not 1<=len(node)<=5:raise GameError("Invalid bar node.")
            for question in node:
                integer(question,"Bar question",minimum=1,maximum=len(definition["questions"]))
                if definition["questions"][question-1] is None:raise GameError("Missing bar question.")


def eligible_targets(work):
    relation=lambda race:work["civilizations"][race-2][27] in (2,4)
    signed=lambda value:value if value<128 else value-256
    result={race:relation(race) for race in (3,4,5,6,7,8,9,10,12)}
    result[3] &= signed(work["known_systems"][2])>0
    result[4] &= signed(work["civilizations"][1][27])>=0
    result[5] &= signed(work["civilizations"][1][27])>=0
    result[6] &= not work["flags"]["5d90"]
    return result


def available_agents(work):
    if work["bar"] is None or work["bar"]["social"] is None:return []
    return [i for i in range(1,11) if i!=8 and agent_status(work,i) in (0,2) and work["bar"]["agents"][i-1]["remaining"]==0]


def current_contract(work):
    # Original date key has gaps, but orders valid calendars chronologically.
    current=tuple(work["date"]);chosen=0
    for index,row in enumerate(work["bar"]["contracts"],1):
        start=(struct.unpack_from("<h",bytes(row),14)[0],*row[16:19])
        end=(struct.unpack_from("<h",bytes(row),19)[0],*row[21:24])
        if start<current<end:chosen=index
    return chosen


def initialize_contracts(work):
    year,month,day,hour=work["date"]
    for row in work["bar"]["contracts"]:
        for at in (14,19):
            y=struct.unpack_from("<h",bytes(row),at)[0]+year
            m,d,h=(row[at+2]+month,row[at+3]+day,row[at+4]+hour)
            d,h=d+h//24,h%24;m,d=m+(d-1)//30,(d-1)%30+1;y,m=y+(m-1)//12,(m-1)%12+1
            integer(y,"Contract year",minimum=1,maximum=32767)
            row[at:at+5]=[*struct.pack("<h",y),m,d,h]


def starting_node(work,agent):
    social=work["bar"]["social"];flags=work["flags"];node=1
    s=lambda at:social[f"{at:x}"]
    if agent==1 and s(0x773E):node=3 if flags["164"]==2 and work["bar"]["agents"][1]["remaining"]<=0 else 2
    if agent==2:
        if s(0x7740) and not s(0x773F):node=2
        if s(0x773F):node=3 if any(eligible_targets(work).values()) else 10
    if agent==3 and s(0x7749):node=2
    if agent==4 and not s(0x7741) and flags["221"]==2:node=3
    if agent==5 and s(0x7742) and not s(0x7743) and all(work["civilizations"][i][27]==2 for i in (5,6)):node=2
    if agent==6:
        if flags["164"]==2 and not s(0x7740):node=2
        if not s(0x7742) and 1 in work["known_systems"][4:6] and not flags["5d98"]:node=4
        if flags["221"]==2 and not s(0x7741) and not s(0x7747):node=3
    if agent==7:
        if s(0x7748):node=2 if s(0x7744) else 6
        if s(0x7748) and s(0x7745):node=3
    if agent==9 and s(0x7741):node=2 if not s(0x7746) else 3 if current_contract(work) else 6
    return node


def choices(work,rules,current):
    if current["phase"]!="choices":return []
    if current["agent"]==2 and current["node"] in (6,7):
        targets=eligible_targets(work)
        if current["node"]==7:return [q for q in (15,16,17,18) if targets[RACE_QUESTIONS[q]]]
        return [
            q for q in (10,11,12,13,14,26) if (any(targets[r] for r in (7,8,9,10)) if q==14 else targets[RACE_QUESTIONS[q]])]
    return list(rules["definitions"][str(current["agent"])]["nodes"][current["node"]])


def open_conversation(work,agent):
    integer(agent,"Bar agent",minimum=1,maximum=10)
    if agent not in available_agents(work):raise GameError("This character is not available in the bar.")
    return {"agent":agent,"node":starting_node(work,agent),"phase":"choices","question":0,"answer":0,
            "race":0,"quote":None,"contract":current_contract(work)}


def answer_effect(work,current,question,rules):
    """Main choice effects 0x6FCB..0x7528, before the answer is displayed."""
    work=deepcopy(work);current=deepcopy(current);agent=current["agent"]
    answer=rules["definitions"][str(agent)]["questions"][question-1]["next"]
    bar=work["bar"];social=bar["social"];flags=work["flags"]
    def spend(amount):
        if work["resources"]["credits"]<amount:raise GameError(f"This choice requires {amount:,} credits.")
        work["resources"]["credits"]-=amount
    def rename(index):
        name=rules["names"][str(index)].encode("ascii")
        bar["agents"][index-1]["prefix"][:len(name)+1]=[len(name),*name]
    def delay(index,parameter):
        work["rng"],roll=random_bounded(work["rng"],100)
        bar["agents"][index-1].update(remaining=100+roll,parameter=parameter)
    if agent==1:
        if question==1:social["773e"]=1;rename(1)
        if question==2:answer=6 if social["773f"] else 4
        if question==4:flags["164"]=1;work["timers"]["5d8a"]=200
    if agent==2:
        if question==8:social["773f"]=1;work["known_systems"][2]=0
        if question in (5,6,7):spend({5:30000,6:40000,7:50000}[question])
        if question in RACE_QUESTIONS:current["race"]=RACE_QUESTIONS[question];current["quote"]=None
        if question==23:
            quote=current["quote"]
            if quote is None:raise GameError("An intelligence quote is required.")
            spend(quote["price"]);delay(2,quote["kind"]*20+quote["race"])
    if agent==3:social["7749"]=1
    # DOS derives this value for every choice, irrespective of selected agent.
    tip=0
    if 0<work["civilizations"][1][27]<128:tip=1
    if flags["5d5e"] and not flags["5d6c"]:tip=2
    if work["known_systems"][1]==1 and work["civilizations"][3][27]==0:tip=3
    if work["known_systems"][3]==1 and not social["5d91"]:tip=4
    if agent==4:
        if question==1:answer=3 if tip else 2
        if question==3:
            spend(500);answer=tip+4
            if tip==3:work["planet_visibility"][0x47E2-0x47D6]=0
        if question==5:social["7741"]=1;rename(9);spend(500)
    if agent==5 and question in (5,6):social["7743"]=1;delay(5,question-4)
    if agent==6:
        if question in (8,10):social["7740"]=1
        if question==10:rename(2)
        if question==11:social["7747"]=1
        if question==13:social["7742"]=1;spend(5000)
        if question in (6,15):
            answer=3
            if work["civilizations"][2][27]==0 or work["civilizations"][3][27]==0:answer=8
            if work["civilizations"][0][27]==0:answer=7
    if agent==7:
        if question in (4,6):spend(100000);delay(7,2)
        if question==5:social["7745"]=1
        social["7748"]=1;rename(7)
    if agent==9:
        if question==2:
            if not social["7746"]:initialize_contracts(work)
            social["7746"]=1
        if question in (5,6,7,8):
            selected=current["contract"]
            if not selected or selected!=current_contract(work):raise GameError("This pirate contract is no longer available.")
            tier=bar["contracts"][selected-1][12]
            if question==5 or tier<=question-5:
                if question!=5:spend({6:10000,7:50000,8:100000}[question])
                answer=6;delay(9,selected+(10 if question==5 else 0))
    if agent==10:
        if question in (3,4,5):spend({3:100000,4:150000,5:200000}[question])
        if question==8:flags["23c"]=1
        if question in (9,10):social["7744"]=1;social["5d99"]=1;flags["23c"]=1
    current.update(question=question,answer=answer,phase="answer")
    if agent==2 and 10<=answer<=13:
        race=current["race"];integer(race,"Quoted civilization",minimum=2,maximum=12)
        kind=answer-9;price=rules["prices"][kind-1]*rules["multipliers"][race-1]
        integer(price,"Intelligence quote",maximum=2**32-1)
        work["rng"],wording=random_bounded(work["rng"],2)
        current["quote"]={"race":race,"kind":kind,"price":price,"wording":wording}
        bar["agents"][1]["parameter"]=20*kind+race
    current["node"]=rules["definitions"][str(agent)]["answers"][answer-1]["next"]
    return work,current


def choose(work,current,question,rules):
    integer(question,"Bar question",minimum=1,maximum=100)
    if question not in choices(work,rules,current):raise GameError("That response is not currently offered.")
    return answer_effect(work,current,question,rules)


def acknowledge(work,current):
    if current["phase"]!="answer":raise GameError("No bar answer is waiting.")
    if not current["node"]:return None
    current=deepcopy(current);current["phase"]="choices";current["contract"]=current_contract(work)
    return current


def answer_text(current,rules):
    if not current["answer"]:return ""
    quote=current["quote"]
    if current["agent"]==2 and 10<=current["answer"]<=13:
        return rules["quote_prefixes"][quote["wording"]]+str(quote["price"])+rules["quote_suffix"]
    return rules["definitions"][str(current["agent"])]["answers"][current["answer"]-1]["text"]


def question_text(current,question,rules):
    if current["agent"]==9 and current["node"]==4 and question==4 and current["contract"]:
        return rules["contracts"][current["contract"]-1]
    return rules["definitions"][str(current["agent"])]["questions"][question-1]["text"]


def validate_conversation(current,work,rules):
    if current is None:return
    if not isinstance(current,dict) or set(current)!={"agent","node","phase","question","answer","race","quote","contract"}:
        raise GameError("Invalid saved bar conversation.")
    integer(current["agent"],"Bar agent",minimum=1,maximum=10)
    if current["agent"]==8:raise GameError("Placeholder agent has no conversation.")
    definition=rules["definitions"][str(current["agent"])]
    integer(current["node"],"Bar node",maximum=len(definition["nodes"])-1)
    integer(current["question"],"Bar question",maximum=len(definition["questions"]))
    integer(current["answer"],"Bar answer",maximum=len(definition["answers"]))
    integer(current["race"],"Bar civilization",maximum=12)
    integer(current["contract"],"Bar contract",maximum=10)
    if current["phase"] not in ("choices","answer") or current["phase"]=="choices" and current["node"]==0:
        raise GameError("Invalid bar conversation phase.")
    if current["answer"]:
        if not current["question"] or definition["questions"][current["question"]-1] is None:raise GameError("Missing chosen bar question.")
        record=definition["answers"][current["answer"]-1]
        if record is None or record["next"]!=current["node"]:raise GameError("Bar answer and node disagree.")
    elif current["phase"]!="choices" or current["question"] or current["node"]!=starting_node(work,current["agent"]):
        raise GameError("Invalid opening bar node.")
    quote=current["quote"]
    if quote is not None:
        if not isinstance(quote,dict) or set(quote)!={"race","kind","price","wording"}:raise GameError("Invalid saved intelligence quote.")
        for key,low,high in (("race",2,12),("kind",1,4),("price",0,2**32-1),("wording",0,1)):
            integer(quote[key],key,minimum=low,maximum=high)
        if current["agent"]!=2 or current["race"]!=quote["race"] or quote["price"]!=rules["prices"][quote["kind"]-1]*rules["multipliers"][quote["race"]-1]:
            raise GameError("Saved quote disagrees with its original price.")
    if current["agent"]==2 and 10<=current["answer"]<=13 and (quote is None or quote["kind"]!=current["answer"]-9):
        raise GameError("Quoted answer lacks its saved price.")
