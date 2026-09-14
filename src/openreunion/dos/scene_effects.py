"""Recovered cinematic palette operations and resumable retrace/input waits."""
from copy import deepcopy

from ..core import GameError,integer


def _palette(value):
    if not isinstance(value,(bytes,bytearray)) or len(value)!=768 or any(v>63 for v in value):
        raise GameError('Invalid six-bit display palette.')


def load_scene_palette(picture_palette,current):
    """35F19..35FB9: source colors 0..191 become display colors 64..255."""
    _palette(current)
    if not isinstance(picture_palette,(bytes,bytearray)) or len(picture_palette)!=768:
        raise GameError('Invalid picture palette.')
    result=bytearray(current);result[192:]=bytes(value>>2 for value in picture_palette[:576])
    return bytes(result)


def fade_updates(target,*,inward=True,start=0,end=255,steps=5):
    """3518B/35292: six default updates; fade-in finally writes all colors."""
    _palette(target)
    if type(inward) is not bool:raise GameError('Invalid fade direction.')
    integer(start,'First fade color',maximum=255);integer(end,'Last fade color',minimum=start,maximum=255)
    integer(steps,'Fade steps',minimum=1,maximum=255)
    updates=[]
    for step in range(steps+1):
        level=step if inward else steps-step
        updates.extend([('retrace',),('palette',start,end,bytes(value*level//steps for value in target[start*3:(end+1)*3]))])
    if inward:updates.append(('palette',0,255,bytes(target)))
    return updates


def dac_rgb(palette):
    """Normalized full-range RGB for the 64 DAC levels, not monitor calibration."""
    _palette(palette);return bytes(value*255//63 for value in palette)


def _settle_wait(state,mouse):
    if state['elapsed']>=state['limit']:state['done']=True
    elif state['phase']=='release' and not mouse:state['phase']='press'
    elif state['phase']=='press' and mouse:state['done']=True


def start_input_wait(limit,*,mouse=False,key=False,key_seen=False):
    integer(limit,'Input wait duration',maximum=2**31-1)
    if any(type(value) is not bool for value in (mouse,key,key_seen)):raise GameError('Invalid scene input.')
    state={'limit':limit,'elapsed':0,'phase':'release','key_seen':key_seen or key,'done':key_seen or key}
    if not state['done']:_settle_wait(state,mouse)
    return state


def step_input_wait(state,*,mouse=False,key=False,legacy_keyboard=False):
    """One completed vertical retrace. Legacy mode reproduces the DOS key bug.

    DOS latches a key during the loop but never checks it again until another
    wait call. The default fixes that delay by completing this wait immediately.
    """
    if any(type(value) is not bool for value in (mouse,key,legacy_keyboard)):raise GameError('Invalid scene input.')
    result=deepcopy(state)
    if result['done']:return result
    result['elapsed']+=1;result['key_seen']|=key
    if key and not legacy_keyboard:result['done']=True
    else:_settle_wait(result,mouse)
    return result
