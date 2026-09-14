"""Player-facing battle identity derived from saved encounter provenance."""


def world_name(catalog,destination):
    identity=':'.join(map(str,destination))
    return next((w['name'] for w in catalog['worlds'] if w['id']==identity),identity)


def civilization_name(catalog,race):
    names=catalog.get('alien_names',[])
    return names[race-2].strip() if 2<=race<=len(names)+1 else f'Civilization {race}'


def space_opponents(state,catalog,encounter):
    """Keep the initiating attacker first, even with zero ships or after losses.

    Hostile roster origins survive casualties and exclude friendly allies.
    Older battles lacking a named initiator can still identify participants.
    Never take identity from the next queued attack or a current map selection.
    """
    races=[]
    def add(race):
        if type(race) is int and 2<=race<=12 and race not in races:races.append(race)
    if not encounter['player_attacking']:add(encounter.get('conquering_owner'))
    for unit in encounter['battle'].get('hostile',[]):
        origin=unit['origin']
        if origin['source']=='alien':add(origin['race'])
        elif origin['source']=='world':
            world=state['worlds'].get(origin['world'])
            if world:add(world['raw'][0])
    # An undefended hostile planet can have no space roster at all.
    if encounter['player_attacking'] and not races:
        identity=':'.join(map(str,encounter['destination']))
        world=state['worlds'].get(identity)
        if world:add(world['raw'][0])
    return ', '.join(civilization_name(catalog,race) for race in races) or 'Unidentified force'


def space_notice(state,catalog,encounter):
    if not encounter or encounter.get('phase')=='closed':return ''
    name=world_name(catalog,encounter['destination'])
    opponents=space_opponents(state,catalog,encounter)
    if encounter['player_attacking']:
        text=f"ATTACKING: {name} | Opponent: {opponents}"
    else:
        prefix='UNDER ATTACK' if encounter['phase']=='fighting' else 'DEFENSE RESULT'
        text=f'{prefix}: {opponents} at {name}'
    pending=len(state.get('battle_requests',[]))
    if pending:text+=f' | Other pending attacks: {pending}'
    return text
