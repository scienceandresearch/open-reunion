"""Saved result-presentation cursor, independent of campaign state and RNG."""
from ..core import GameError,integer
from .battle_results import advance_ground_result


def has_defeat(state):
    encounter=state.get('ground_encounter')
    return bool(encounter and encounter['phase'] in ('result','closed') and not encounter['battle']['player_won'])


def initial_animation(state,*,paused=True):
    if not has_defeat(state):return None
    # Result entry already invokes D1B9 once: frame 1 drawn, next=2, count=1.
    return {'version':1,'frame':2,'counter':1,'shown':1,
            'paused':paused or state['ground_encounter']['phase']=='closed'}


def validate_animation(value,state):
    if value is None:return
    if not isinstance(value,dict) or set(value)!={'version','frame','counter','shown','paused'}:
        raise GameError('Invalid saved result-animation fields.')
    if type(value['version']) is not int or value['version']!=1 or type(value['paused']) is not bool:
        raise GameError('Invalid result-animation version or pause state.')
    for field,maximum in (('frame',3),('counter',13),('shown',3)):
        integer(value[field],'Result animation '+field,minimum=1,maximum=maximum)
    if value['shown']!=((value['frame']+1)%3+1):raise GameError('Result animation disagrees with its displayed frame.')
    if not has_defeat(state):raise GameError('Saved animation has no ground defeat result.')
    if state['ground_encounter']['phase']=='closed' and not value['paused']:raise GameError('Closed result animation is running.')


def stage_animation(value,before,after):
    validate_animation(value,before)
    if not has_defeat(after):return None
    new=after['ground_encounter']
    if not has_defeat(before) or value is None:
        result=initial_animation(after,paused=False)
    else:result=dict(value)
    if new['phase']=='closed':result['paused']=True
    validate_animation(result,after);return result


def tick_animation(value,state):
    validate_animation(value,state)
    if value is None or value['paused'] or state['ground_encounter']['phase']!='result':return value,False
    frame,counter,paint=advance_ground_result(value['frame'],value['counter'])
    result=dict(value,frame=frame,counter=counter)
    if paint is not None:result['shown']=paint
    validate_animation(result,state);return result,paint is not None
