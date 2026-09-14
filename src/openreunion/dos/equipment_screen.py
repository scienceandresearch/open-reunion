"""Original BEOSZTAS presentation over the shared fleet transfer commands."""
from dataclasses import dataclass
import struct

from ..core import GameError
from .fleets import local_record

# Original descriptor fields: stock label x/y, quantity x/y and label width.
HULL_STOCK = {
    1: ((16,176,62,176,7),(16,186,62,186,7),(88,176,146,176,9),(88,186,146,186,9)),
    2: ((16,176,62,176,7),(88,176,158,176,11),(88,186,158,186,11),(16,186,62,186,7)),
    3: ((16,176,62,176,7),(16,186,62,186,7),(88,176,146,176,9),(88,186,146,186,9)),
    4: ((16,176,67,176,8),),
}
COMPONENT_STOCK = ((188,176,222,176),(188,186,222,186),(248,176,282,176),(248,186,282,186))
CARRIER_STOCK = ((99,176,132,176),(99,186,132,186),(161,176,194,176),(161,186,194,186))
RENAME_RECT = (21,53,108,12)
PREVIOUS_RECT, NEXT_RECT = (7,53,14,12), (129,53,13,12)
CATEGORY_UP, CATEGORY_DOWN = (291,84,28,35), (291,121,28,35)


def fleet_name(row):
    return bytes(row[2:2+min(17,row[1])]).decode('cp437')


def count_rect(hull,component):
    return ((106 if not component else 143+38*(component-1)),108+10*(hull-1),26 if not component else 33,9)


@dataclass
class EquipmentView:
    bank:str
    index:int
    category:int=0
    world_id:str|None=None
    notice:str=''

    def choices(self,state):
        return [(bank,i) for bank in ('moving','local') for i,row in enumerate(state['fleets'][bank])
                if self.world_id is None or bank=='local' and ':'.join(map(str,row[19:22]))==self.world_id]

    def row(self,state):
        if (self.bank,self.index) not in self.choices(state):
            raise GameError('The fleet selection changed. Reopen its equipment screen.')
        return state['fleets'][self.bank][self.index]

    def rule(self,state,catalog):
        row=self.row(state)
        return next(rule for rule in catalog['fleet_rules'] if rule['id']==row[0])

    def category_rule(self,state,catalog):
        cat=self.rule(state,catalog)['categories'][self.category]
        # DS:BCD gives Pirate transport three columns even though its shared
        # Trade descriptor contains a fourth (Miner station) component.
        if self.row(state)[0]==3 and cat['id']==2:
            return {**cat,'components':cat['components'][:3]}
        return cat

    def step(self,state,delta):
        choices=self.choices(state)
        position=choices.index((self.bank,self.index))
        self.bank,self.index=choices[max(0,min(len(choices)-1,position+delta))]
        self.category=0

    def report(self,state,catalog):
        row=self.row(state)
        identity=tuple(row[19:22]);wid=':'.join(map(str,identity))
        raw=state['worlds'].get(wid,{}).get('raw')
        local=local_record(state['fleets'],identity)
        home=identity==(1,5,0)
        editable=bool(raw and raw[0]==1 and raw[6] and row[22] in (1,7) and (home or local is not None))
        cat=self.category_rule(state,catalog)
        def item(entry):
            product=state['products'][entry['product']-1]
            return {'visible':product['research_state']>0,
                    'enabled':editable and (home or entry['local_slot']>0),
                    'stock':product['stock'] if home else struct.unpack_from('<h',bytes(local),131+2*entry['local_slot'])[0]
                            if local is not None and entry['local_slot'] else None}
        return {'row':tuple(row),'world':wid,'editable':editable,
                'hulls':[item(entry) for entry in cat['hulls']],
                'components':[item(entry) for entry in cat['components']],
                'counts':[struct.unpack_from('<5h',bytes(row),29+40*(cat['bank']-1)+10*h)
                          for h in range(len(cat['hulls']))],
                # Cancel held clicks on any inventory/research/location change,
                # including aliased remote slots and another equipment category.
                'signature':(tuple(raw) if raw else None,tuple(local) if local is not None else None,
                             tuple((p['stock'],p['research_state']) for p in state['products']))}

    def targets(self,state,catalog):
        report=self.report(state,catalog);cat=self.category_rule(state,catalog)
        choices=self.choices(state);position=choices.index((self.bank,self.index))
        targets=[(RENAME_RECT,'Change name',('equipment_rename',))]
        if position:targets.append((PREVIOUS_RECT,'Previous group',('equipment_step',-1)))
        if position+1<len(choices):targets.append((NEXT_RECT,'Next group',('equipment_step',1)))
        if self.category:targets.append((CATEGORY_UP,'Previous category',('equipment_category',-1)))
        if self.category+1<len(self.rule(state,catalog)['categories']):
            targets.append((CATEGORY_DOWN,'Next category',('equipment_category',1)))
        for h,hull in enumerate(cat['hulls'],1):
            # Original targets allow discovered components on an undiscovered
            # hull row; the shared command still enforces its actual capacity.
            for component,entry in enumerate([hull,*cat['components']]):
                info=report['hulls'][h-1] if component==0 else report['components'][component-1]
                if info['visible'] and info['enabled']:
                    targets.append((count_rect(h,component),catalog['products'][entry['product']-1]['name'],
                                    ('equipment_transfer',h,component)))
        return targets

    def buttons(self,state):
        from .disband import disband_available
        row=self.row(state);buttons=[24,13]
        if self.bank=='moving':buttons.append(16)
        if row[0] in (2,3):buttons.append(3)
        if row[22] in (1,2,7):buttons.extend((46,41))
        if disband_available(state,self.index,self.bank):buttons.append(37)
        return buttons


