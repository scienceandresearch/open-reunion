"""Original story scene scripts and cumulative main-animation frames."""
from copy import deepcopy
import hashlib
import struct

from ..core import GameError,integer
from .animation import decode_frame
from .campaign import random_bounded
from .catalog import DATA_FILE_OFFSET

STORY_ASSETS={8:9,9:9,10:1,13:10,14:2}


def validate_rules(rows):
    if not isinstance(rows,list) or len(rows)!=17:raise GameError('Invalid main animation table.')
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'frames','width','height','x','y','rate','repeats'}:
            raise GameError('Invalid main animation fields.')
        for key,limit in (('frames',140),('width',320),('height',200),('x',319),('y',199),('rate',255),('repeats',255)):
            integer(row[key],'Main animation '+key,minimum=1 if key in ('frames','width','height') else 0,maximum=limit)
        if row['x']+row['width']>320 or row['y']+row['height']>200:raise GameError('Main animation exceeds the screen.')


def read_rules(executable):
    if len(executable)<DATA_FILE_OFFSET+0x56B0:raise GameError('Truncated story animation tables.')
    rows=[]
    for asset in range(1,18):
        count,width,height,x,y=struct.unpack_from('<BHBHB',executable,DATA_FILE_OFFSET+0x55D7+7*asset)
        rate,repeats=executable[DATA_FILE_OFFSET+0x5652+5*asset:DATA_FILE_OFFSET+0x5654+5*asset]
        if not 1<=count<=140 or not 1<=width<=320 or not 1<=height<=200 or x+width>320 or y+height>200:
            raise GameError('Invalid story animation geometry.')
        rows.append({'frames':count,'width':width,'height':height,'x':x,'y':y,'rate':rate,'repeats':repeats})
    validate_rules(rows);return rows


def read_main_animation(data,row):
    """The loader reads exactly the table's frame count; retain any unused tail.

    These records draw on the current buffer. A zero length does not draw.
    They must not be reconstructed independently against frame one as space
    battle assets are. MAIN13 includes data after the declared 41 frames.
    """
    if len(data)>2*1024*1024:raise GameError('Main animation exceeds input limit.')
    frames=[];position=0;background=bytes(row['width']*row['height'])
    for _ in range(row['frames']):
        if position+2>len(data):raise GameError('Truncated main animation container.')
        length=struct.unpack_from('<H',data,position)[0];position+=2
        if not length:frames.append(None);continue
        end=position+13+length
        if end>len(data):raise GameError('Truncated main animation frame.')
        raw=data[position:end];position=end
        width,height,_=decode_frame(raw,background)
        if (width,height)!=(row['width'],row['height']):raise GameError('Main animation dimensions disagree with its table.')
        frames.append(raw)
    return tuple(frames),bytes(data[position:])


def audit_animations(root,rules):
    decoded=[];missing=[]
    for asset,row in enumerate(rules,1):
        relative=f'ANIM/MAIN{asset}.ANI';path=root/relative
        if not path.is_file():missing.append({'path':relative,'declared_frames':row['frames']});continue
        with path.open('rb') as stream:data=stream.read(2*1024*1024+1)
        frames,tail=read_main_animation(data,row)
        decoded.append({'path':relative,'sha256':hashlib.sha256(data).hexdigest(),'declared_frames':len(frames),
                        'unused_bytes':len(tail),'unused_sha256':hashlib.sha256(tail).hexdigest() if tail else None,
                        'converted_story_asset':asset in STORY_ASSETS})
    return {'decoded':decoded,'missing':missing}


def draw_frame(frames,frame,background):
    integer(frame,'Main animation frame',minimum=1,maximum=len(frames))
    raw=frames[frame-1]
    return bytes(background) if raw is None else decode_frame(raw,background)[2]


def initial_controller(seed):
    integer(seed,'Scene random seed',maximum=2**32-1)
    return {'asset':0,'frame':0,'delay':0,'interval':1,'repeats':0,'rate':0,'rng':seed}


def select_animation(state,rules,asset):
    integer(asset,'Main animation',minimum=1,maximum=len(rules))
    result=deepcopy(state);row=rules[asset-1]
    result['rng'],roll=random_bounded(result['rng'],200)
    result.update(asset=asset,frame=1,delay=100+roll,repeats=row['repeats'],rate=row['rate'])
    return result


def advance_animation(state,rules):
    result=deepcopy(state)
    if result['asset']:
        result['frame']+=1
        if result['frame']>rules[result['asset']-1]['frames']:result['frame']=1
    return result


def scene_script(scene,rules):
    """230B8..232DD, after the original picture load and palette fade-in.

    Operations preserve retrace counts instead of assuming a wall-clock rate.
    click_cycle requires the original three mouse phases: wait for press,
    release, then press. Its interpreter must keep advancing animation.
    """
    integer(scene,'Story scene',minimum=1,maximum=10)
    result=[]
    def emit(*operation):result.append(operation)
    if scene not in (1,2,9,10):emit('input_wait',30000)
    if scene==1:
        emit('init');emit('select',10);emit('click_cycle',10);emit('close')
    if scene==2:
        emit('init');emit('select',14);emit('input_wait',20)
        for _ in range(1,rules[13]['frames']):emit('advance');emit('wait',6)
        emit('close');emit('input_wait',30000)
    if scene==9:
        emit('init');emit('select',8);emit('reset_frame')
        for frame in range(1,rules[7]['frames']+1):
            if frame==5:emit('sound','satrobb1')
            emit('advance');emit('wait',2)
        emit('sound','satrobb2');emit('select',9);emit('reset_frame')
        for frame in range(1,rules[8]['frames']+1):
            if frame==18:emit('sound','satrobb3')
            emit('advance');emit('retrace')
            if frame>28:emit('wait',4)
        emit('close')
    if scene==10:
        emit('init');emit('select',13);emit('reset_frame')
        for frame in range(1,rules[12]['frames']+1):
            if frame==10:emit('sound','tractor')
            emit('advance');emit('wait',5)
        emit('stop_sound');emit('close')
    return result
