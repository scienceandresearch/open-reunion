"""Recovered numbered battle sample names; all use the ordinary PCM format."""
from ..core import GameError,integer
from .samples import STORY_SAMPLES

BATTLE_BUFFER_BYTES=30100
GROUND_SAMPLE_IDS=tuple(range(1,12))+(20,21,22,30,31,32)
SPACE_SAMPLES=tuple('WARSND'+str(n) for n in range(1,46))
GROUND_SAMPLES=tuple('GRSND'+str(n) for n in GROUND_SAMPLE_IDS)
LIFECYCLE_SAMPLES=('RETREAT','ENDBATTL')
V19_EFFECT_SAMPLES=STORY_SAMPLES+SPACE_SAMPLES+GROUND_SAMPLES
EFFECT_SAMPLES=V19_EFFECT_SAMPLES+LIFECYCLE_SAMPLES


def battle_sample(family,number):
    integer(number,'Battle sound number',minimum=1,maximum=45)
    if family=='space':return 'WARSND'+str(number)
    if family=='ground' and number in GROUND_SAMPLE_IDS:return 'GRSND'+str(number)
    raise GameError('Unsupported battle sound.')


def sample_folder(name):
    if name in STORY_SAMPLES+LIFECYCLE_SAMPLES:return 'SOUND'
    if name in SPACE_SAMPLES:return 'SOUND2'
    if name in GROUND_SAMPLES:return 'SOUND3'
    raise GameError('Unsupported game sound effect.')


def battle_effect_requests(action,events):
    if action in ('space_acknowledge','ground_acknowledge'):
        return [('stop_sound',),('sound','ENDBATTL')]
    if action=='space_retreat' or action=='ground_command' and any(
            isinstance(e,dict) and e.get('kind')=='ground_result_requested' for e in events):
        return [('stop_sound',),('sound','RETREAT')]
    route={'space_tick':('space','sound'),'ground_tick':('ground','ground_sound'),
           'ground_command':('ground','ground_notice')}.get(action)
    if route is None:return []
    family,kind=route
    return [('sound',battle_sample(family,e['id'])) for e in events
            if isinstance(e,dict) and e.get('kind')==kind]
