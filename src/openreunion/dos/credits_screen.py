"""Optional original Game Credits playback, isolated from campaign progression."""
import time
from tkinter import ttk
from .assets import Picture
from .credits_assets import ASSETS,displayed_frames
from .credits_cinema import PICTURES,Shot,timeline,shot_palette
from .victory_screen import VictoryScreen
from .video_timing import RetraceClock


class CreditsScreen(VictoryScreen):
    screen_name='credits'

    def __init__(self,app):
        self.opened=False;self.background_player=None;self.background_paused=True
        super().__init__(app)

    @property
    def active(self):return self.opened and self.owner is self.app.session

    def open(self):
        entries,duration=timeline(self.app.content.module_music('STEAL2'))
        self.prepare()
        self.leave();self.app.clock_panel.clock.pause()
        self.owner=self.app.session;self.opened=True;self.position=0;self.elapsed=0;self.cache={}
        self.duration=duration
        self.starts=tuple(t for t,_ in entries);self.frames=tuple(s for _,s in entries)
        self.background_player=self.app.music_panel.player
        self.background_paused=self.background_player.paused
        self.background_player.pause(True)
        self.app.show_original('credits');self.play()

    def leave(self):
        self.close()
        if self.opened and self.owner is self.app.session and self.background_player is self.app.music_panel.player:
            self.background_player.pause(self.background_paused)
        self.background_player=None;self.opened=False

    def sync(self):
        if self.opened and self.owner is not self.app.session:self.leave()
        return False

    def draw(self):
        if self.done:
            picture=self.app.content.credits_picture('PAL10')
            return Picture(picture.width,picture.height,picture.pixels,shot_palette(picture.palette,Shot()))
        shot=self.frames[self.position];key=(shot.picture,shot.asset,shot.frame)
        if key not in self.cache:
            picture=(self.app.content.credits_animation(shot.asset,shot.frame) if shot.asset else
                     self.app.content.credits_picture(shot.picture) if shot.picture else
                     Picture(320,200,bytes(64000),bytes(768)))
            if len(self.cache)>32:self.cache.clear()
            self.cache[key]=picture
        picture=self.cache[key]
        palette=shot_palette(picture.palette,shot)
        if shot.picture=='PRESENTS':palette=bytes(3)+palette[3:]
        return Picture(picture.width,picture.height,picture.pixels,palette)

    def prepare(self):
        for name in PICTURES:self.app.content.credits_picture(name)
        for asset in ASSETS:
            for frame in displayed_frames(asset):self.app.content.credits_animation(asset,frame)

    def play(self):
        if not self.active or self.done or self.running:return
        enabled=bool(self.app.session.audio and self.app.session.audio['automatic'])
        if enabled:
            if not self.music_started:
                self.music.start(self.app.content.module_music('STEAL2'),frames=self.elapsed*48000//1_000_000_000)
                self.music_started=True
            else:self.music.pause(False)
        else:self.music.stop();self.music_started=False
        self.base_elapsed=self.elapsed;self.wall_start=time.perf_counter_ns();self.running=True
        self.clock=RetraceClock(self.wall_start);self.schedule();self.app.render_original()


class CreditsBar(ttk.Frame):
    def __init__(self,app):
        super().__init__(app.root);self.app=app;self.view=app.credits_view
        self.play=ttk.Button(self,text='Pause (Space)',command=lambda:app.guard(self.view.toggle));self.play.pack(side='left')
        ttk.Button(self,text='Replay',command=lambda:app.guard(self.view.replay)).pack(side='left',padx=3)
        ttk.Button(self,text='Back (Esc)',command=lambda:app.guard(app.show_original)).pack(side='left',padx=3)
        self.status=ttk.Label(self);self.status.pack(side='left',padx=8)

    def sync(self):
        self.play.configure(text='Pause (Space)' if self.view.running else 'Play (Space)',state='disabled' if self.view.done else 'normal')
        text='Credits complete' if self.view.done else 'Game Credits' if self.view.running else 'Game Credits paused'
        if self.view.music.error:text+=' | Music unavailable: '+self.view.music.error
        self.status.configure(text=text)