def draw(renderer,state,view,caption,page=0):
    from .production_screen import display_number
    catalog=renderer.content.catalog
    report=view.report(state,catalog);cat=view.category_rule(state,catalog)
    target=renderer.frame(state,'BEOSZTAS',22,page,view.notice or caption,buttons=view.buttons(state))
    art=renderer.asset('BEOSZTAS');black=tuple(art.palette[192:195])  # DOS clear color 64.
    def text(value,x,y,columns,enabled=False):
        renderer.text(target,value,x,y,columns=columns,
                      **({'color':(198,198,198),'shadow':(129,129,129)} if enabled else {}))
    text(fleet_name(report['row']),24,56,17,True)
    text(view.rule(state,catalog)['name'],223,56,13)
    world=next((w['name'] for w in catalog['worlds'] if w['id']==report['world']),None)
    if world is None:
        system=report['row'][19]
        world=catalog['system_names'][system-1] if 1<=system<=len(catalog['system_names']) else 'Unknown location'
    prefix={1:'In the dock ',2:'In orbit ',4:'Fly to ',5:'Fly to ',6:'Fly to '}.get(report['row'][22],'')
    text(prefix+world,12,67,49)
    choices=view.choices(state);position=choices.index((view.bank,view.index))
    if position==0:target.fill((9,53,10,12),black)
    if position==len(choices)-1:target.fill((131,53,10,12),black)
    if view.category==0:target.fill((294,87,17,28),black)
    if view.category+1==len(view.rule(state,catalog)['categories']):target.fill((294,124,17,28),black)
    for c,entry in enumerate(cat['components']):
        if report['components'][c]['visible']:text(entry['name'],144+38*c,99,5)
    for h,hull in enumerate(cat['hulls']):
        info=report['hulls'][h]
        if not info['visible']:continue
        text(hull['name'],21,109+10*h,11)
        text(display_number(report['counts'][h][0],3).rjust(3),109,109+10*h,3,info['enabled'])
        for c,entry in enumerate(cat['components']):
            info=report['components'][c]
            if info['visible']:
                value='-' if hull['limits'][c]==0 else display_number(report['counts'][h][c+1],4)
                text(value.rjust(4),146+38*c,109+10*h,4,info['enabled'])
    if report['editable']:
        for entry,info,coords in zip(cat['hulls'],report['hulls'],HULL_STOCK[cat['id']]):
            x,y,nx,ny,columns=coords
            if info['visible']:
                text(entry['name'],x,y,columns)
                if info['enabled']:text(display_number(info['stock'],4),nx,ny,4)
        coords=CARRIER_STOCK if cat['id']==4 else COMPONENT_STOCK
        for entry,info,(x,y,nx,ny) in zip(cat['components'],report['components'],coords):
            if info['visible']:
                text(entry['name'],x,y,5)
                if info['enabled']:text(display_number(info['stock'],4),nx,ny,4)
    return target
