"""Desktop result clock and timer ownership; no gameplay transactions."""
import time
from .video_timing import RetraceClock


class ResultPlayback:
    def __init__(self,owner):
        self.owner=owner;self.session=owner.app.session;self.timer=None;self.clock=None

    def cancel(self):
        if self.timer is not None:
            self.owner.window.after_cancel(self.timer);self.timer=None
        self.clock=None

    def pause(self):
        self.cancel();self.session.pause_result_animation()
        self.controls()

    def controls(self):
        if not self.owner.result_play_button.winfo_exists():return
        value=self.session.result_animation
        playable=value is not None and (self.session.state['ground_encounter'] or {}).get('phase')=='result'
        self.owner.result_play_button.configure(state='normal' if playable else 'disabled',
            text='Play animation' if not playable or value['paused'] else 'Pause animation')

    def sync(self):
        if self.session is not self.owner.app.session:
            self.cancel();self.session=self.owner.app.session
        value=self.session.result_animation
        if value is None or value['paused'] or (self.session.state['ground_encounter'] or {}).get('phase')!='result':self.cancel()
        elif self.timer is None:
            # Decode/cache every frame before starting the clock. The original
            # result initializer also prepares the atlas before its loop.
            encounter=self.session.state['ground_encounter']
            for frame in (1,2,3):self.owner.result_pixels.picture('ground',False,encounter['losses'],frame=frame)
            self.clock=RetraceClock(time.perf_counter_ns());self.schedule()
        self.controls()

    def toggle(self):
        value=self.session.result_animation
        if value is None or (self.session.state['ground_encounter'] or {}).get('phase')!='result':return
        if value['paused']:self.session.pause_result_animation(False);self.sync()
        else:self.pause()

    def schedule(self):
        if self.timer is None and self.clock is not None:
            self.timer=self.owner.window.after(self.clock.delay_ms(time.perf_counter_ns()),lambda:self.owner.app.guard(self.tick))

    def tick(self):
        self.timer=None
        if self.session is not self.owner.app.session:self.cancel();return
        value=self.session.result_animation
        if value is None or value['paused'] or (self.session.state['ground_encounter'] or {}).get('phase')!='result':self.cancel();return
        if self.owner.control_panel.busy or self.owner.fade.active:self.schedule();return
        try:
            if self.session.tick_result_animation():self.owner.draw_result()
            # Wait for the next reference edge after work, without catch-up
            # bursts or skipped logical calls when the host stalls.
            self.schedule()
        except Exception:
            self.pause();raise
