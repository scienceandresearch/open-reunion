"""Original cinematic script controller, including its shared RNG consumption."""
from copy import deepcopy
import struct
from ..core import GameError, integer
from .catalog import DATA_FILE_OFFSET
from .campaign import random_bounded
from .ground_validation import _keys, _array


def read_cinema_rules(executable, definitions):
    if len(definitions) != 14000:raise GameError("Space animation script file must contain 25 fixed-size records.")
    rules = {"assets": [list(executable[DATA_FILE_OFFSET+0x555B+5*i:DATA_FILE_OFFSET+0x5560+5*i]) for i in range(1,26)],
        "repeats": list(struct.unpack_from("<25h", executable, DATA_FILE_OFFSET+0x569C)),
        "pool": int.from_bytes(executable[0x159D3:0x159D7], "little"),
        "scripts": [[list(definitions[560*i+4*j:560*i+4*j+4]) for j in range(140)] for i in range(25)]}
    validate_cinema_rules(rules);return rules


def validate_cinema_rules(rules):
    _keys(rules, ("assets", "repeats", "pool", "scripts"), "space cinematic rules")
    _array(rules["repeats"],25,"cinematic repeats",maximum=32767)
    if rules["pool"] != sum(1<<i for i in range(2,26)):raise GameError("Unsupported cinematic selection pool.")
    if not isinstance(rules["assets"],list) or len(rules["assets"]) != 25:raise GameError("Incomplete cinematic metadata.")
    for row in rules["assets"]:
        _array(row,5,"cinematic asset")
        frames,width,height,x,y = row
        integer(frames,"Animation frame count",minimum=1,maximum=140)
        integer(width,"Animation width",minimum=1,maximum=160)
        integer(height,"Animation height",minimum=1,maximum=151)
        if not 160 <= x < 320 or not 49 <= y < 200 or x+width > 320 or y+height > 200:
            raise GameError("Cinematic asset exceeds its display region.")
    if not isinstance(rules["scripts"],list) or len(rules["scripts"]) != 25:raise GameError("Incomplete cinematic scripts.")
    for rows in rules["scripts"]:
        if not isinstance(rows,list) or len(rows) != 140:raise GameError("Invalid cinematic script length.")
        terminal = False
        for row in rows:
            _array(row,4,"cinematic instruction")
            if terminal:continue # Preserve padding; it is not executed.
            asset,frame,sound,delay = row
            if delay == 255:terminal = True;continue
            integer(asset,"Cinematic asset",maximum=25);integer(sound,"Cinematic sound",maximum=255)
            integer(delay,"Cinematic delay",maximum=127)
            if asset:integer(frame,"Cinematic frame",minimum=1,maximum=rules["assets"][asset-1][0])
        if not terminal:raise GameError("Cinematic script has no terminator.")


def start_cinema(seed, rules):
    """0x761E..0x765E, after the initializer's first numerical space frame."""
    seed, selected = random_bounded(seed,25);selected += 1
    return {"sequence":selected,"row":1,"wait":0,"repeats":rules["repeats"][selected-1],
        "remaining":rules["pool"] & ~(1<<selected),"transition":[2000,0,0,0]}, seed


def validate_cinema(state, rules):
    _keys(state,("sequence","row","wait","repeats","remaining","transition"),"space cinematic state")
    integer(state["sequence"],"Cinematic sequence",maximum=25)
    integer(state["row"],"Cinematic row",minimum=1,maximum=140)
    integer(state["wait"],"Cinematic wait",maximum=32767)
    integer(state["repeats"],"Cinematic repetitions",maximum=32767)
    integer(state["remaining"],"Cinematic pool",maximum=2**32-1)
    if state["remaining"] & ~rules["pool"]:raise GameError("Cinematic pool contains an unavailable sequence.")
    if state["sequence"]:
        if state["repeats"] > rules["repeats"][state["sequence"]-1]:raise GameError("Too many cinematic repetitions.")
        rows = rules["scripts"][state["sequence"]-1]
        end = next(i+1 for i,row in enumerate(rows) if row[3] == 255)
        if state["row"] >= end:raise GameError("Cinematic cursor reached its terminator.")
    _array(state["transition"],4,"Cinematic transition",maximum=2000)
    left,right,top,bottom = state["transition"]
    if left < 1000 and (left > right or top > bottom or right > 319 or bottom > 199):
        raise GameError("Invalid cinematic transition rectangle.")


