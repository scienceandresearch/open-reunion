"""Original empty-group disbanding with inventory and overflow guards."""
import struct

from ..core import GameError,integer
from .fleets import local_record


def hulls_empty(row):
    """21F5D..2204C for the four moving types; local forces cannot disband."""
    if row[0] not in (1,2,3,4):return False
    banks=(0,1) if row[0] in (1,3) else (0,)
    count=1 if row[0]==4 else 4
    return all(struct.unpack_from('<h',bytes(row),29+40*bank+10*h)[0]==0
               for bank in banks for h in range(count))


def disband_plan(state,fleet_index,bank='moving'):
    if bank!='moving':raise GameError('Planetary defense groups cannot be disbanded.')
    integer(fleet_index,'Fleet index',maximum=len(state['fleets']['moving'])-1)
    row=state['fleets']['moving'][fleet_index]
    raw=state['worlds'].get(':'.join(map(str,row[19:22])),{}).get('raw')
    if row[22]!=1 or not raw or raw[0]!=1 or not raw[6]:
        raise GameError('Disbanding requires a landed group at an owned colony.')
    if not hulls_empty(row):raise GameError('Unload all ships and ground units before disbanding the group.')
    # DOS merges Army's two equipment banks, or Pirate's first bank, into
    # the last local defense at this exact world. Other contents are discarded
    # by DOS; reject those cases instead of silently losing cargo/equipment.
    stop=109 if row[0]==1 else 69 if row[0]==3 else 29
    if any(row[stop:159]):raise GameError('Unload cargo and remaining equipment before disbanding the group.')
    incoming=list(struct.unpack_from('<'+'h'*((stop-29)//2),bytes(row),29))
    for value in incoming:integer(value,'Disbanded equipment',maximum=32767)
    local=local_record(state['fleets'],tuple(row[19:22]))
    if any(incoming) and local is None:
        raise GameError('This colony has no local defense group to receive the remaining equipment.')
    merged=[]
    if local is not None:
        for i,value in enumerate(incoming):
            old=struct.unpack_from('<h',bytes(local),29+2*i)[0]
            integer(old,'Local defense equipment',maximum=32767)
            integer(old+value,'Combined defense equipment',maximum=32767)
            merged.append(old+value)
    return local,merged


def disband_available(state,fleet_index,bank='moving'):
    try:disband_plan(state,fleet_index,bank)
    except GameError:return False
    return True


def disband_fleet(state,fleet_index,bank='moving'):
    local,merged=disband_plan(state,fleet_index,bank)
    if local is not None and merged:
        local[29:29+2*len(merged)]=struct.pack('<'+'h'*len(merged),*merged)
    # Use the selected bank's actual list length. The original compaction loop
    # used the currently displayed bank count, which may refer to another bank.
    return state['fleets']['moving'].pop(fleet_index)
