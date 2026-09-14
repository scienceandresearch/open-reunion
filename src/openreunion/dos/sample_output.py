"""Single-voice finite PCM output with consumed-position pause and resume.

The game has one sample buffer separate from FM music. A successful new start
stops the previous device before opening its replacement. Validation occurs
first so an invalid native request does not interrupt working playback.
"""
import threading
from ..core import GameError
from .audio_output import WaveOutput
from .samples import SampleRenderer


class SamplePlayer:
    def __init__(self):
        self._lock=threading.RLock();self._stop=threading.Event()
        self._thread=None;self._device=None;self._paused=False
        self._consumed=0;self.offset_frames=0;self.total_frames=0
        self.rendered_frames=0;self.error=None;self.completed=False

    @property
    def playing(self):return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self):return self._paused

    def start(self,sample,*,frames=0,paused=False):
        if type(paused) is not bool:raise GameError('Invalid sample pause state.')
        renderer=SampleRenderer(sample,position=frames)
        self.stop()
        with self._lock:
            self._stop.clear();self.error=None;self.completed=frames==renderer.total
            self.offset_frames=frames;self._consumed=frames;self.rendered_frames=frames
            self.total_frames=renderer.total;self._paused=paused
            if self.completed:return
            self._thread=threading.Thread(target=self._run,args=(renderer,),name='OpenReunion sample',daemon=True)
            self._thread.start()

    def _position(self):
        if self._device:
            self._consumed=max(self._consumed,min(self.total_frames,self.offset_frames+self._device.position()))
        return self._consumed

    def position(self):
        with self._lock:return self._position()

    def pause(self,paused=True):
        if type(paused) is not bool:raise GameError('Invalid sample pause state.')
        with self._lock:
            if self._device:self._device.pause(paused)
            self._paused=paused
            self._position()

    def _run(self,renderer):
        try:
            with self._lock:
                if self._stop.is_set():return
                self._device=WaveOutput(renderer.rate)
            try:
                with self._lock:
                    if self._paused:self._device.pause(True)
                while not self._stop.is_set():
                    with self._lock:
                        if not self._paused:
                            self._device.fill(renderer,remaining=renderer.total-renderer.position)
                            self.rendered_frames=renderer.position
                            if self._position()>=self.total_frames:
                                self.completed=True;break
                    self._stop.wait(.005)
            finally:
                with self._lock:
                    try:
                        # Freeze consumption before the final cursor capture;
                        # resetting queued buffers must not advance that cursor.
                        self._device.pause(True)
                        self._position()
                    finally:
                        try:self._device.close()
                        finally:self._device=None
        except Exception as exc:self.error=str(exc)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(2)
            if self._thread.is_alive():raise GameError('Sample output did not stop in time.')
            self._thread=None
