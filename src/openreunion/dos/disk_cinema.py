"""Original CD tray and disc motion, scheduled without blocking Tk input."""
from bisect import bisect_right
import time
from .video_timing import FRAME_DOTS,PIXEL_CLOCK_HZ


def sequence(old_main,new_main):
    frames=[]
    if old_main:
        frames.extend((i+1,None,3) for i in range(22))
        frames.extend((23,i,2) for i in range(22))
        frames.append((23,None,10))
    if new_main:
        frames.extend((23,i,2) for i in range(21,-1,-1))
        frames.extend((i+1,None,3) for i in range(21,-1,-1))
    return tuple(frames)


def disc_copy(step):
    return (1+79*min(step//5,3),1,78,18),(176,max(49,152-5*step))


class DiskCinema:
    def __init__(self,app):
        self.app=app;self.timer=None;self.frames=();self.starts=();self.position=0;self.duration=0;self.owner=None

    @property
    def running(self):return bool(self.frames)

    def cancel(self):
        if self.timer is not None:
            self.app.root.after_cancel(self.timer);self.timer=None
        self.frames=();self.owner=None

    def start(self,old_main,new_main):
        self.cancel();self.frames=sequence(old_main,new_main);self.owner=self.app.session
        at=0;starts=[]
        for _,__,wait in self.frames:starts.append(at);at+=wait
        self.starts=tuple(starts);self.duration=at;self.position=0;self.origin=time.perf_counter_ns()
        self.tick()

    def tick(self):
        self.timer=None
        if not self.running:return
        if self.app.screen!='disk' or self.owner is not self.app.session:
            self.cancel();return
        elapsed=(time.perf_counter_ns()-self.origin)*PIXEL_CLOCK_HZ/(FRAME_DOTS*1_000_000_000)
        if elapsed>=self.duration:self.cancel();self.app.render_original();return
        self.position=max(0,bisect_right(self.starts,elapsed)-1)
        self.app.render_original();self.timer=self.app.root.after(10,self.tick)

    def draw(self,renderer,target,main):
        frame,disc,_=self.frames[self.position] if self.running else (1 if main else 23,None,0)
        target.blit(self.app.content.disk_animation(frame),166,150)
        if disc is not None:
            source,(x,y)=disc_copy(disc)
            target.blit(renderer.asset('DISKBR'),x,y,source=source,transparent=0)
