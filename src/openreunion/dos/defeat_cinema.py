"""Original 30E8D..310F6 defeat film, measured in completed VGA retraces."""
from dataclasses import dataclass
from .hero import validate_hero
from ..core import integer

ANIMATIONS={15:('DEATH2',237),16:('DEATH',61)}


def defeat_cause(state):
    encounter=state.get('ground_encounter') or {}
    if encounter.get('next_phase')=='defeat':return 1
    home=state['worlds'].get('1:5:0')
    return 1 if home and home['raw'][0]>1 else 2


@dataclass(frozen=True)
class FilmFrame:
    picture: str
    asset: int=0
    step: int=0
    level: int=1
    divisor: int=1


def film(hero,cause):
    validate_hero(hero);integer(cause,'Defeat cause',minimum=1,maximum=2)
    frames=[]
    def hold(picture,count,*,asset=0,step=0):
        frames.extend([FilmFrame(picture,asset,step)]*count)
    def fade(picture,count,inward,*,asset=0,step=0):
        frames.extend(FilmFrame(picture,asset,step,i if inward else count-i,count) for i in range(count+1))
    notice=f'DEATHSZ{cause}';portrait=f'DEATH{hero}'
    fade(notice,140,True);hold(notice,720);fade(notice,70,False)
    fade(portrait,140,True)
    if hero==2:
        for step in range(1,238):hold(portrait,7,asset=15,step=step)
    else:hold(portrait,1660)
    fade(portrait,70,False,asset=15 if hero==2 else 0,step=237 if hero==2 else 0)
    # The ruins picture is copied while the hardware palette remains black.
    frames.extend([FilmFrame('DEATH',level=0)]*70);fade('DEATH',70,True)
    for step in range(1,62):hold('DEATH',12,asset=16,step=step)
    fade('DEATH',280,False,asset=16,step=61)
    return tuple(frames)


def animation_index(asset,step,count):
    integer(asset,'Defeat animation',minimum=15,maximum=16)
    integer(step,'Defeat animation step',minimum=1,maximum=ANIMATIONS[asset][1])
    # Preserve the first cycle drawn over the initial picture, then the stable
    # cycle after the complete frame-one redraw. The female base differs.
    return step if step<=count else count+(step-count-1)%count+1
