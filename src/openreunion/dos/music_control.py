"""Recovered music selector plus validated optional presentation save state."""
from copy import deepcopy
from ..core import GameError,integer
from .fm_music import MUSIC_NAMES


def select_music(backend,main_active,name):
    active=name in ('main1','main2','no')
    events=[('stop',backend),('play',backend,name)] if backend in (1,2) else []
    return active,events


def main_music(backend,main_active,mode):
    if mode in (1,2):return select_music(backend,main_active,'main'+str(mode))
    if mode==0:
        if backend==1:return main_active,[('stop',1)]
        if backend==2:return select_music(backend,main_active,'no')
    return main_active,[]


def restore_main(backend,main_active,mode):
    events=[] if main_active else main_music(backend,main_active,mode)[1]
    return True,events


def cinematic_track(scene):
    """7E53..7EE9: scene IDs are not FM track numbers."""
    return {1:'atv1',2:'atv5',3:'atv2',4:'atv5',5:'atv4',6:'atv3'}.get(scene)


def screen_entry_music(screen,pending,redraw,scene,backend,main_active):
    """Music-only projection of 7E2B..7F6E and 8283..82D4."""
    if pending or not redraw:return main_active,[]
    name=cinematic_track(scene) if screen==33 else 'talk' if screen==34 else 'failure' if screen in (35,36) else None
    return select_music(backend,main_active,name) if name else (main_active,[])


def screen_exit_music(previous,current,redraw,backend,main_active,mode):
    """5A94..5AEB and 5C93..5DD1, excluding graphics cleanup."""
    if not redraw or previous==current:return main_active,[]
    if previous in (19,29,32) and current==7:return main_music(backend,main_active,mode)
    if previous in (33,34):return restore_main(backend,main_active,mode)
    return main_active,[]


def validate_audio(value):
    if value is None:return
    if not isinstance(value,dict) or set(value)!={'version','main','scene','track','automatic','frames','paused'}:
        raise GameError('Invalid saved music fields.')
    if type(value['version']) is not int or value['version']!=1:raise GameError('Unsupported saved music version.')
    integer(value['main'],'Main music',maximum=2)
    integer(value['frames'],'Audio sample position',maximum=2**53-1)
    if value['scene'] not in ('main','space','ground','talk','manual')+tuple('cinema'+str(i) for i in range(1,11)):raise GameError('Invalid saved music scene.')
    if value['track'] is not None and value['track'] not in MUSIC_NAMES:raise GameError('Invalid saved music track.')
    if any(type(value[key]) is not bool for key in ('automatic','paused')):raise GameError('Invalid music control flags.')
    if value['track'] is None and (value['frames'] or value['paused']):raise GameError('Stopped music has a playback position.')


def initial_audio():
    return {'version':1,'main':1,'scene':'main','track':'MAIN1','automatic':True,'frames':0,'paused':False}


def campaign_scene(state):
    # These are the reconstructed desktop encounter lifecycles. Remaining
    # cinematic ATV/failure and commander-selection screen callers are separate.
    if (state.get('ground_encounter') or {}).get('phase','closed')!='closed':return 'ground'
    if (state.get('space_encounter') or {}).get('phase','closed')!='closed':return 'space'
    if state.get('active_dialog') is not None:return 'talk'
    if ((state.get('campaign') or {}).get('bar') or {}).get('conversation') is not None:return 'talk'
    scene=state.get('active_scene')
    if scene is not None:return 'talk' if scene['dialog'] is not None else 'cinema'+str(scene['playback']['scene'])
    return 'main'


def scene_music(value,scene,*,previous_scene=None):
    validate_audio(value);result=deepcopy(value)
    if scene=='main':
        previous=previous_scene if previous_scene is not None else result['scene']
        screen=33 if isinstance(previous,str) and previous.startswith('cinema') else {'main':7,'space':29,'ground':32,'talk':34}.get(previous)
        if screen is None:_,events=restore_main(1,result['scene']=='main',result['main'])
        else:_,events=screen_exit_music(screen,7,True,1,result['scene']=='main',result['main'])
        if not events:return result,False
        track='MAIN'+str(result['main']) if result['main'] else None
    elif isinstance(scene,str) and scene in tuple('cinema'+str(i) for i in range(1,11)):
        name=cinematic_track(int(scene[6:]))
        if name is None:
            # Scenes 7..10 select no new music. If a previous special screen
            # exits, its main restoration happens before this silent entry.
            previous=previous_scene if previous_scene is not None else result['scene']
            if previous in ('space','ground','talk') or isinstance(previous,str) and previous.startswith('cinema'):
                return scene_music(result,'main',previous_scene=previous)
            return result,False
        track=name.upper()
    else:
        track={'space':'SPACE','ground':'EARTH','talk':'TALK'}[scene]
    result.update(scene=scene,track=track,frames=0,paused=False)
    return result,True
