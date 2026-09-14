"""Original VICTORY.PRG sequence and music-cue timing."""
from fractions import Fraction
from dataclasses import dataclass,replace
from .video_timing import FRAME_DOTS,PIXEL_CLOCK_HZ
from ..core import GameError

PICTURES=('TX1','TX2','PAL1','RETURN','TX3','EARTH','END','TX4','TX5','CR1','CR2','CR3')
ANIMATION_RULE={'frames':16,'width':320,'height':200}


def script():
    # Picture arguments: cue order/row, fade-out steps, fade-in steps.
    # Both cue coordinates are the original driver's one-based counters.
    return (
        ('music','victory\\endseq'),
        ('picture','TX1',1,1,1,40),
        ('picture','TX2',2,1,120,40),
        ('delayed_picture','PAL1',3,1,3,25,80,70),
        ('animation',1,3,30,74,0),
        ('load','RETURN'),('to_white',10),('copy',),('palette_copy',),('from_white',10),
        ('picture','TX3',4,40,120,40),
        ('picture','EARTH',5,1,5,70),
        ('picture','END',6,1,5,70),
        ('picture','TX4',8,1,5,70),
        ('picture','TX5',8,32,5,70),
        ('cue',8,50),('fade_out',70),('load_wait','CR1',1,1),
        ('clear',),('palette_set',),('credits',1,6),('cue',11,58),('input',0),
    )


def module_rows(song,*,pattern_loops=False,ignore_zero_speed=False):
    """Exact rational row starts for the timing effects used by ENDSEQ.MOD.

    This is a cue clock, not a general MOD player. Unsupported timing effects
    and cycles fail explicitly; libopenmpt handles the actual sample playback.
    """
    data=song.data;order=row=0;speed=6;tempo=125;elapsed=Fraction(0);times={};visited=set()
    loop_rows=[0]*4;loop_counts=[0]*4
    while order<len(song.orders):
        signature=(order,row,speed,tempo,tuple(loop_rows),tuple(loop_counts))
        if signature in visited or len(visited)>=100000:raise GameError('Cyclic module timing.')
        visited.add(signature);times.setdefault((order,row),elapsed)
        next_order=order;next_row=row+1;delay=0
        for channel in range(4):
            at=1084+song.orders[order]*1024+row*16+channel*4
            effect=data[at+2]&15;value=data[at+3]
            if effect==15:
                if value==0:
                    if ignore_zero_speed:continue
                    raise GameError('Unsupported zero-speed victory module.')
                if value<32:speed=value
                else:tempo=value
            elif effect==11:next_order=value;next_row=0
            elif effect==13:next_order=order+1;next_row=(value>>4)*10+(value&15)
            elif effect==14 and value>>4==6:
                if not pattern_loops:raise GameError('Unsupported victory pattern-loop timing.')
                count=value&15
                if not count:loop_rows[channel]=row
                else:
                    loop_counts[channel]=count if not loop_counts[channel] else loop_counts[channel]-1
                    if loop_counts[channel]:next_row=loop_rows[channel]
            elif effect==14 and value>>4==14:delay=value&15
        elapsed+=Fraction(speed*5*(delay+1),tempo*2)
        if next_row>=64:next_order+=1;next_row=0
        if next_order!=order:loop_rows=[0]*4;loop_counts=[0]*4
        order,row=next_order,next_row
    return times,elapsed


def cue_times(song):
    rows,duration=module_rows(song);cues=set()
    for operation in script():
        kind=operation[0]
        if kind in ('picture','delayed_picture','load_wait'):cues.add(operation[2:4])
        if kind=='delayed_picture':cues.add(operation[4:6])
        if kind=='animation':cues.add(operation[2:4])
        if kind in ('cue','credits'):cues.add(operation[1:3])
    try:return {cue:rows[cue[0]-1,cue[1]-1] for cue in cues}
    except KeyError as exc:raise GameError('Victory music does not contain a required cue.') from exc


@dataclass(frozen=True)
class Shot:
    picture: str=''
    animation: int=0
    scroll: int=-1
    level: int=1
    divisor: int=1
    white: bool=False


def timeline(song):
    """Nominal retrace transitions over the module's musical timeline.

    Real display scheduling may skip intermediate pictures to stay with audio.
    This deliberately avoids advancing the game clock or consuming its RNG.
    """
    cues=cue_times(song);period=Fraction(FRAME_DOTS,PIXEL_CLOCK_HZ)
    now=Fraction(0);shot=Shot();frames=[];loaded=''
    def emit(duration):
        nonlocal now
        if duration>0:frames.append((now,shot));now+=duration
    def cue(order,row):emit(max(Fraction(0),cues[order,row]-now))
    def fade(steps,inward,white=False):
        nonlocal shot
        for i in range(steps+1):
            shot=replace(shot,level=i if inward else steps-i,divisor=steps,white=white);emit(period)
    def show(name):
        nonlocal shot
        shot=Shot(name,level=shot.level,divisor=shot.divisor,white=shot.white)
    for operation in script():
        kind,*args=operation
        if kind=='music':continue
        if kind in ('picture','delayed_picture'):
            name,order,row,*rest=args;cue(order,row)
            outward,inward=rest[-2:];fade(outward,False);show(name)
            if kind=='delayed_picture':cue(*rest[:2])
            fade(inward,True)
        elif kind=='animation':
            _,order,row,delay,_=args;cue(order,row);origin=now
            for index in range(1,17):
                shot=Shot('PAL1',animation=index)
                if index<16:
                    # Original PIT divisor 1193, delay accumulator 74 per
                    # advance, then one retrace if the deadline required waiting.
                    due=origin+index*delay*Fraction(1193,1193182)
                    if due>now:
                        edge=due//period+1;emit(edge*period-now)
        elif kind=='load':loaded=args[0]
        elif kind=='copy':show(loaded)
        elif kind=='to_white':fade(args[0],False,True)
        elif kind=='from_white':fade(args[0],True,True)
        elif kind=='cue':cue(*args)
        elif kind=='fade_out':fade(args[0],False)
        elif kind=='load_wait':loaded=args[0];cue(*args[1:])
        elif kind=='clear':shot=Shot()
        elif kind=='credits':
            cue(*args)
            for offset in range(800):shot=Shot('CR1',scroll=offset);emit(period)
        elif kind in ('palette_copy','palette_set','input'):continue
        else:raise GameError('Unknown victory presentation operation.')
    return tuple((int(start*1_000_000_000),frame) for start,frame in frames),int(now*1_000_000_000)
