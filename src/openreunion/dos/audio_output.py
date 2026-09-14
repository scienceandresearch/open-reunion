"""Windows PCM streaming; synthesis runs off the Tk thread."""
import ctypes as c
import os
import threading

from ..core import GameError
from .fm_audio import FmRenderer


class WaveFormat(c.Structure):
    _pack_=1
    _fields_=[('tag',c.c_uint16),('channels',c.c_uint16),('rate',c.c_uint32),
              ('bytes_per_second',c.c_uint32),('align',c.c_uint16),('bits',c.c_uint16),('extra',c.c_uint16)]


class WaveHeader(c.Structure):
    _fields_=[('data',c.c_void_p),('length',c.c_uint32),('recorded',c.c_uint32),
              ('user',c.c_size_t),('flags',c.c_uint32),('loops',c.c_uint32),
              ('next',c.c_void_p),('reserved',c.c_size_t)]


class WaveTime(c.Structure):
    _fields_=[('kind',c.c_uint32),('value',c.c_uint32),('extra',c.c_uint32)]


class WaveOutput:
    block_frames=1024
    def __init__(self,rate):
        if os.name!='nt':raise GameError('Live audio output currently requires Windows; WAV export is available separately.')
        self.rate=rate;self.handle=c.c_void_p();self.buffers=[];self._position_counts={}
        self.api=c.WinDLL('winmm')
        signatures={'waveOutOpen':[c.POINTER(c.c_void_p),c.c_uint,c.POINTER(WaveFormat),c.c_size_t,c.c_size_t,c.c_uint],
                    'waveOutGetPosition':[c.c_void_p,c.POINTER(WaveTime),c.c_uint]}
        for name in ('waveOutPrepareHeader','waveOutUnprepareHeader','waveOutWrite'):
            signatures[name]=[c.c_void_p,c.POINTER(WaveHeader),c.c_uint]
        for name in ('waveOutPause','waveOutRestart','waveOutReset','waveOutClose'):signatures[name]=[c.c_void_p]
        for name,types in signatures.items():
            function=getattr(self.api,name);function.argtypes=types;function.restype=c.c_uint
        fmt=WaveFormat(1,2,rate,rate*4,4,16,0)
        self.check(self.api.waveOutOpen(c.byref(self.handle),0xFFFFFFFF,c.byref(fmt),0,0,0))
        try:
            for _ in range(4):
                data=c.create_string_buffer(self.block_frames*4)
                header=WaveHeader(c.cast(data,c.c_void_p),len(data),0,0,0,0,None,0)
                self.check(self.api.waveOutPrepareHeader(self.handle,c.byref(header),c.sizeof(header)))
                self.buffers.append((data,header))
        except BaseException:
            self.close();raise

    @staticmethod
    def check(result):
        if result:raise GameError(f'Windows audio device error {result}.')

    def fill(self,renderer,*,remaining=None):
        for data,header in self.buffers:
            if remaining is not None and remaining<=0:break
            if not header.flags&16:  # WHDR_INQUEUE
                pcm=renderer.render(self.block_frames)
                if len(pcm)!=self.block_frames*4:raise GameError('Audio renderer returned an invalid PCM block.')
                c.memmove(data,pcm,len(pcm))
                self.check(self.api.waveOutWrite(self.handle,c.byref(header),c.sizeof(header)))
                if remaining is not None:remaining-=self.block_frames

    def pause(self,paused):
        self.check((self.api.waveOutPause if paused else self.api.waveOutRestart)(self.handle))

    def position(self):
        value=WaveTime(2,0,0)
        self.check(self.api.waveOutGetPosition(self.handle,c.byref(value),c.sizeof(value)))
        if value.kind not in (1,2,4):raise GameError('Audio device returned an unsupported position format.')
        previous,wraps=self._position_counts.get(value.kind,(0,0))
        if value.value<previous:wraps+=1
        self._position_counts[value.kind]=(value.value,wraps)
        count=value.value+(wraps<<32)
        if value.kind==2:return count
        if value.kind==4:return count//4
        return count*self.rate//1000

    def close(self):
        if not self.handle:return
        self.check(self.api.waveOutReset(self.handle))
        for _,header in self.buffers:
            self.check(self.api.waveOutUnprepareHeader(self.handle,c.byref(header),c.sizeof(header)))
        self.check(self.api.waveOutClose(self.handle));self.handle=c.c_void_p();self.buffers=[]


class AudioPlayer:
    def __init__(self):
        self._lock=threading.RLock();self._stop=threading.Event()
        self._thread=None;self._device=None;self._paused=False
        self.error=None;self.rendered_frames=0;self.renderer=None
        self.offset_frames=0;self.seeking=False

    @property
    def playing(self):return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self):return self._paused

    def start(self,song,*,frames=0,paused=False):
        if type(frames) is not int or not 0<=frames<=2**53-1 or type(paused) is not bool:raise GameError('Invalid audio resume state.')
        self.stop();self._stop.clear();self._paused=False;self.error=None;self.rendered_frames=0
        self.offset_frames=frames;self._paused=paused;self.seeking=bool(frames)
        self._thread=threading.Thread(target=self._run,args=(song,),name='OpenReunion audio',daemon=True)
        self._thread.start()

    def _run(self,song):
        try:
            from .module_music import ModuleSong
            from .module_audio import ModuleRenderer
            renderer_type=ModuleRenderer if isinstance(song,ModuleSong) else FmRenderer
            with renderer_type(song) as renderer:
                if self.offset_frames and not renderer.seek(self.offset_frames,self._stop.is_set):return
                self.seeking=False
                with self._lock:
                    self.renderer=renderer;self.rendered_frames=renderer.frames
                    self._device=WaveOutput(renderer.rate)
                try:
                    with self._lock:
                        if self._paused:self._device.pause(True)
                    while not self._stop.is_set():
                        with self._lock:
                            if not self._paused:
                                self._device.fill(renderer);self.rendered_frames=renderer.frames
                                # Observe the DWORD counter continuously, even
                                # when the player does not save for many hours.
                                self._device.position()
                        self._stop.wait(0.005)
                finally:
                    with self._lock:
                        self._device.close();self._device=None
        except Exception as exc:self.error=str(exc)
        finally:self.renderer=None;self.seeking=False

    def pause(self,paused=True):
        with self._lock:
            if self._device:self._device.pause(paused)
            self._paused=paused

    def position(self):
        with self._lock:return self.offset_frames+(self._device.position() if self._device else 0)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(2)
            if self._thread.is_alive():raise GameError('Audio output did not stop in time.')
            self._thread=None
