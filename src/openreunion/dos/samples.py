"""Recovered single-block, unsigned mono PCM samples and portable conversion.

The DSP time constant stores an integer microsecond sample period (256 - TC).
Resampling uses an explicit zero-order hold; no analog card filtering is claimed.
"""
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import struct
import wave
from ..core import GameError,integer

MAX_PCM=65528
MAGIC=b'ORSM\x01'
SAMPLE_FOLDERS=('SOUND','SOUND2','SOUND3')
STORY_SAMPLES=('SATROBB1','SATROBB2','SATROBB3','TRACTOR')


@dataclass(frozen=True)
class Sample:
    time_constant: int
    pcm: bytes

    def __post_init__(self):
        integer(self.time_constant,'Sample time constant',maximum=255)
        if not isinstance(self.pcm,bytes) or not 1<=len(self.pcm)<=MAX_PCM:raise GameError('Invalid sample PCM length.')

    @property
    def period_us(self):return 256-self.time_constant

    def frames(self,rate=48000):
        integer(rate,'PCM output rate',minimum=8000,maximum=192000)
        return (len(self.pcm)*self.period_us*rate+999999)//1000000

    def converted(self):return MAGIC+bytes([self.time_constant])+struct.pack('<I',len(self.pcm))+self.pcm

    def wav(self,rate=48000):
        output=io.BytesIO();renderer=SampleRenderer(self,rate=rate)
        with wave.open(output,'wb') as stream:
            stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(rate)
            while renderer.position<renderer.total:
                stream.writeframesraw(renderer.render(min(4096,renderer.total-renderer.position)))
        return output.getvalue()


def decode_sample(data):
    if not isinstance(data,bytes) or not 8<=len(data)<=MAX_PCM+7:raise GameError('Invalid or oversized SMP file.')
    if data[0]!=1 or data[5]!=0:raise GameError('Unsupported SMP block or compression method.')
    if int.from_bytes(data[1:4],'little')!=len(data)-5 or data[-1]!=0:
        raise GameError('Invalid SMP block length or terminator.')
    return Sample(data[4],data[6:-1])


def decode_converted_sample(data):
    if not isinstance(data,bytes) or not data.startswith(MAGIC) or not 11<=len(data)<=MAX_PCM+10:
        raise GameError('Invalid or oversized converted sample.')
    if struct.unpack_from('<I',data,6)[0]!=len(data)-10:raise GameError('Invalid converted PCM length.')
    return Sample(data[5],data[10:])


def decode_driver(data):
    if not isinstance(data,bytes) or not 1<=len(data)<=6000:raise GameError('Invalid sample driver size.')
    return bytes(value^((len(data)-index)&255) for index,value in enumerate(data[::-1]))


class SampleRenderer:
    def __init__(self,sample,*,rate=48000,position=0):
        if not isinstance(sample,Sample):raise GameError('Invalid PCM sample.')
        self.sample=sample;self.total=sample.frames(rate);self.rate=rate
        integer(position,'Sample playback position',maximum=self.total);self.position=position

    def render(self,frames):
        integer(frames,'PCM frame count',maximum=65536)
        end=min(self.position+frames,self.total);period=self.sample.period_us*self.rate
        values=[(self.sample.pcm[index*1000000//period]-128)*256 for index in range(self.position,end)]
        output=bytearray(frames*4)
        for index,value in enumerate(values):struct.pack_into('<hh',output,index*4,value,value)
        self.position=end
        return bytes(output)


def audit_samples(root):
    root=Path(root);records=[]
    for folder in SAMPLE_FOLDERS:
        for path in sorted((root/folder).glob('*.SMP')):
            with path.open('rb') as stream:data=stream.read(MAX_PCM+8)
            sample=decode_sample(data)
            records.append({'path':path.relative_to(root).as_posix(),'sha256':hashlib.sha256(data).hexdigest(),
                            'pcm_sha256':hashlib.sha256(sample.pcm).hexdigest(),'pcm_bytes':len(sample.pcm),
                            'time_constant':sample.time_constant,'rate_numerator':1000000,'rate_denominator':sample.period_us,
                            'duration_us':len(sample.pcm)*sample.period_us})
    return {'version':1,'format':'single VOC type-1 PCM block plus terminator','samples':records}
