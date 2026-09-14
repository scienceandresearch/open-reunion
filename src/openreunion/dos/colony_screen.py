"""Original colony bundle presentation; drafts do not modify campaign state."""
from dataclasses import dataclass,field

from ..core import GameError
from .settlement import can_settle

# Original DS:6528 six ten-byte records, coordinates in the 320x200 display.
OPTION_RECTS=((2,6,130,64,64),(3,74,130,32,32),(22,110,130,64,64),
              (4,178,130,48,48),(17,230,130,48,48),(7,282,130,32,32))


def settlement_offered(state,catalog,world_id):
    return can_settle(state['worlds'][world_id]['raw'],catalog['surface_rules'],
                      state['products'][6]['research_state']==5,len(state['deployments']))


def option_available(state,catalog,world_id,kind):
    definition=catalog['buildings'][kind-1]
    fields=bytes.fromhex(definition['unclassified_fields_hex'])
    terrain=state['worlds'][world_id]['raw'][21]
    return ((fields[0]==0 and state['levels']['builder']>=fields[1] or
             fields[0]>0 and state['products'][fields[0]-1]['research_state']==5)
            and 1<=terrain<=11 and bool(fields[terrain+4]))


@dataclass
class ColonyView:
    world_id:str
    options:set=field(default_factory=set)

    def cost(self,catalog):
        return 100000+sum(catalog['buildings'][kind-1]['price'] for kind in self.options)

    def toggle(self,state,catalog,kind):
        if kind not in catalog['settlement_options']:raise GameError('Unknown colony option.')
        if kind in self.options:self.options.remove(kind);return
        if not option_available(state,catalog,self.world_id,kind):
            raise GameError('This building needs different terrain, builder skill or research.')
        if self.cost(catalog)+catalog['buildings'][kind-1]['price']>state['resources']['credits']:
            raise GameError('Not enough credits for this colony bundle.')
        self.options.add(kind)

    def targets(self,catalog):
        return [((x,y,w,h),catalog['buildings'][kind-1]['name'],('colony_option',kind))
                for kind,x,y,w,h in OPTION_RECTS]
