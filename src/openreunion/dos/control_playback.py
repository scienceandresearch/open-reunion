"""Cancellable original page slides; no gameplay state or random draws."""
import time
from .control_slide import PageClock


class ControlPagePlayback:
    def __init__(self,panel,guard):
        self.panel=panel;self.guard=guard;self.timer=None;self.clock=None
        self.frames=();self.index=0;self.stage=None;self.deadline=None

    @property
    def active(self):return self.clock is not None

    def cancel(self):
        if self.timer is not None:self.panel.after_cancel(self.timer)
        self.timer=None;self.clock=None;self.frames=();self.stage=None;self.deadline=None

    def start(self):
        if self.active:return
        frames=self.panel.slide_images() # Prepare before advancing the clock.
        self.frames=frames;self.index=0;self.clock=PageClock(time.perf_counter_ns())
        self.panel.caption.set('');self.panel.canvas.configure(cursor='')
        self.schedule('draw')

    def schedule(self,stage):
        self.stage=stage;now=time.perf_counter_ns()
        self.deadline=(self.clock.display_deadline(now) if stage=='draw' else self.clock.retrace_deadline(now))
        self.timer=self.panel.after((self.deadline-now+999_999)//1_000_000,lambda:self.guard(self.tick))

    def tick(self):
        self.timer=None
        if not self.active:return
        try:
            if self.stage=='draw':
                self.panel.paint(self.frames[self.index]);self.index+=1;self.schedule('retrace')
            elif self.index==len(self.frames):
                self.cancel();self.panel.page=1-self.panel.page
                self.panel.show(self.panel.number,self.panel.commands)
            else:self.schedule('draw')
        except Exception:
            self.cancel()
            if self.panel.winfo_exists():self.panel.show(self.panel.number,self.panel.commands)
            raise
