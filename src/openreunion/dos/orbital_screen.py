"""Orbital fleet records and visibility recovered from 2C232..2C59B.

The native panel paginates instead of dropping records after original slot 18.
Padding preserves the original rule that each alien civilization starts a row.
"""
from .world_lists import world_visible
from ..core import GameError
from .battle_dispatch import player_attack_request


def map_buttons(state, planet, entries, selected=None, *, routing=False, shortcuts=True):
    """DC26..DD8F contextual offers; commander checks occur on activation.

    Keep the preview's Ship Info/Cargo shortcuts after the original actions.
    All pages participate in offers instead of DOS's truncated 18-slot roster.
    """
    if routing:return [57,33] if planet else [57]
    buttons = [24,33] if planet else [24]
    entry = next((e for e in entries if e and e['key'] == selected), None) if planet else None
    if entry is None:return buttons
    civilizations = state['campaign']['civilizations']
    def hostile(race):
        relation = civilizations[race-2][27]
        return (relation if relation < 128 else relation-256) < 6
    if selected[0] == 'alien':
        if hostile(selected[1]) and any(e and e['icon'] == 1 for e in entries):
            buttons.append(55)
    else:
        row = state['fleets']['moving'][selected[1]]
        buttons.append(56)
        world = state['worlds'].get(':'.join(map(str,row[19:22])))
        if world:
            raw = world['raw']
            if row[0] == 1 and 2 <= raw[0] <= 12 and 40 <= raw[12] < 128 and hostile(raw[0]):
                buttons.append(71)
        if shortcuts:
            buttons.append(13)
            if row[0] in (2,3):buttons.append(7)
    return buttons


def map_attack(state, planet, entries, selected, action):
    """Resolve current map selection to the shared transactional attack command."""
    if action not in (55,71) or action not in map_buttons(state,planet,entries,selected):
        raise GameError('This attack is no longer available. Select the target again.')
    if action == 71:
        arguments = {'fleet_index':selected[1]}
    else:
        # The combat builder gathers every eligible Army at the primary. The
        # command's Army index supplies location, not a restriction on forces.
        index = next((e['key'][1] for e in entries if e and e['key'][0] == 'player'
                      and e['icon'] == 1 and state['fleets']['moving'][e['key'][1]][22] in (1,2)), None)
        if index is None:raise GameError('An Army must arrive before attacking.')
        arguments = {'fleet_index':index,'target_race':selected[1],'target_slot':selected[2]+1}
    player_attack_request(state,**arguments)
    return arguments


def attack_signature(state, entries, selected, buttons):
    """Cancel a held gesture when offers, forces, target slots or skills change."""
    world = None
    if selected and selected[0] == 'player' and any(e and e['key'] == selected for e in entries):
        row = state['fleets']['moving'][selected[1]]
        world = state['worlds'].get(':'.join(map(str,row[19:22])))
    return (selected,tuple(buttons),tuple(tuple(r) for r in state['fleets']['moving']),
            tuple(tuple(r) for r in state['campaign']['civilizations']),
            tuple(world['raw']) if world else None,state['levels']['fighter'],state['ranks']['fighter'])


def orbital_entries(state, catalog, system, planet):
    primary = next((w for w in catalog['worlds'] if
                    (w['system'], w['planet'], w['moon']) == (system, planet, 0)), None)
    if primary is None or not world_visible(state, primary):
        return []
    if system == 4 and state['campaign']['flags']['5d90']:
        return []
    raw = state['worlds'][primary['id']]['raw']
    civilizations = state['campaign']['civilizations']
    owner = raw[0]
    monitored = bool(raw[9] or owner == 1 and (raw[6] or raw[10]) or
                     2 <= owner <= 12 and raw[6] and civilizations[owner-2][27] == 6)
    entries = []
    for index, row in enumerate(state['fleets']['moving']):
        if row[19:21] == [system, planet] and row[22] in (1, 2, 3):
            entries.append({'key':('player', index), 'icon':row[0], 'moon':row[21],
                            'label':bytes(row[2:2+min(17,row[1])]).decode('cp437'), 'status':row[22]})
    monitored = monitored or bool(entries)
    for civilization in civilizations:
        if civilization[27] == 6:
            for index in range(civilization[38]):
                row = civilization[39+27*index:66+27*index]
                if row[8:10] == [system, planet] and row[2] == 1:
                    monitored = True
    if monitored:
        for race, civilization in enumerate(civilizations, 2):
            if len(entries)%2:
                entries.append(None)
            for index in range(civilization[38]):
                row = civilization[39+27*index:66+27*index]
                if row[8:10] == [system, planet] and row[2] == 1 and row[0] > 1:
                    entries.append({'key':('alien', race, index), 'icon':race+3, 'moon':row[10],
                                    'label':catalog['alien_names'][race-2]+' '+str(index+1), 'status':row[2]})
    while entries and entries[-1] is None:
        entries.pop()
    return entries


def fleet_rect(slot):
    return (257+32*(slot%2), 50+16*(slot//2), 31, 15)


def fleet_sprite(icon):
    return (1+32*((icon-1)%10), 1+16*((icon-1)//10), 31, 15)


def orbital_targets(entries, page):
    return [(fleet_rect(slot), entry['label'], ('orbital_select', entry['key']))
            for slot, entry in enumerate(entries[page*18:page*18+18]) if entry is not None]
