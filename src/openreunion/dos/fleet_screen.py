"""Original ship overview and a transactional new-group draft."""
from dataclasses import dataclass,field
import struct

from ..core import GameError
from .equipment_screen import fleet_name
from .navigation import remaining_hours
from .production_screen import display_number

CHANGE_RECT=(0,188,200,12)
NEW_NAME_RECT=(132,91,108,13)  # Widen DOS's 93 pixels for the shared 17-character limit.
NEW_TYPE_RECT=(132,117,93,11)
SYSTEM_SHORT=('Amnes','Phnx ','Mirac','Antar','Orion','Lyrae','Rigel','Sun')  # DS:5BAF.


def available_types(state):
    caps=state['campaign']['capabilities']
    if not caps['transport'] or len(state['fleets']['moving'])>=32:return []
    return [i for i,key in enumerate(('hunter','transfer','pirate','carrier'),1) if caps[key]]


def sprite_source(row):
    icon=(row[0]-1)*160+row[22] if row[22]<=6 else row[22]
    if icon<=0:return None
    at=(icon-1)*32+321
    return at%320,at//320,31,14


def grid_rect(slot,*,lamp=False):
    return (48*(slot//8)+(0 if lamp else 17),60+16*(slot%8),16 if lamp else 32,17)


@dataclass
class FleetView:
    bank:str='moving'
    selected:dict=field(default_factory=lambda:{'moving':None,'local':None})
    pages:dict=field(default_factory=lambda:{'moving':0,'local':0})

    def row(self,state):
        index=self.selected[self.bank]
        rows=state['fleets'][self.bank]
        return rows[index] if index is not None and 0<=index<len(rows) else None

    def select(self,state,index):
        if not 0<=index<len(state['fleets'][self.bank]):raise GameError('This fleet is no longer available.')
        self.selected[self.bank]=index
        self.pages[self.bank]=index//32

    def scroll(self,state,delta):
        self.pages[self.bank]=max(0,min((len(state['fleets'][self.bank])-1)//32,self.pages[self.bank]+delta))

    def buttons(self,state):
        buttons=[24];row=self.row(state)
        if row is not None:
            if self.bank=='moving':buttons.append(16)
            buttons.append(49)
        if self.bank=='moving' and available_types(state):buttons.append(15)
        if row is not None:
            if row[0] in (2,3):buttons.append(3)
            if row[22] in (1,2,7):buttons.append(41)
        return buttons

    def targets(self,state):
        targets=[(CHANGE_RECT,'Change group',('fleet_bank',))]
        start=self.pages[self.bank]*32
        for index in range(start,min(start+32,len(state['fleets'][self.bank]))):
            label=fleet_name(state['fleets'][self.bank][index])
            for lamp in (True,False):targets.append((grid_rect(index-start,lamp=lamp),label,('fleet_select',index)))
        return targets


@dataclass
class NewFleetView:
    kind:int
    name:str

    def cycle(self,state,catalog,delta=1):
        kinds=available_types(state)
        if not kinds:raise GameError('No new fleet type is available.')
        auto=self.name==catalog['fleet_rules'][self.kind-1]['default_name']
        self.kind=kinds[(kinds.index(self.kind)+delta)%len(kinds)] if self.kind in kinds else kinds[0]
        if auto:self.name=catalog['fleet_rules'][self.kind-1]['default_name']

    def targets(self):
        return [(NEW_NAME_RECT,'Change name',('fleet_name',)),(NEW_TYPE_RECT,'Change type',('fleet_type',))]


def composition(row,catalog):
    """Original nonzero hull rows, Carrier payloads and Trade Miner stations."""
    lines=[];y=116
    rule=catalog['fleet_rules'][row[0]-1]
    for cat in rule['categories']:
        for h,hull in enumerate(cat['hulls']):
            count=struct.unpack_from('<h',bytes(row),29+40*(cat['bank']-1)+10*h)[0]
            if count>0:lines.append((204,y,hull['name'],count));y+=9
        y+=3
    if row[0]==4:
        for i,label in enumerate(('Satellite','Spy Sat','Spy Ship','Solar sat')):
            count=struct.unpack_from('<h',bytes(row),31+2*i)[0]
            if count>0:lines.append((208,y,label,count));y+=9
    y+=3
    if row[0]==2:
        count=sum(struct.unpack_from('<h',bytes(row),37+10*h)[0] for h in range(4))
        if count>0:lines.append((208,y,'Miner stat',count))
    return lines


def draw(renderer,state,view,caption):
    catalog=renderer.content.catalog
    target=renderer.frame(state,'SHIP1' if view.bank=='moving' else 'SHIP2',16,0,caption,buttons=view.buttons(state))
    sprites=renderer.asset('SHIP3');start=view.pages[view.bank]*32
    rows=state['fleets'][view.bank]
    for slot,row in enumerate(rows[start:start+32]):
        x,y,_,_=grid_rect(slot)
        source=sprite_source(row)
        if source is not None:target.blit(sprites,x,y+1,source=source,transparent=64)
        target.blit(sprites,x-12,y+5,source=(213 if start+slot==view.selected[view.bank] else 197,22,7,6))
    if len(rows)>32:renderer.text(target,f'{view.pages[view.bank]+1}/{(len(rows)+31)//32}',155,190,columns=7)
    row=view.row(state)
    if row is None:return target
    renderer.text(target,fleet_name(row),202,60,columns=18,color=(198,198,198),shadow=(129,129,129))
    system,planet,moon=row[19:22]
    traveling=row[22] in (4,5,6)
    renderer.text(target,'Destination:' if traveling else 'Base on:' if row[22]==7 else 'Currently on:',202,70,columns=18)
    if 1<=system<=len(SYSTEM_SHORT):
        if row[22]==7:renderer.text(target,catalog['system_names'][system-1],258,70,columns=8)
        else:renderer.text(target,SYSTEM_SHORT[system-1],276 if traveling else 282,70,columns=5)
    primary=next((w['name'] for w in catalog['worlds'] if (w['system'],w['planet'],w['moon'])==(system,planet,0)),None)
    if primary is None:primary=catalog['system_names'][system-1] if 1<=system<=len(catalog['system_names']) else 'Unknown'
    renderer.text(target,primary,211,79,columns=15)
    satellite=next((w['name'] for w in catalog['worlds'] if (w['system'],w['planet'],w['moon'])==(system,planet,moon)),'') if moon else ''
    renderer.text(target,satellite,220,89,columns=14)
    if traveling:renderer.text(target,f'Time left: {remaining_hours(row,state["levels"]["pilot"])}',202,100,columns=18)
    for x,y,label,count in composition(row,catalog):
        renderer.text(target,label,x,y,columns=11)
        renderer.text(target,':',274,y,columns=1)
        renderer.text(target,display_number(count,4).rjust(4),280,y,columns=4,color=(198,198,198),shadow=(129,129,129))
    return target


def draw_new(renderer,state,view,caption):
    target=renderer.frame(state,'BEOSZT',21,0,caption)
    target.fill((132,93,108,10),(0,0,0))
    renderer.text(target,view.name,135,94,columns=17,color=(198,198,198),shadow=(129,129,129))
    renderer.text(target,renderer.content.catalog['fleet_rules'][view.kind-1]['name'],135,118,columns=13)
    return target
