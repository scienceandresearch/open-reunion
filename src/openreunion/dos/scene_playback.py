"""Serializable story playback core; one step is one completed VGA retrace.

Campaign dispatch, wall-clock scheduling and device sound output are adapters.
The controller RNG returned by a committed step belongs to campaign state.
"""
from copy import deepcopy

from ..core import GameError,integer
from .story_cinema import initial_controller,select_animation,advance_animation,scene_script,validate_rules
from .scene_effects import start_input_wait,step_input_wait


def begin_scene(scene,rules,seed,*,key_seen=False):
    validate_rules(rules);scene_script(scene,rules)
    if type(key_seen) is not bool:raise GameError('Invalid scene keyboard latch.')
    return {'version':1,'scene':scene,'phase':'fade_in','fade_step':-1,'pc':0,'wait':None,
            'click_phase':0,'controller':initial_controller(seed),'view':{'asset':None,'frame':0},
            'key_seen':key_seen,'ticks':0}


def validate_scene(state,rules):
    validate_rules(rules)
    fields={'version','scene','phase','fade_step','pc','wait','click_phase','controller','view','key_seen','ticks'}
    if not isinstance(state,dict) or set(state)!=fields:raise GameError('Invalid saved scene fields.')
    integer(state['version'],'Scene version',minimum=1,maximum=1)
    script=scene_script(state['scene'],rules)
    if state['phase'] not in ('fade_in','body','fade_out','done'):raise GameError('Invalid scene phase.')
    integer(state['fade_step'],'Scene fade step',minimum=-1,maximum=5)
    integer(state['pc'],'Scene operation',maximum=len(script))
    integer(state['click_phase'],'Scene mouse phase',maximum=2)
    integer(state['ticks'],'Scene retraces',maximum=2**53-1)
    if type(state['key_seen']) is not bool:raise GameError('Invalid scene keyboard latch.')
    controller=state['controller'];keys={'asset','frame','delay','interval','repeats','rate','rng'}
    if not isinstance(controller,dict) or set(controller)!=keys:raise GameError('Invalid scene controller.')
    allowed={operation[1] for operation in script if operation[0]=='select'}
    integer(controller['asset'],'Scene animation',maximum=17)
    if controller['asset'] and controller['asset'] not in allowed:raise GameError('Animation does not belong to this scene.')
    for key,limit in (('frame',140),('delay',299),('repeats',255),('rate',255),('rng',2**32-1)):
        integer(controller[key],'Scene '+key,maximum=limit)
    integer(controller['interval'],'Scene interval',minimum=1,maximum=1)
    if controller['asset'] and controller['frame']>rules[controller['asset']-1]['frames']:
        raise GameError('Scene animation frame exceeds its table.')
    view=state['view']
    if not isinstance(view,dict) or set(view)!={'asset','frame'}:raise GameError('Invalid displayed scene frame.')
    if view['asset'] is None:integer(view['frame'],'Picture-only scene frame',maximum=0)
    else:
        integer(view['asset'],'Displayed scene animation',minimum=1,maximum=17)
        if view['asset'] not in allowed:raise GameError('Displayed animation does not belong to this scene.')
        integer(view['frame'],'Displayed scene frame',minimum=1,maximum=rules[view['asset']-1]['frames'])
    wait=state['wait'];phase=state['phase']
    if phase=='body':
        if state['fade_step']!=5 or state['pc']>=len(script) or not isinstance(wait,dict):
            raise GameError('Scene body has no pending timed operation.')
        operation=script[state['pc']];kind=operation[0]
        if kind in ('wait','retrace','click_cycle'):
            expected='click' if kind=='click_cycle' else 'retrace'
            if set(wait)!={'kind','remaining'} or wait['kind']!=expected:raise GameError('Invalid saved retrace wait.')
            integer(wait['remaining'],'Remaining retraces',minimum=1,maximum=1 if kind=='retrace' else operation[1])
        elif kind=='input_wait':
            if set(wait)!={'kind','input'} or wait['kind']!='input':raise GameError('Invalid saved input wait.')
            value=wait['input']
            if not isinstance(value,dict) or set(value)!={'limit','elapsed','phase','key_seen','done'}:
                raise GameError('Invalid saved input fields.')
            integer(value['limit'],'Input limit',minimum=operation[1],maximum=operation[1])
            integer(value['elapsed'],'Elapsed input retraces',maximum=value['limit']-1)
            if value['phase'] not in ('release','press') or value['done'] is not False or value['key_seen'] is not False or state['key_seen']:
                raise GameError('Completed input wait was left active.')
        else:raise GameError('Saved scene stopped on an instantaneous operation.')
    else:
        if wait is not None:raise GameError('A scene fade cannot have a pending wait.')
        if phase=='fade_in':
            if state['pc'] or state['fade_step']==5 or controller['asset'] or view['asset'] is not None:
                raise GameError('Invalid scene initialization.')
        elif state['pc']!=len(script) or controller['asset']:
            raise GameError('Unfinished scene body has entered its closing phase.')
        if phase=='done' and state['fade_step']!=5:raise GameError('Scene ended before its fade completed.')
        if phase=='fade_out' and state['fade_step']==5:raise GameError('Completed fade was left active.')


