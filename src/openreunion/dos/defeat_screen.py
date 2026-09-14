"""Main-screen loss cinematic and a usable terminal campaign screen."""
import time
from tkinter import ttk
from .defeat_cinema import film,defeat_cause
from .video_timing import RetraceClock
from .assets import Picture
from .audio_output import AudioPlayer


class DefeatScreen:
    def __init__(self,app):
        self.app=app;self.owner=None;self.ready=False;self.context=None
        self.frames=();self.position=0;self.running=False;self.timer=None;self.clock=None;self.generation=0
        self.cache={}
        self.music=AudioPlayer();self.music_started=False

    @property
    def active(self):
        state=self.app.session.state
        return (state['campaign_phase']!='victory' and self.app.session.defeated()
                and not state['presentation_requests'] and state['active_scene'] is None and state['active_dialog'] is None
                and not any((state[key] or {}).get('phase','closed')!='closed' for key in ('space_encounter','ground_encounter')))

    @property
    def done(self):return self.position>=len(self.frames)

    def pause(self):
        self.generation+=1;self.running=False;self.clock=None
        if self.timer is not None:self.app.root.after_cancel(self.timer)
        self.timer=None
        if self.music.playing:self.music.pause(True)

    def close(self):
        self.pause();self.music.stop();self.music_started=False

    def sync(self):
        same=self.owner is self.app.session;ready=self.active;autoplay=same and ready and not self.ready
        context=(self.app.session,self.app.hero,defeat_cause(self.app.session.state)) if ready else None
        if not same or context!=self.context:
            self.close();self.context=context;self.position=0;self.cache={}
            self.frames=film(context[1],context[2]) if ready else ()
            self.app.pointer.cancel(reset=True)
        self.owner=self.app.session;self.ready=ready
        if ready and self.app.session.audio and self.app.session.audio['track']:
            # The separate ending player uses the complete original module.
            # Preserve the regular player's saved track and user preferences.
            self.app.music_panel.pause(True)
        return autoplay

    def draw(self):
        if self.done:
            source=self.app.screen_renderer.asset(f'DEATHSZ{self.context[2]}')
            return Picture(320,200,source.pixels[:64000],source.palette)
        frame=self.frames[self.position];key=(frame.picture,frame.asset,frame.step)
        if key not in self.cache:
            picture=(self.app.content.defeat_animation(frame.asset,frame.step) if frame.asset else
                     self.app.screen_renderer.asset(frame.picture))
            if len(self.cache)>8:self.cache.clear()
            self.cache[key]=Picture(320,200,picture.pixels[:64000],picture.palette)
        picture=self.cache[key]
        # The original scales six-bit DAC entries using integer division.
        palette=bytes(((value>>2)*frame.level//frame.divisor)*255//63 for value in picture.palette)
        return Picture(320,200,picture.pixels,palette)

    def play(self):
        if not self.active or self.done or self.running:return
        # Decode before the clock starts; every exported frame is bounded.
        self.app.content.defeat_animation(16,1)
        if self.app.hero==2:self.app.content.defeat_animation(15,1)
        enabled=bool(self.app.session.audio and self.app.session.audio['automatic'])
        if enabled:
            if not self.music_started:
                self.music.start(self.app.content.module_music('FAILURE'));self.music_started=True
            else:self.music.pause(False)
        else:self.music.stop();self.music_started=False
        self.running=True;self.clock=RetraceClock(time.perf_counter_ns());self.schedule();self.app.render_original()

    def toggle(self):
        if self.running:self.pause();self.app.render_original()
        else:self.play()

    def replay(self):
        self.close();self.position=0;self.play()

    def schedule(self):
        if self.running and self.timer is None:
            generation=self.generation
            self.timer=self.app.root.after(self.clock.delay_ms(time.perf_counter_ns()),lambda:self.app.guard(lambda:self.tick(generation)))

    def step(self):
        if self.active and not self.done:self.position+=1
        if self.done:self.close()

    def tick(self,generation):
        if generation!=self.generation:return
        self.timer=None
        if not self.running:return
        if self.owner is not self.app.session or self.app.screen!='defeat' or not self.app.original.winfo_ismapped():self.pause();return
        self.step();self.app.render_original();self.schedule()


class DefeatBar(ttk.Frame):
    def __init__(self,app,*,view=None,title='Defeat cinematic'):
        super().__init__(app.root);self.app=app;self.view=view if view is not None else app.defeat_view;self.title=title
        self.play=ttk.Button(self,text='Play (Space)',command=lambda:app.guard(self.view.toggle));self.play.pack(side='left')
        for text,callback in (('Replay',self.view.replay),('Main menu (F10)',app.open_startup),('Save result',app.save),('Load',app.load)):
            ttk.Button(self,text=text,command=lambda fn=callback:app.guard(fn)).pack(side='left',padx=3)
        self.status=ttk.Label(self);self.status.pack(side='left',padx=8)

    def sync(self):
        self.play.configure(text='Pause (Space)' if self.view.running else 'Play (Space)',state='disabled' if self.view.done else 'normal')
        text='Campaign ended - load or start a new game' if self.view.done else self.title if self.view.running else self.title+' paused'
        if self.view.music.error:text+=' | Music unavailable: '+self.view.music.error
        self.status.configure(text=text)
