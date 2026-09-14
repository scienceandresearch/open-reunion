"""Original TRANSFER screen over the transactional cargo commands."""
from dataclasses import dataclass
import struct

from ..core import GameError, integer
from .cargo import cargo_capacity, cargo_used, ore_transfer_limit, item_transfer_limit
from .catalog import ORE_KEYS
from .fleets import local_record, storage_limit
from .industry import world_stocks

BUTTONS = [24, 13, 16, 49]


def visible_items(state, catalog):
    return [item for item in catalog['cargo_rules']['items']
            if item['product'] is not None and state['products'][item['product']-1]['research_state']==5]


def arrow_rect(position, loading):
    """1AAB6..1ABA3: one-based displayed row, unload left / load right."""
    return (235 if loading else 68, 53+8*position, 16, 7)


@dataclass
class CargoView:
    index: int

    def row(self, state):
        integer(self.index, 'Fleet index', maximum=len(state['fleets']['moving'])-1)
        row=state['fleets']['moving'][self.index]
        if row[0] not in (2,3):raise GameError('Select a Trade or Pirate fleet.')
        return row

    def report(self, state, catalog):
        row=self.row(state);identity=tuple(row[19:22]);wid=':'.join(map(str,identity))
        raw=state['worlds'].get(wid,{}).get('raw');home=identity==(1,5,0)
        local=local_record(state['fleets'],identity)
        editable=bool(raw and row[22]==1 and raw[0]==1 and (raw[6] or raw[10]))
        port=any(b[0]==12 and b[1:4]==list(identity) and b[6]==0 for b in state['buildings'])
        depot=[state['resources'][key] for key in ORE_KEYS] if home else world_stocks(raw) if raw else [0]*6
        lines=[{'kind':'ore','key':key,'name':key.capitalize(),'aboard':struct.unpack_from('<I',bytes(row),109+4*i)[0],
                'depot':depot[i],'weight':1,'queued':0} for i,key in enumerate(ORE_KEYS)]
        for item in visible_items(state,catalog):
            slot=item['slot'];product=state['products'][item['product']-1]
            stock=product['stock'] if home else struct.unpack_from('<h',bytes(local),131+2*slot)[0] if local else 0
            lines.append({'kind':'slot','key':slot,'name':catalog['products'][item['product']-1]['name'],
                'aboard':struct.unpack_from('<h',bytes(row),131+2*slot)[0],'depot':stock,'weight':item['weight'],
                'queued':product['queued'] if home else 0})
        return {'row':tuple(row),'world':wid,'editable':editable,'port':port,'item_depot':home or local is not None,
                'lines':lines,'used':cargo_used(row,catalog['cargo_rules']),'capacity':cargo_capacity(row,catalog),
                'storage':storage_limit(state['fleets'],identity,state['buildings']),
                'signature':(tuple(raw) if raw else None,tuple(local) if local else None,
                    tuple((p['stock'],p['research_state'],p['queued']) for p in state['products']),
                    tuple(tuple(b) for b in state['buildings'] if b[1:4]==list(identity)))}

    def targets(self, state, catalog):
        report=self.report(state,catalog)
        if not report['editable']:return []
        targets=[(arrow_rect(i,loading),('Load ' if loading else 'Unload ')+line['name'],
                 ('cargo_transfer',line['kind'],line['key'],loading))
                for loading in (False,True) for i,line in enumerate(report['lines'],1)]
        return targets+[((8 if loading else 260,53+8*i,52 if loading else 60,7),
                         ('Load ' if loading else 'Unload ')+line['name'],
                         ('cargo_transfer',line['kind'],line['key'],loading))
                        for loading in (False,True) for i,line in enumerate(report['lines'],1)]

    def transfer(self, state, catalog, kind, key, loading, mouse, *, maximum=False, steps=1):
        """Return a current, bounded public command; empty/full clicks do nothing."""
        integer(steps,"Cargo adjustment",minimum=1,maximum=1000)
        if type(maximum) is not bool:raise GameError("Invalid maximum transfer flag.")
        report=self.report(state,catalog)
        if not report['editable']:raise GameError('Land at an owned colony or mining outpost to transfer cargo.')
        line=next((line for line in report['lines'] if (line['kind'],line['key'])==(kind,key)),None)
        if line is None:raise GameError('The available cargo changed. Select it again.')
        if kind=='ore':
            amount=ore_transfer_limit(line['aboard'],line['depot'],report['capacity'],report['used'],report['storage'],loading)
            if not maximum and mouse!=3:amount=min(100*steps,amount)
        else:
            if not report['port']:raise GameError('Stored items require a completed Space Port at this world.')
            if not report['item_depot']:raise GameError('No local item depot is available.')
            amount=item_transfer_limit(line['aboard'],line['depot'],line['weight'],report['capacity'],
                                           report['used'],loading,line['queued'])
            if not maximum:amount=min(steps,amount)
        if not amount:return None
        return {'fleet_index':self.index,kind:key,'quantity':amount if loading else -amount}


def draw(renderer, state, view, caption):
    from .production_screen import display_number
    report=view.report(state,renderer.content.catalog)
    target=renderer.frame(state,'TRANSFER',13,0,caption)
    for i,line in enumerate(report['lines'],1):
        y=53+8*i
        renderer.text(target,line['name'],112,y,columns=16)
        renderer.text(target,display_number(line['aboard'],6).rjust(6),270,y,columns=6)
        if report['editable'] and (line['kind']=='ore' or report['port'] and report['item_depot']):
            renderer.text(target,display_number(line['depot'],6).rjust(6),12,y,columns=6)
    # The native font is eight pixels high; shift DOS y=193 up one pixel.
    renderer.text(target,f"Space: {display_number(report['used'],6)}/{display_number(report['capacity'],6)}",5,192,columns=20)
    renderer.text(target,f"Storage on planet: {display_number(report['storage'],8)}",128,192,columns=31)
    return target
