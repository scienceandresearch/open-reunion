"""37DA:01B6 control-panel reveal: even rows down, odd rows back up."""
from ..core import GameError
from .assets import Picture
from .video_timing import RetraceClock
import time


def wipe_steps(source,previous):
    """All 32 row operations and their post-operation retrace flags.

    The panel caller uses exactly 320x32. Retain destination pixels until the
    original copy/fill reaches them; fill color is the original index 0x40.
    """
    if any(not isinstance(p,bytes) or len(p)!=320*32 for p in (source,previous)):
        raise GameError('Expected 320x32 control wipe buffers.')
    pixels=bytearray(previous);steps=[]
    for index,row in enumerate(range(0,32,2),1):
        at=row*320;pixels[at:at+320]=source[at:at+320]
        pixels[at+320:at+640]=bytes([64])*320
        steps.append((bytes(pixels),bool(index%2)))
    for index,row in enumerate(range(31,0,-2),1):
        at=row*320;pixels[at:at+320]=source[at:at+320]
        steps.append((bytes(pixels),bool(index%2)))
    return tuple(steps)


def wipe_pictures(target,previous):
    if (target.width,target.height)!=(320,32):raise GameError('Invalid control wipe picture.')
    return tuple((Picture(320,32,pixels,target.palette),wait) for pixels,wait in wipe_steps(target.pixels,previous))


class ControlWipePlayback:
    """One timer; replacement starts from the last displayed indexed pixels."""
    def __init__(self,panel,guard):
        self.panel=panel;self.guard=guard;self.timer=None;self.clock=None
        self.steps=();self.index=0;self.deadline=None

    @property
    def active(self):return self.clock is not None

    def cancel(self):
        if self.timer is not None:self.panel.after_cancel(self.timer)
        for image,_ in self.steps:self.panel.picture_data.pop(str(image),None)
        self.timer=None;self.clock=None;self.steps=();self.deadline=None

    def start(self,target):
        previous=self.panel.displayed_picture
        pixels=previous.pixels if previous is not None else bytes(320*32)
        pictures=wipe_pictures(target,pixels)
        self.steps=tuple((self.panel.make_image(p),wait) for p,wait in pictures)
        self.index=0;self.clock=RetraceClock(time.perf_counter_ns())
        self.panel.caption.set('');self.panel.canvas.configure(cursor='')
        self.tick()

    def tick(self):
        self.timer=None
        if not self.active:return
        try:
            while self.index<len(self.steps):
                image,wait=self.steps[self.index];self.index+=1;self.panel.paint(image)
                if wait:
                    now=time.perf_counter_ns();self.deadline=self.clock.next_deadline(now)
                    self.timer=self.panel.after((self.deadline-now+999_999)//1_000_000,lambda:self.guard(self.tick))
                    return
            self.cancel();self.panel.show(self.panel.number,self.panel.commands)
        except Exception:
            self.cancel()
            if self.panel.winfo_exists():self.panel.show(self.panel.number,self.panel.commands)
            raise
