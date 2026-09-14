"""Dated mission snapshots shared by the message archive and incoming notices."""
import json
from ..core import GameError
from .worlds import world_message_label

REPORT_BUDGET = 500_000


def validate_report(record):
    if 'report' not in record:
        if record['kind']=='report':raise GameError('A mission report has no text.')
        return
    rows=record['report']
    if record['kind'] not in ('message','report') or not isinstance(rows,list) or not 1<=len(rows)<=512:
        raise GameError('Invalid mission report.')
    if any(not isinstance(row,str) or not row or len(row)>500 or any(ord(c)<32 for c in row) for row in rows):
        raise GameError('Invalid mission report text.')


def report_size(records):
    return sum(len(json.dumps(record['report'],ensure_ascii=True,separators=(',',':')))
               for record in records if 'report' in record)


def append_report_text(text,record):
    return '\n'.join(([text] if text else [])+record.get('report',[]))


def mission_text(catalog,kind,detail):
    if kind=='ore_reward':return [f"You got {detail['quantity']:,} t of {catalog['ore_names'][detail['ore']]}."]
    if kind=='product_reward':
        return [f"You got {detail['quantity']:,} pieces of {catalog['products'][detail['product']-1]['name']}."]
    if kind=='pirate_announcement':
        lines=catalog.get('pirate_messages')
        return [line for line in lines[detail-1].split('|') if line] if lines else [f'Pirate contract {detail} announced.']
    if kind!='intelligence':raise GameError('Unknown mission report kind.')
    name=catalog.get('alien_names',['Civilization']*11)[detail['race']-2]
    result=[f'Information on {name}:']
    for report in detail['reports']:
        if 'world' in report:
            definition=next(w for w in catalog['worlds'] if w['id']==report['world'])
            text=world_message_label(catalog,definition)
            if report.get('garrison'):text='Garrison: '+text
            if detail['kind']==1:text=('Main planet: ' if report['base'] else 'Colony: ')+text
        elif 'slot' in report:text=f"Army {report['slot']}"
        else:
            names=('Hunter','Fighter','Destroyer','Cruiser','Trooper','Tank','Aircraft','Missile')
            text='Weapons available: '+(', '.join(names[n-1] for n in report['weapons']) or 'None')
        if 'forces' in report:
            labels=('hunters','fighters','destroyers','cruisers','troopers','tanks','aircraft','missiles')
            text+='; '+', '.join(f'{n:,} {label}' for n,label in zip(report['forces'],labels))
        result.append(text)
    if not detail['reports']:result.append('No matching colonies or forces reported.')
    return result
