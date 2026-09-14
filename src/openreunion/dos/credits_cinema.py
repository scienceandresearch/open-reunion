"""Original credits cue sequence with a separate centisecond animation clock."""
from dataclasses import dataclass,replace
from fractions import Fraction
from .credits_assets import displayed_frames
from .victory_cinema import module_rows
from .video_timing import FRAME_DOTS,PIXEL_CLOCK_HZ

ANIMATION_CUES=((10,9,22),(11,9,53),(12,10,23),(13,10,54),(14,11,22),(15,11,54),
    (16,12,22),(17,12,55),(18,13,23),(19,13,55),(20,14,23),(21,14,55),
    (22,15,56),(23,16,28),(24,16,58),(25,17,23),(26,17,55),(27,18,23))
PICTURES=('PRESENTS','GAMEBY','REUNION','PAL10','HIGHRES')


@dataclass(frozen=True)
class Shot:
    picture:str=''
    asset:int=0
    frame:int=0
    level:int=1
    divisor:int=1
    white:bool=False


def fade_levels(steps,inward,*,half=False):
    positions=range(steps//2 if half and inward else 0,(steps//2 if half and not inward else steps)+1)
    return tuple(i if inward else steps-i for i in positions)


def shot_palette(palette,shot):
    return bytes((63-(63-(v>>2))*shot.level//shot.divisor if shot.white else
                  (v>>2)*shot.level//shot.divisor)*255//63 for v in palette)


def timeline(song):
    rows,duration=module_rows(song,pattern_loops=True)
    period=Fraction(FRAME_DOTS,PIXEL_CLOCK_HZ);now=Fraction(0);shot=Shot();frames=[]
    def emit(seconds):
        nonlocal now
        if seconds>0:frames.append((now,shot));now+=seconds
    def cue(order,row):emit(max(Fraction(0),rows[order-1,row-1]-now))
    def fade(steps,inward,white=False,half=False):
        nonlocal shot
        for level in fade_levels(steps,inward,half=half):
            shot=replace(shot,level=level,divisor=steps,white=white)
            emit(Fraction(800*525,PIXEL_CLOCK_HZ) if shot.picture=='HIGHRES' else period)
    def picture(name):
        nonlocal shot
        shot=Shot(picture=name,level=shot.level,divisor=shot.divisor,white=shot.white)
    def animation(asset,order,row):
        nonlocal shot
        cue(order,row);reset=now
        for index in displayed_frames(asset):
            if index!=displayed_frames(asset).start:
                delay=2*(index%2) if asset==3 else 5 if asset==4 else 3
                reset=max(now,reset+Fraction(delay,100))
                emit((reset//period+1)*period-now)
            shot=Shot(asset=asset,frame=index)
    animation(3,1,1);cue(2,32)
    # Pascal Move restores the loaded palette before the white-to-image fade.
    picture('PRESENTS');fade(20,True,True)
    cue(3,1);fade(5,False);picture('GAMEBY');fade(70,True)
    cue(3,43);fade(5,False);picture('HIGHRES');cue(4,1);fade(70,True)
    animation(4,4,45);fade(4,False,True);picture('REUNION');fade(10,True,True)
    cue(8,1);fade(195,False);picture('PAL10');fade(70,True)
    for asset,order,row in ANIMATION_CUES:animation(asset,order,row)
    cue(20,1);fade(5,False,True,True);picture('PAL10');fade(5,True,True,True)
    cue(37,63);emit(max(Fraction(0),duration-now))
    return tuple((int(t*1_000_000_000),s) for t,s in frames),int(now*1_000_000_000)
