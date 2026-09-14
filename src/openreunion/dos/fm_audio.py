"""FM register-to-PCM synthesis, independent of the campaign clock and RNG."""
import ctypes
import os
from pathlib import Path
import platform
import threading
import wave

from ..core import GameError
from .fm_music import FmPlayer

PIT_HZ=1193182
BIOS_DIVISOR=65536


def default_library():
    configured=os.environ.get('OPENREUNION_OPL_LIBRARY')
    if configured:return Path(configured)
    suffix='.dll' if os.name=='nt' else '.dylib' if platform.system()=='Darwin' else '.so'
    return Path(__file__).resolve().parents[3]/'local/native'/('openreunion_opl'+suffix)


class OplSynth:
    def __init__(self,rate=48000,library=None):
        if type(rate) is not int or not 8000<=rate<=192000:raise GameError('Unsupported audio sample rate.')
        self._lock=threading.RLock();self._chip=None
        path=Path(library) if library else default_library()
        try:self._lib=ctypes.CDLL(str(path.resolve()))
        except OSError as exc:raise GameError('FM synthesizer is unavailable. Build it with python tools/build_audio.py.') from exc
        lib=self._lib
        try:
            lib.reunion_opl_abi.argtypes=[];lib.reunion_opl_abi.restype=ctypes.c_uint
            if lib.reunion_opl_abi()!=1:raise GameError('Unsupported FM synthesizer ABI.')
            lib.reunion_opl_create.argtypes=[ctypes.c_uint];lib.reunion_opl_create.restype=ctypes.c_void_p
            lib.reunion_opl_destroy.argtypes=[ctypes.c_void_p];lib.reunion_opl_destroy.restype=None
            lib.reunion_opl_write.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint];lib.reunion_opl_write.restype=None
            lib.reunion_opl_generate.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int16),ctypes.c_uint];lib.reunion_opl_generate.restype=None
        except AttributeError as exc:raise GameError('Invalid FM synthesizer library.') from exc
        self._chip=lib.reunion_opl_create(rate)
        if not self._chip:raise GameError('Unable to allocate FM synthesizer.')
        self.rate=rate

    def _open(self):
        if not self._chip:raise GameError('FM synthesizer is closed.')

    def write(self,writes):
        values=list(writes)
        if any(type(reg) is not int or type(value) is not int or not 0<=reg<512 or not 0<=value<256 for reg,value in values):
            raise GameError('Invalid FM register write.')
        with self._lock:
            self._open()
            for reg,value in values:self._lib.reunion_opl_write(self._chip,reg,value)

    def generate(self,frames):
        if type(frames) is not int or not 0<=frames<=192000:raise GameError('Invalid audio block length.')
        with self._lock:
            self._open();buffer=(ctypes.c_int16*(frames*2))()
            self._lib.reunion_opl_generate(self._chip,buffer,frames)
            return bytes(buffer)

    def close(self):
        with self._lock:
            if self._chip:self._lib.reunion_opl_destroy(self._chip);self._chip=None

    def __enter__(self):return self
    def __exit__(self,*_):self.close()


class FmRenderer:
    """Pull-based audio with integer sample scheduling at the nominal BIOS rate.

    The first IRQ occurs one tick after initialization. Fractional samples are
    carried across tick boundaries; the caller's block sizes cannot add drift.
    """
    def __init__(self,song,rate=48000,library=None,*,synth=None):
        self.player=FmPlayer(song);self.synth=synth if synth is not None else OplSynth(rate,library)
        self.rate=self.synth.rate;self.frames=0;self.ticks=0
        self.synth.write(self.player.initial_writes)

    def render(self,frames):
        if type(frames) is not int or not 0<=frames<=192000:raise GameError('Invalid audio block length.')
        pieces=[];remaining=frames
        while remaining:
            boundary=(self.ticks+1)*self.rate*BIOS_DIVISOR//PIT_HZ
            if self.frames==boundary:
                self.synth.write(self.player.tick());self.ticks+=1;continue
            count=min(remaining,boundary-self.frames)
            pieces.append(self.synth.generate(count));self.frames+=count;remaining-=count
        return b''.join(pieces)

    def close(self):self.synth.close()
    def seek(self,frames,cancelled=lambda:False):
        if type(frames) is not int or frames<self.frames or frames>2**53-1:raise GameError('Invalid audio seek position.')
        while self.frames<frames:
            if cancelled():return False
            self.render(min(4096,frames-self.frames))
        return True
    def __enter__(self):return self
    def __exit__(self,*_):self.close()


def render_wave(song,path,seconds,*,rate=48000,library=None):
    if type(seconds) is not int or not 1<=seconds<=3600:raise GameError('Audio duration must be 1 to 3600 seconds.')
    with FmRenderer(song,rate,library) as renderer:
        # Exclusive creation protects an existing recording or original asset.
        with Path(path).open('xb') as output,wave.open(output,'wb') as wav:
            wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(rate)
            remaining=seconds*rate
            while remaining:
                count=min(remaining,4096);wav.writeframesraw(renderer.render(count));remaining-=count
        return {'frames':renderer.frames,'ticks':renderer.ticks,'sample_rate':rate,'channels':2}
