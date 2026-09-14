"""Recovered MUSZI cockpit controls, window composition and instruments."""
from dataclasses import dataclass, field
import random

from ..core import GameError, integer
from .planet_actions import deployment_buttons, action_signature

RECTS=((0,49,320,87),(0,149,71,51),(77,141,42,40),
       (131,137,59,63),(202,145,41,39),(255,153,65,47))
LIGHTS=tuple(zip((0,6,13,20,28,37),(0,1,2,4,5,7),(6,6,6,7,7,8),(3,3,3,3,3,3)))


@dataclass
class CockpitView:
    index:int
    ticks:int=0
    monitor:int=0
    lights:list=field(default_factory=lambda:[False]*6)
    rng:random.Random=field(default_factory=lambda:random.Random(1994),repr=False)
    stars:list=field(default_factory=list,repr=False)
    trails:dict=field(default_factory=dict,repr=False)

    def row(self,state):
        integer(self.index,'Fleet index',maximum=len(state['fleets']['moving'])-1)
        row=state['fleets']['moving'][self.index]
        if row[0] not in (1,2,3,4):raise GameError('Select a moving fleet.')
        return row

    def world_id(self,state):return ':'.join(map(str,self.row(state)[19:22]))

    def buttons(self,state,catalog):
        row=self.row(state);buttons=[24,13,49]
        if row[0] in (2,3):buttons.append(3)
        if row[22] in (1,2):
            buttons.extend((46,41))
            if self.world_id(state) in state['worlds']:buttons.extend(deployment_buttons(state,catalog,self.world_id(state)))
        return buttons

    def targets(self,state):
        row=self.row(state);status=row[22]
        labels=('Planet main','Launching' if status==1 else 'Docking' if status==2 else 'No effect',
                'Transfer','Move' if status==2 else 'Change destination' if status in (4,5,6) else 'No effect',
                'Ships','Group')
        actions=('surface','orbit','cargo','move','fleets','equipment')
        return [(rect,label,('cockpit_'+action,)) for i,(rect,label,action) in enumerate(zip(RECTS,labels,actions))
                if not(i==0 and status>2 or i==2 and row[0] not in (2,3))]

    def signature(self,state,catalog):
        row=self.row(state);wid=self.world_id(state)
        return (tuple(row),tuple(self.buttons(state,catalog)),state['levels']['pilot'],
                action_signature(state,wid) if wid in state['worlds'] else None)

    def advance(self,state):
        """Cosmetic randomness is deliberately separate from campaign RNG."""
        self.ticks+=1
        selected=self.rng.randrange(6)
        if self.rng.randrange(2)==0:self.lights[selected]=not self.lights[selected]
        if self.ticks%6==0:self.monitor=self.rng.randrange(6)
        status=self.row(state)[22]
        if status not in (4,5,6):self.trails.clear();return
        if not self.stars:
            for _ in range(1101):
                x,y,z,speed=self.rng.randrange(654)-327,self.rng.randrange(210)-105,self.rng.randrange(900)+115,self.rng.randrange(10)+5
                if abs(x)<50 and abs(y)<50:x*=2;y*=2
                if abs(x)<30 and abs(y)<30:x=abs(x)+30;y=abs(y)+30
                self.stars.append([x,y,z,speed])
        if status!=5:self.trails.clear()
        for star in self.stars:
            x,y,z,speed=star
            # C/Pascal division truncates negative projections toward zero.
            px,py=int(x*100/(z+100)),int(y*100/(z+100))
            if 0<=160+px<320 and 0<=49+py<151:
                self.trails[(160+px,49+py)]=max(90,min(255,255-z//5))
            star[2]-=speed
            if abs(px)>140 or abs(py)>45 or star[2]<=-90:star[2]=self.rng.randrange(500)+500


def instrument_copies(view):
    """Original MUSZIANM source/destination rectangles (194F8..19735)."""
    copies=[((201,183),(135+26*view.monitor,46,24,18)),
            ((193,151),(89+11*((view.ticks%32)//8),54,10,16))]
    for enabled,(x,y,w,h) in zip(view.lights,LIGHTS):
        copies.append(((201+x,127+y),(89+x,(32 if enabled else 43)+y,w,h)))
    return copies


def draw(renderer,state,view,caption,page=0):
    row=view.row(state);wid=view.world_id(state);raw=state['worlds'].get(wid,{}).get('raw')
    target=renderer.frame(state,'PLANETS/MUSZI.PIC',17,page,caption,buttons=view.buttons(state,renderer.content.catalog))
    cockpit=renderer.path_asset('PLANETS/MUSZI.PIC')
    terrain=raw[21] if raw and 1<=raw[21]<=12 else 0
    if wid=='1:7:0' and raw and raw[0] not in (1,2):terrain=12
    background=renderer.path_asset(f"PLANETS/NAGY{terrain if row[22]==1 else 0}.PIC")
    if row[22]==1:target.blit(background,0,49,source=(0,43,320,108))
    else:target.blit(background,0,49)
    if row[22] in (4,5,6):
        target.fill((0,49,320,151),(0,0,0))
        for (x,y),brightness in view.trails.items():
            at=((49+y)*320+x)*3;target.rgb[at:at+3]=bytes((brightness,brightness,min(255,brightness+25)))
    target.blit(cockpit,0,49,transparent=64)
    instruments=renderer.path_asset('PLANETS/MUSZIANM.PIC')
    for (x,y),(sx,sy,w,h) in instrument_copies(view):
        # The original bottom monitor writes one scanline below visible VRAM.
        target.blit(instruments,x,y,source=(sx,sy,w,min(h,200-y)))
    return target
