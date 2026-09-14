"""Recovered nine-channel FM music data and deterministic register sequencer.

This module produces ordered OPL register writes. Audio synthesis and campaign
music scheduling belong to the presentation adapter and are not implemented here.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from ..core import GameError

MAX_MUSIC_BYTES = 0x7BD4
PATTERN_OFFSET = 51+128*12
PATTERN_BYTES = 64*9*2
CONVERTED_MAGIC = b'OpenReunionFM1\0'
MUSIC_NAMES = ('ATV1','ATV2','ATV3','ATV4','ATV5','CHOISE','EARTH','FAILURE','MAIN1','MAIN2','SPACE','TALK')
OPERATORS = ((3,0),(4,1),(5,2),(11,8),(12,9),(13,10),(19,16),(20,17),(21,18))
FREQUENCIES = (0,)+tuple(note+octave*1024 for octave in range(8) for note in
                        (0x216B,0x2181,0x2198,0x21B0,0x21CA,0x21E5,
                         0x2202,0x2220,0x2241,0x2263,0x2287,0x22AE))


@dataclass(frozen=True)
class FmSong:
    orders: tuple
    instruments: tuple
    patterns: tuple
    trailing: bytes


def unpack_music(data):
    """Original 3720D..37302 transformation; does not infer a file's format."""
    if not isinstance(data,bytes) or not 1<=len(data)<=MAX_MUSIC_BYTES:
        raise GameError('FM music data exceeds supported bounds.')
    return bytes((value+47)&255 for value in reversed(data))


def decode_music(data):
    return _parse_music(unpack_music(data))


def decode_converted_music(data):
    if not isinstance(data,bytes) or not data.startswith(CONVERTED_MAGIC) or len(data)>MAX_MUSIC_BYTES+len(CONVERTED_MAGIC):
        raise GameError('Invalid converted FM music.')
    return _parse_music(data[len(CONVERTED_MAGIC):])


def _parse_music(decoded):
    if len(decoded)<PATTERN_OFFSET+PATTERN_BYTES:
        raise GameError('Truncated FM music header or patterns.')
    table=decoded[:51]
    if 255 not in table or table[0]==255:
        raise GameError('FM music requires a nonempty terminated order list.')
    orders=tuple(table[:table.index(255)])
    count=max(orders)+1
    end=PATTERN_OFFSET+count*PATTERN_BYTES
    if end>len(decoded):
        raise GameError('FM music order references a truncated or missing pattern.')
    instruments=tuple(decoded[51+i*12:51+(i+1)*12] for i in range(128))
    patterns=tuple(decoded[PATTERN_OFFSET+i*PATTERN_BYTES:PATTERN_OFFSET+(i+1)*PATTERN_BYTES]
                   for i in range(count))
    for pattern in patterns:
        for note in pattern[::2]:
            if note>97 and note not in (127,128):
                raise GameError('FM music note exceeds the original frequency table.')
    return FmSong(orders,instruments,patterns,decoded[end:])


def audit_music(root,output=None):
    root=Path(root).resolve();output=Path(output).resolve() if output else None
    if output and output.is_relative_to(root) and 'opensource' not in output.relative_to(root).parts:
        raise GameError('Converted music must not be written into the source installation.')
    report={'decoded':[],'unsupported':[]}
    for name in MUSIC_NAMES:
        path=root/'GRWAR'/(name+'.PIC')
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):continue
        with path.open('rb') as stream:data=stream.read(MAX_MUSIC_BYTES+1)
        record={'path':f'GRWAR/{name}.PIC','sha256':hashlib.sha256(data).hexdigest()}
        try:
            song=decode_music(data);decoded=unpack_music(data)
        except GameError as exc:
            record['error']=str(exc);report['unsupported'].append(record);continue
        record.update(orders=len(song.orders),patterns=len(song.patterns),trailing_bytes=len(song.trailing),
                      decoded_sha256=hashlib.sha256(decoded).hexdigest())
        report['decoded'].append(record)
        if output:
            output.mkdir(parents=True,exist_ok=True)
            (output/(name+'.ofm')).write_bytes(CONVERTED_MAGIC+decoded)
    return report