def _advance(state,rules,events):
    state['controller']=advance_animation(state['controller'],rules)
    current=state['controller'];row=rules[current['asset']-1]
    state['view']={'asset':current['asset'],'frame':current['frame']}
    events.append(('frame',current['asset'],current['frame'],row['y']*320+row['x']))


def _settle(state,rules,mouse,key,events):
    script=scene_script(state['scene'],rules)
    while state['pc']<len(script):
        operation=script[state['pc']];kind=operation[0]
        if kind=='click_cycle':
            while mouse==(state['click_phase'] in (0,2)):
                if state['click_phase']==2:
                    state['click_phase']=0;state['pc']+=1;break
                state['click_phase']+=1
            else:
                _advance(state,rules,events);events.append(('wait',operation[1]))
                state['wait']={'kind':'click','remaining':operation[1]};return
            continue
        if kind in ('wait','retrace'):
            state['wait']={'kind':'retrace','remaining':1 if kind=='retrace' else operation[1]}
            events.append(operation);return
        if kind=='input_wait':
            value=start_input_wait(operation[1],mouse=mouse,key=key,key_seen=state['key_seen'])
            events.append(operation);state['key_seen']=value['key_seen']
            if not value['done']:state['wait']={'kind':'input','input':value};return
        elif kind=='init':state['controller'].update(asset=0,frame=0,interval=1);events.append(operation)
        elif kind=='select':state['controller']=select_animation(state['controller'],rules,operation[1]);events.append(operation)
        elif kind=='advance':_advance(state,rules,events)
        elif kind=='reset_frame':state['controller']['frame']=0
        elif kind=='close':state['controller']['asset']=0;events.append(operation)
        else:events.append(operation)  # verified sound requests; device output is separate
        state['pc']+=1
    state.update(phase='fade_out',fade_step=-1,wait=None)


def tick_scene(state,rules,*,mouse=False,key=False):
    """Pure committed-retrace transition. Returned operations happen in order."""
    validate_scene(state,rules)
    if type(mouse) is not bool or type(key) is not bool:raise GameError('Invalid scene input.')
    result=deepcopy(state);events=[]
    if result['phase']=='done':return result,events
    result['ticks']+=1
    if result['phase'] in ('fade_in','fade_out'):
        inward=result['phase']=='fade_in';result['fade_step']+=1;step=result['fade_step']
        events.append(('fade',step if inward else 5-step,5))
        if step==5:
            if inward:
                result['phase']='body';_settle(result,rules,mouse,key,events)
            else:result['phase']='done';events.append(('done',))
    else:
        wait=result['wait']
        if wait['kind']=='input':
            wait['input']=step_input_wait(wait['input'],mouse=mouse,key=key)
            result['key_seen']=wait['input']['key_seen'];finished=wait['input']['done']
        else:wait['remaining']-=1;finished=wait['remaining']==0
        if finished:
            if wait['kind']!='click':result['pc']+=1
            result['wait']=None;_settle(result,rules,mouse,key,events)
    validate_scene(result,rules)
    return result,events
