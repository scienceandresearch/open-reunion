"""Transient result reveal after control presentation, without gameplay ticks."""
import time
from .video_timing import RetraceClock


class ResultFade:
    def __init__(self,owner,family):
        self.owner=owner;self.family=family;self.session=owner.app.session
        self.phase=(owner.encounter() or {}).get('phase');self.timer=None
        self.active=False;self.level=5;self.clock=None;self.previous=None;self.deadline=None
        self.stage=None

    def cancel(self):
        if self.timer is not None:self.owner.window.after_cancel(self.timer)
        self.timer=None;self.clock=None;self.deadline=None;self.active=False;self.level=5;self.previous=None
        self.stage=None
        self.owner.control_panel.locked=False

    def finish(self):
        was_active=self.active;self.cancel()
        if was_active and self.owner.window.winfo_exists():
            self.draw()
            self.owner.acknowledge_button.configure(state='normal' if (self.owner.encounter() or {}).get('phase')=='result' else 'disabled')

    def draw(self):
        if self.family=='ground':self.owner.draw_result()
        else:self.owner.draw()

    def sync(self):
        phase=(self.owner.encounter() or {}).get('phase')
        if self.session is not self.owner.app.session:
            self.cancel();self.session=self.owner.app.session;self.phase=phase;return
        previous=self.phase;self.phase=phase
        if phase!='result':self.cancel();return
        if previous in ('setup','fighting'):
            self.cancel();self.active=True;self.level=-1
            self.stage='panel'
            self.previous=getattr(self.owner,'combat_ppm',None)
            self.owner.control_panel.locked=True
            self.owner.control_panel.caption.set('');self.owner.control_panel.canvas.configure(cursor='')
            self.clock=RetraceClock(time.perf_counter_ns());self.schedule()

    def schedule(self):
        now=time.perf_counter_ns();self.deadline=self.clock.next_deadline(now)
        self.timer=self.owner.window.after((self.deadline-now+999_999)//1_000_000,lambda:self.owner.app.guard(self.tick))

    def tick(self):
        self.timer=None
        if not self.active:return
        if self.session is not self.owner.app.session or (self.owner.encounter() or {}).get('phase')!='result':self.cancel();return
        if self.owner.control_panel.busy:self.schedule();return
        try:
            if self.stage=='panel':
                self.stage='fade';self.draw();self.schedule();return
            self.level+=1
            if self.level==5:self.finish()
            else:self.draw();self.schedule()
        except Exception:
            self.finish();raise

    def picture_data(self,ppm):
        # During the preceding panel wipe, retain the last battle viewport.
        # The loader's completed progress pass proves black in all used result
        # colors; level zero therefore needs no guessed previous palette.
        if self.active and self.level<0 and self.owner.control_panel.busy and self.previous is not None:return self.previous
        return ppm

    def palette_step(self):return max(0,self.level) if self.active else 5