class FmPlayer:
    """One original timer interrupt per tick; no RNG or wall-clock access.

    Note-off updates the actual frequency bank, correcting DOS's wrong address.
    Unexplained trailing file bytes are retained by FmSong, never interpreted.
    """
    def __init__(self,song):
        self.song=song
        self.frequency=[0]*9;self.frequency_dirty=[1]*9
        self.level1=[0]*9;self.level2=[0]*9
        self.level1_dirty=[1]*9;self.level2_dirty=[1]*9
        self.instrument=[255]*9;self.detune=[0]*9
        self.note=[0]*9;self.note_dirty=[0]*9
        self.meter=[255]*9;self.pulse=[0]*9
        self.volume=0;self.wait=1;self.speed=2
        self.order=0;self.pattern=0;self.row=0
        self.writes=[]
        for register in (1,*range(0xB0,0xB9)):self._write(register,0)
        for register in (0x80,0x81,0x82,0x83,0x84,0x85,0x88,0x89,0x8A,
                         0x8B,0x8C,0x8D,0x90,0x91,0x92,0x93,0x94,0x95):
            self._write(register,255)
        for register,value in ((1,32),(8,64),(0xBD,0)):self._write(register,value)
        for channel in range(9):self._instrument(channel,channel)
        self.initial_writes=self.writes[:];self.writes=[]

    def _write(self,register,value):self.writes.append([register,value&255])

    def _instrument(self,channel,index):
        if self.instrument[channel]==index:return
        self.instrument[channel]=index;record=self.song.instruments[index]
        first,second=OPERATORS[channel]
        self._write(0xB0+channel,0);self._write(0xC0+channel,record[8])
        for register,a,b in ((0x20,0,1),(0x60,4,5),(0x80,6,7),(0xE0,9,10),(0x40,2,3)):
            self._write(register+first,record[a]);self._write(register+second,record[b])
        self.level1[channel]=record[2];self.level2[channel]=record[3]
        self.level1_dirty[channel]=self.level2_dirty[channel]=1
        self.detune[channel]=record[11]>>4

    def _event(self,channel,note,effect):
        if note==128:
            self._instrument(channel,effect&127);return
        if note==127:
            self.frequency[channel]&=~0x2000
            self.frequency_dirty[channel]=1
        elif note:
            self.note[channel]=note;self.note_dirty[channel]=1
            self._write(0xB0+channel,0)
            self.frequency[channel]=FREQUENCIES[note-1]
            self.frequency_dirty[channel]=1
        if not effect:return
        if effect==1:
            self.row=63;return
        kind,value=effect>>4,effect&15
        if kind in (1,2):
            low=self.frequency[channel]&255
            low=(low+(value+1)*(1 if kind==1 else -1))&255
            self.frequency[channel]=(self.frequency[channel]&0xFF00)|low
            self.frequency_dirty[channel]=1
        elif kind in (10,11,12):
            if kind in (10,12):
                self.level1[channel]=value*4;self.level1_dirty[channel]=1
            if kind==11 or (kind==12 and self.song.instruments[self.instrument[channel]][8]&1):
                self.level2[channel]=value*4;self.level2_dirty[channel]=1
        else:
            # The original falls through for every otherwise-unhandled nibble.
            self.speed=self.wait=value+1

    def _level(self,value):
        inverse=(63-value)&255
        return ((63-((inverse&63)*((63-self.volume)&255)//63))&63)|(inverse&192)

    def tick(self):
        self.writes=[];self.wait=(self.wait-1)&255
        if not self.wait:
            self.wait=self.speed;self.pattern=self.song.orders[self.order]
            start=self.row*18;row=self.song.patterns[self.pattern][start:start+18]
            for channel in range(9):self._event(channel,*row[channel*2:channel*2+2])
            self.row+=1
            if self.row==64:
                self.row=0;self.order=(self.order+1)%len(self.song.orders)
        for channel in reversed(range(9)):
            self.pulse[channel]=0
            if self.note_dirty[channel]:
                level=(128-(self.level1[channel]&63)-(self.level2[channel]&63))>>3
                self.meter[channel]=min(level,15)+1;self.note_dirty[channel]=0;self.pulse[channel]=255
            if self.meter[channel]!=255:self.meter[channel]=(self.meter[channel]-1)&255
        for channel in reversed(range(9)):
            if self.detune[channel] or self.frequency_dirty[channel]:
                self.frequency_dirty[channel]=0
                self._write(0xA0+channel,(self.frequency[channel]&255)+self.detune[channel])
                self._write(0xB0+channel,self.frequency[channel]>>8)
            first,second=OPERATORS[channel]
            if self.level1_dirty[channel]:
                self.level1_dirty[channel]=0;self._write(0x40+first,self._level(self.level1[channel]))
            if self.level2_dirty[channel]:
                self.level2_dirty[channel]=0;value=self.level2[channel]
                if self.song.instruments[self.instrument[channel]][8]&1:value=self._level(value)
                self._write(0x40+second,value)
        return self.writes[:]