def cinema_tick(state, seed, rules):
    """0x162C7..0x165EA, after simulation if the space fight is still active.

    Requests retain original screen coordinates. Loading/unloading assets and
    playing sounds have no additional RNG calls in the recovered helpers.
    """
    validate_cinema(state,rules);state = deepcopy(state);events = []
    left,right,top,bottom = state["transition"]
    if left < 1000:
        width,height = right-left+1,bottom-top+1
        if right-left > 20 and bottom-top > 20:
            for x,y,w,h in ((left,top,width,10),(left,bottom-10,width,11),
                            (left,top,10,height),(right-10,top,11,height)):
                events.append({"kind":"cinema_clear","rect":[x,y,w,h]})
            state["transition"] = [left+10,right-10,top+10,bottom-10]
        else:
            events.append({"kind":"cinema_clear","rect":[left,top,width,height]})
            state["transition"][0] = 2000
    if not state["sequence"]:return state,seed,events
    if state["wait"]:
        state["wait"] -= 1;return state,seed,events
    previous = state["sequence"];state["row"] += 1
    row = rules["scripts"][previous-1][state["row"]-1]
    if row[3] == 255:
        if not state["remaining"]:state["remaining"] = rules["pool"]
        selected = previous
        if not state["repeats"]:
            seed, selected = random_bounded(seed,25);selected += 1
            attempts = 0
            while not state["remaining"] & (1<<selected):
                seed, selected = random_bounded(seed,24);selected += 2;attempts += 1
                if attempts > 4096:raise GameError("Cinematic selection exceeded its bounded retry limit.")
            state["remaining"] &= ~(1<<selected)
        else:state["repeats"] -= 1
        if selected != previous:
            state.update(sequence=selected,row=1,repeats=rules["repeats"][selected-1],transition=[160,319,49,199])
            seed, delay = random_bounded(seed,10);state["wait"] = 10+delay
            events.append({"kind":"cinema_sequence","id":selected})
            return state,seed,events
        state["row"] = 1;row = rules["scripts"][previous-1][0]
    asset,frame,sound,delay = row
    if asset:
        events.append({"kind":"cinema_frame","asset":asset,"frame":frame})
        if sound:events.append({"kind":"sound","id":sound})
        state["wait"] = delay
    return state,seed,events


def advance_cinema_view(view,events):
    view=deepcopy(view)
    for event in events:
        if event["kind"]=="cinema_clear":view["clears"].append(list(event["rect"]))
        elif event["kind"]=="cinema_frame":
            if view["clears"]:view["black"]=True
            view["clears"]=[];view["picture"]=[event["asset"],event["frame"]]
    return view


def validate_cinema_view(view,rules):
    _keys(view,("picture","clears","black"),"cinematic view")
    if type(view["black"]) is not bool:raise GameError("Invalid cinematic background.")
    if view["picture"] is not None:
        _array(view["picture"],2,"cinematic picture",minimum=1)
        asset,frame=view["picture"]
        if asset>25 or frame>rules["assets"][asset-1][0]:raise GameError("Unknown cinematic picture.")
    if not isinstance(view["clears"],list) or len(view["clears"])>32:raise GameError("Too many cinematic transition strips.")
    for rect in view["clears"]:
        _array(rect,4,"cinematic clear rectangle",maximum=320)
        x,y,width,height=rect
        if width<1 or height<1 or x+width>320 or y+height>200:raise GameError("Cinematic clear exceeds the screen.")
