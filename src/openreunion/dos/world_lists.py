"""Original galaxy-list categories with a shared native discovery gate."""
from .orbital import can_deploy_station
from .world_info import survey_information

FILTERS=('All discovered','Colonies & stations','Suitable sites','Alien worlds')
CATEGORIES={1:{1:'Colony',2:'Miner station'},2:{1:'Colony site',2:'Mining site'},
            3:{1:'Alien world',2:'Enemy world',3:'Friendly world'}}


def world_visible(state,definition):
    system,planet=definition['system'],definition['planet']
    return (state['known_systems'][system-1]==1 and
            state['campaign']['navigation']['planet_visibility'][8*(system-1)+planet-1]<128)


def list_category(raw,catalog,campaign,mode):
    """8445..8623, segment 0390. Zero excludes a world from the list."""
    owner=raw[0];survey=raw[12] if raw[12]<128 else raw[12]-256
    if mode==1:
        return 1 if owner==1 and raw[6] else 2 if owner==1 and raw[10] else 0
    if mode==2:
        colony=(not raw[6] and not raw[7] and survey>=30 and owner<2 and
                survey_information(raw,catalog)['habitable'])
        return 1 if colony else 2 if can_deploy_station(raw,1) else 0
    if mode==3:
        if not 2<=owner<=12:return 0
        bar=campaign['bar']
        known=bool(bar and bar['intelligence'][owner-1]) or survey>=40
        relation=campaign['civilizations'][owner-2][27]
        if not known:return 1 if survey>=30 else 0
        return {4:1,2:2,6:3}.get(relation,0)
    raise ValueError('Unknown original world-list mode.')


def filtered_worlds(state,catalog,selected=FILTERS[0]):
    mode=FILTERS.index(selected);result=[]
    for definition in sorted(catalog['worlds'],key=lambda w:(w['system'],w['planet'],w['moon'])):
        if not world_visible(state,definition):continue
        raw=state['worlds'][definition['id']]['raw']
        if mode:
            category=list_category(raw,catalog,state['campaign'],mode)
            if not category:continue
            label=CATEGORIES[mode][category]
        else:label=''
        result.append((definition,label))
    return result
