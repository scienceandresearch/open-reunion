"""Bounded original four-channel MOD assets (the DOS sample-music backend)."""
from dataclasses import dataclass
import struct
from ..core import GameError

MODULE_NAMES=('ATV1','ATV2','ATV3','ATV4','ATV5','CHOISE','EARTH','FAILURE','MAIN1','MAIN2','NO','SPACE','TALK','ENDSEQ','STEAL2')
MAX_MODULE_BYTES=4*1024*1024


@dataclass(frozen=True)
class ModuleSong:
    data: bytes
    orders: tuple
    patterns: int
    sample_bytes: int


def decode_module(data):
    if not isinstance(data,bytes) or not 1084<=len(data)<=MAX_MODULE_BYTES or data[1080:1084]!=b'M.K.':
        raise GameError('Invalid original four-channel module music.')
    count=data[950]
    if not 1<=count<=128:raise GameError('Invalid module order count.')
    orders=tuple(data[952:952+count]);patterns=max(data[952:1080])+1
    if patterns>128:raise GameError('Invalid module pattern index.')
    sample_bytes=sum(struct.unpack_from('>H',data,42+i*30)[0]*2 for i in range(31))
    if len(data)!=1084+patterns*1024+sample_bytes:
        raise GameError('Truncated module patterns/samples or unexpected trailing data.')
    for i in range(31):
        if data[44+i*30]>15 or data[45+i*30]>64:raise GameError('Invalid module sample tuning/volume.')
    return ModuleSong(data,orders,patterns,sample_bytes)
