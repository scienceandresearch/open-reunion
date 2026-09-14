"""Original mining display values (19F35..1A2B7), without simulation writes."""
import struct

from .catalog import ORE_KEYS
from .fleets import local_record
from .industry import world_stocks


def mining_available(state,world_id):
    raw=state['worlds'][world_id]['raw']
    return raw[0]==1 and bool(raw[6] or raw[10])


def mining_report(state,world_id):
    raw=state['worlds'][world_id]['raw']
    identity=tuple(map(int,world_id.split(':')))
    home=identity==(1,5,0)
    local=local_record(state['fleets'],identity)
    stored=(state['products'][1]['stock'] if home else
            struct.unpack_from('<h',bytes(local),157)[0] if raw[6] and local else 0)
    mines=sum(r[1:4]==list(identity) and r[0] in (4,25) and not r[6] for r in state['buildings'])
    active=raw[10]
    rates=[]
    for i,abundance in enumerate(raw[59:65]):
        rates.append('-' if abundance<10 else '--' if i==0 else str(abundance*active//10))
    return {'stocks':[state['resources'][k] for k in ORE_KEYS] if home else world_stocks(raw),
            'rates':rates,'active':active,'stored':stored,'mines':mines,
            'can_assign':raw[0]==1 and bool(raw[6]) and stored>0 and active<min(9,mines)}
