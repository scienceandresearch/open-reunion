"""Original colony surface tile identities and native view state."""
from dataclasses import dataclass, field
from .surface_animation import SurfaceAnimation

from .surface import surface_map, building_available, footprint, surface_editable, surface_revealed, occupancy, automatic_position

VIEWPORT = (93,53,224,144)


def local_group(state,world_id):
    """203DD..2045F selects the last matching local row, not a stale index."""
    identity=list(map(int,world_id.split(':')))
    return next((i for i in range(len(state['fleets']['local'])-1,-1,-1)
                 if state['fleets']['local'][i][19:22]==identity),None)


def surface_buttons(state,world_id,*,return_cockpit=False):
    raw=state['worlds'][world_id]['raw']
    buttons=[24,46,9,43]
    # Original 5FDD..5FEF offers 66 on owned colonies. Do not reproduce its
    # stale local selection when malformed/imported state has no matching row.
    if raw[0]==1 and raw[6] and local_group(state,world_id) is not None:buttons.append(66)
    if return_cockpit:buttons.append(16)
    return buttons


def building_tiles(state,catalog,world_id):
    identity = list(map(int,world_id.split(':')))
    definitions = {d['id']:d for d in catalog['buildings']}
    result = {}
    for index,row in enumerate(state['buildings']):
        if row[1:4] != identity or 255 in row[4:6]:
            continue
        definition = definitions[row[0]]
        stage = min(3,(row[6]+39)//40)
        for x,y in footprint(definition,row[4],row[5]):
            tile = 219+stage if stage else definition['tile_ids'][(y-row[5])*4+x-row[4]]
            result[(x,y)] = (tile,index)
    return result


@dataclass
class SurfaceView:
    world_id: str = '1:5:0'
    x: int = 0
    y: int = 0
    selected: int = 1
    mode: str = 'inspect'
    tile: tuple | None = None
    inspected: int | None = None
    inspected_identity: tuple | None = None
    editable: bool = True
    revealed: bool = True
    inspectable: bool = True
    animation: SurfaceAnimation = field(default_factory=SurfaceAnimation)

    def overlays(self,state,catalog):
        result=building_tiles(state,catalog,self.world_id)
        raw=state['worlds'][self.world_id]['raw']
        if raw[0]>1 and surface_revealed(raw):
            # 240F0..24125 adds a graphical type-25 alien base after ordinary
            # records. It is not a mine in the player's saved building bank.
            definition=catalog['buildings'][24]
            width,height,blocked=occupancy(catalog,raw,state['buildings'],
                list(map(int,self.world_id.split(':'))),allow_unplaced=True)
            position=automatic_position(definition,width,height,blocked)
            if position is not None:
                x,y=position
                for xx,yy in footprint(definition,x,y):
                    result[(xx,yy)]=(definition['tile_ids'][(yy-y)*4+xx-x],None)
        return result

    def choices(self,state,catalog):
        raw = state['worlds'][self.world_id]['raw']
        if not surface_editable(catalog,raw):return []
        return [d for d in catalog['buildings'] if building_available(d,raw,state['products'],state['levels']['builder'])]

    def sync(self,state,catalog):
        raw=state['worlds'][self.world_id]['raw']
        terrain = surface_map(catalog,raw)
        self.editable=surface_editable(catalog,raw)
        self.revealed=surface_revealed(raw)
        self.inspectable=self.revealed and raw[0]==1
        if self.inspected is not None:
            rows=state['buildings']
            row=rows[self.inspected] if 0<=self.inspected<len(rows) else None
            if (row is None or row[1:4]!=list(map(int,self.world_id.split(':')))
                    or self.inspected_identity is not None and tuple(row[:6])!=self.inspected_identity):
                self.mode,self.inspected='inspect',None
            else:self.inspected_identity=tuple(row[:6])
        if self.inspected is None:self.inspected_identity=None
        if (not self.revealed or not self.editable and self.mode in ('build','demolish')
                or not self.inspectable and self.mode=='info'):
            self.mode,self.inspected='inspect',None
        self.x = max(0,min(self.x,max(0,terrain['width']-14)))
        self.y = max(0,min(self.y,max(0,terrain['height']-9)))
        choices = self.choices(state,catalog)
        if self.selected not in [d['id'] for d in choices] and not (self.mode == 'info' and self.inspected is not None):
            self.selected = choices[0]['id'] if choices else 1
            self.mode = 'inspect'
        return terrain

    def step(self,state,catalog,amount):
        choices = [d['id'] for d in self.choices(state,catalog)]
        if choices:
            at = choices.index(self.selected) if self.selected in choices else 0
            self.selected = choices[max(0,min(len(choices)-1,at+amount))]
        self.mode,self.inspected = 'inspect',None

    def radar(self,terrain):
        scale = 2 if terrain['width'] <= 45 and terrain['height'] <= 30 else 1
        return ((90-terrain['width']*scale)//2+1,
                139+(60-terrain['height']*scale)//2,scale)

    def targets(self):
        if not self.revealed:return []
        if self.mode=='info':
            return [(rect,'Back to surface',('surface_close_info',))
                    for rect in ((90,49,230,151),(12,66,77,59))]
        controls = [((0,64,11,32),'Previous building',('surface_step',-1)),
                    ((0,97,11,32),'Next building',('surface_step',1)),
                    ((0,50,44,13),'Build',('surface_mode','build')),
                    ((45,50,44,13),'Demolish (2000 credits)',('surface_mode','demolish')),
                    ((12,66,77,59),'Building information',('surface_info',)),
                    ((0,138,89,62),'Radar',('surface_radar',)),
                    ((89,53,4,144),'Scroll left',('surface_pan',-1,0)),
                    ((317,53,3,144),'Scroll right',('surface_pan',1,0)),
                    ((93,49,224,4),'Scroll up',('surface_pan',0,-1)),
                    ((93,197,224,3),'Scroll down',('surface_pan',0,1))]
        if not self.editable:controls=controls[5:]
        return controls + ([((93+16*x,53+16*y,16,16),'Surface',('surface_tile',self.x+x+1,self.y+y+1))
                            for y in range(9) for x in range(14)] if self.inspectable else [])
