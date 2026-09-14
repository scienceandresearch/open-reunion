"""Original victory film with audio-synchronized visuals and terminal controls."""
from bisect import bisect_right
import time
from .assets import Picture
from .defeat_screen import DefeatScreen
from .video_timing import RetraceClock
from .victory_cinema import timeline,PICTURES


class VictoryScreen(DefeatScreen):
    screen_name='victory'
    def __init__(self,app):
        self.elapsed=0;self.duration=0;self.starts=();self.wall_start=None;self.base_elapsed=0
        super().__init__(app)

    @property
    def active(self):
        state=self.app.session.state
        return (state['campaign_phase']=='victory' and not state['presentation_requests']
            and state['active_scene'] is None and state['active_dialog'] is None
            and not any((state[key] or {}).get('phase','closed')!='closed' for key in ('space_encounter','ground_encounter')))

    def current_time(self):
        if self.music_started and not self.music.error:
            return max(self.elapsed,self.music.position()*1_000_000_000//48000)
        return max(self.elapsed,self.base_elapsed+time.perf_counter_ns()-self.wall_start) if self.wall_start is not None else self.elapsed

    def pause(self):
        if self.running:self.elapsed=min(self.duration,self.current_time())
        super().pause();self.wall_start=None

    def sync(self):
        same=self.owner is self.app.session;ready=self.active;autoplay=same and ready and not self.ready
        context=(self.app.session,) if ready else None
        if not same or context!=self.context:
            self.close();self.context=context;self.position=0;self.elapsed=0;self.cache={}
            entries,self.duration=timeline(self.app.content.module_music('ENDSEQ')) if ready else ((),0)
            self.starts=tuple(start for start,shot in entries);self.frames=tuple(shot for start,shot in entries)
            self.app.pointer.cancel(reset=True)
        self.owner=self.app.session;self.ready=ready
        if ready and self.app.session.audio and self.app.session.audio['track']:self.app.music_panel.pause(True)
        return autoplay

    def draw(self):
        if self.done:return self.app.content.victory_picture('TX1')
        shot=self.frames[self.position];key=(shot.picture,shot.animation,shot.scroll)
        if key not in self.cache:
            if shot.scroll>=0:
                if 'credits' not in self.cache:
                    self.cache['credits']=bytes(64000)+b''.join(self.app.content.victory_picture(name).pixels for name in ('CR1','CR2','CR3'))+bytes(64000)
                palette=self.app.content.victory_picture('CR1').palette
                pixels=self.cache['credits'][shot.scroll*320:shot.scroll*320+64000]
                picture=Picture(320,200,pixels,palette)
            elif shot.animation:picture=self.app.content.victory_animation(shot.animation)
            elif shot.picture:picture=self.app.content.victory_picture(shot.picture)
            else:picture=Picture(320,200,bytes(64000),bytes(768))
            if len(self.cache)>32:self.cache={k:v for k,v in self.cache.items() if k=='credits'}
            self.cache[key]=picture
        picture=self.cache[key]
        palette=bytes((63-(63-(value>>2))*shot.level//shot.divisor if shot.white else
                       (value>>2)*shot.level//shot.divisor)*255//63 for value in picture.palette)
        return Picture(320,200,picture.pixels,palette)

    def play(self):
        if not self.active or self.done or self.running:return
        # Bound preparation before starting either clock.
        for name in PICTURES:self.app.content.victory_picture(name)
        for index in range(1,17):self.app.content.victory_animation(index)
        enabled=bool(self.app.session.audio and self.app.session.audio['automatic'])
        if enabled:
            if not self.music_started:
                self.music.start(self.app.content.module_music('ENDSEQ'),frames=self.elapsed*48000//1_000_000_000)
                self.music_started=True
            else:self.music.pause(False)
        else:self.music.stop();self.music_started=False
        self.base_elapsed=self.elapsed;self.wall_start=time.perf_counter_ns()
        self.running=True;self.clock=RetraceClock(self.wall_start);self.schedule();self.app.render_original()

    def replay(self):
        self.close();self.position=0;self.elapsed=0;self.play()

    def step(self):
        # Deterministic offline presentation stepping for verification.
        self.close()
        if self.active and not self.done:self.position+=1
        self.elapsed=self.duration if self.done else self.starts[self.position]

    def tick(self,generation):
        if generation!=self.generation:return
        self.timer=None
        if not self.running:return
        if self.owner is not self.app.session or self.app.screen!=self.screen_name or not self.app.original.winfo_ismapped():self.pause();return
        self.elapsed=min(self.duration,self.current_time())
        self.position=len(self.frames) if self.elapsed>=self.duration else max(0,bisect_right(self.starts,self.elapsed)-1)
        if self.done:self.close()
        self.app.render_original();self.schedule()
