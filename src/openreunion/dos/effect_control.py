"""Optional saved effect presentation state; no gameplay clock or RNG."""
from copy import deepcopy
from ..core import GameError,integer
from .samples import STORY_SAMPLES,MAX_PCM
from .battle_samples import EFFECT_SAMPLES,V19_EFFECT_SAMPLES


def initial_effects():
    return {'version':1,'enabled':True,'sample':None,'frames':0,'paused':False}


def validate_effects(value,*,battle=True,lifecycle=True):
    if value is None:return
    if not isinstance(value,dict) or set(value)!={'version','enabled','sample','frames','paused'}:
        raise GameError('Invalid saved sound effect fields.')
    if type(value['version']) is not int or value['version']!=1:raise GameError('Unsupported saved sound effect version.')
    if any(type(value[k]) is not bool for k in ('enabled','paused')):raise GameError('Invalid sound effect flags.')
    names=(EFFECT_SAMPLES if lifecycle else V19_EFFECT_SAMPLES) if battle else STORY_SAMPLES
    if value['sample'] is not None and value['sample'] not in names:raise GameError('Invalid saved sound effect name.')
    integer(value['frames'],'Sound effect position',maximum=(MAX_PCM*256*48000+999999)//1000000)
    if value['sample'] is None and (value['frames'] or value['paused']):raise GameError('Stopped effect has a playback position.')
    if not value['enabled'] and value['sample'] is not None:raise GameError('Disabled effects contain active playback.')


def scene_effects(value,events):
    """Stage ordered scene or battle requests alongside a successful transaction."""
    validate_effects(value);result=deepcopy(value);requests=0
    for event in events:
        if event[0] not in ('sound','stop_sound'):continue
        if result is None:result=initial_effects()
        requests+=1
        if event[0]=='stop_sound':result.update(sample=None,frames=0,paused=False)
        elif result['enabled']:result.update(sample=event[1].upper(),frames=0,paused=False)
    validate_effects(result);return result,requests
