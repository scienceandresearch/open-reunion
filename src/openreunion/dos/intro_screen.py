"""Connected original intro player with isolated timing, input and RNG."""
from bisect import bisect_right
import time
from tkinter import ttk

from .assets import Picture
from .audio_output import AudioPlayer
from .credits_cinema import Shot as PaletteShot, shot_palette
from .intro_assets import PICTURE_PREFIXES
from .intro_cinema import LOW_PICTURES, TRACKS, timeline
from .intro_effects import flight_frame, scroll_frame, shake_frame, white_flash_dac
from .story_cinema import draw_frame
from .video_timing import RetraceClock


class IntroScreen:
    screen_name='intro'

    def __init__(self,app):
        self.app=app;self.owner=None;self.opened=False;self.running=False
        self.entries=();self.starts=();self.music_starts=();self.music_names=();self.duration=0
        self.position=0;self.elapsed=0;self.base_elapsed=0;self.wall_start=None
        self.timer=None;self.clock=None;self.generation=0;self.music=AudioPlayer();self.music_index=-1
        self.background_player=None;self.background_paused=True
        self.seed=time.perf_counter_ns()&0xffffffff;self.reset_render()

    @property
    def active(self):return self.opened and self.owner is self.app.session

    @property
    def done(self):return self.position>=len(self.entries)

    def reset_render(self):
        self.rendered_position=-1;self.picture=Picture(320,200,bytes(64000),bytes(768))
        self.palette=self.picture.palette;self.dac=bytes(768);self.loaded=None
        self.animation_call=None;self.animation_base=None;self.shake_call=None;self.shake_source=None
        self.scroll_call=None;self.scroll_base=None

    def prepare(self):
        for name in LOW_PICTURES:self.app.content.intro_picture(name)
        for prefix in PICTURE_PREFIXES:self.app.content.intro_high_resolution(prefix)
        from .intro_assets import FRAME_COUNTS
        for asset in FRAME_COUNTS:self.app.content.intro_animation(asset)

    def open(self):
        songs={name:self.app.content.intro_music(name) for name in TRACKS}
        film=timeline(songs,seed=self.seed);self.songs=songs
        self.prepare();self.leave();self.app.clock_panel.clock.pause()
        self.app.startup=None
        self.owner=self.app.session;self.opened=True;self.entries=tuple(shot for _,shot in film.entries)
        self.starts=tuple(start for start,_ in film.entries);self.duration=film.duration;self.seed=film.next_seed
        self.music_starts=tuple(start for start,_ in film.music);self.music_names=tuple(name for _,name in film.music)
        self.background_player=getattr(getattr(self.app,'music_panel',None),'player',None)
        if self.background_player is not None:
            self.background_paused=self.background_player.paused;self.background_player.pause(True)
        self.position=0;self.elapsed=0;self.reset_render()
        self.app.show_original('intro');self.play()

    def pause(self):
        if self.running:self.elapsed=min(self.duration,self.current_time())
        self.generation+=1;self.running=False;self.wall_start=None;self.clock=None
        if self.timer is not None:self.app.root.after_cancel(self.timer)
        self.timer=None
        if self.music.playing:self.music.pause(True)

    def close(self):
        self.pause();self.music.stop();self.music_index=-1

    def leave(self):
        self.close();self.opened=False
        player=getattr(getattr(self.app,'music_panel',None),'player',None)
        if self.background_player is not None and self.background_player is player and self.owner is self.app.session:
            self.background_player.pause(self.background_paused)
        self.background_player=None

    def sync(self):
        if self.opened and self.owner is not self.app.session:self.leave()
        return False

    def current_time(self):
        if self.running and self.music_index>=0 and not self.music.error:
            return max(self.elapsed,self.music_starts[self.music_index]+self.music.position()*1_000_000_000//48000)
        if self.running and self.wall_start is not None:
            return max(self.elapsed,self.base_elapsed+time.perf_counter_ns()-self.wall_start)
        return self.elapsed

    def select_music(self,elapsed,enabled):
        index=bisect_right(self.music_starts,elapsed)-1
        if not enabled:
            self.music.stop();self.music_index=-1;return
        if index!=self.music_index:
            self.music.stop();self.music_index=index
            offset=max(0,elapsed-self.music_starts[index])
            self.music.start(self.app.content.intro_music(self.music_names[index]),frames=offset*48000//1_000_000_000)

    def play(self):
        if not self.active or self.done or self.running:return
        enabled=bool(self.app.session.audio and self.app.session.audio['automatic'])
        self.select_music(self.elapsed,enabled)
        if enabled and self.music.playing:self.music.pause(False)
        self.base_elapsed=self.elapsed;self.wall_start=time.perf_counter_ns();self.running=True
        self.clock=RetraceClock(self.wall_start);self.schedule();self.app.render_original()

    def toggle(self):
        if self.running:self.pause();self.app.render_original()
        else:self.play()

    def replay(self):
        self.close()
        if hasattr(self,'songs'):
            film=timeline(self.songs,seed=self.seed);self.seed=film.next_seed
            self.entries=tuple(shot for _,shot in film.entries);self.starts=tuple(start for start,_ in film.entries)
            self.duration=film.duration;self.music_starts=tuple(start for start,_ in film.music)
            self.music_names=tuple(name for _,name in film.music)
        self.position=0;self.elapsed=0;self.reset_render();self.play()

    def input(self):
        """Original final input repeats; input during the film aborts to menu."""
        if self.done:self.replay()
        else:self.app.open_startup()

    def schedule(self):
        if self.running and self.timer is None:
            generation=self.generation
            self.timer=self.app.root.after(self.clock.delay_ms(time.perf_counter_ns()),
                lambda:self.app.guard(lambda:self.tick(generation)))

    def tick(self,generation):
        if generation!=self.generation:return
        self.timer=None
        if not self.running:return
        if self.owner is not self.app.session or self.app.screen!='intro' or not self.app.original.winfo_ismapped():
            self.pause();return
        self.elapsed=min(self.duration,self.current_time())
        self.position=bisect_right(self.starts,self.elapsed)-1
        enabled=bool(self.app.session.audio and self.app.session.audio['automatic'])
        self.select_music(self.elapsed,enabled)
        if self.elapsed>=self.duration:self.position=len(self.entries);self.close()
        self.app.render_original();self.schedule()

    def apply(self,shot):
        operation=shot.operation
        if operation:
            kind,*args=operation
            if kind=='picture':self.picture=self.app.content.intro_picture(args[0]);self.palette=self.picture.palette
            elif kind=='load':self.loaded=self.app.content.intro_picture(args[0])
            elif kind=='show_loaded':
                # This operation represents the original load-and-blit pair.
                # It must replace any older buffered picture (PAL1 remains
                # buffered after the BASE1 shake sequence).
                self.loaded=self.app.content.intro_picture(args[0])
                self.picture=self.loaded;self.palette=self.picture.palette
            elif kind=='highres':self.picture=self.app.content.intro_high_resolution(args[0]);self.palette=self.picture.palette
            elif kind=='animation':
                call,asset,frame,redraw,palette=args
                if call!=self.animation_call:
                    self.animation_call=call;self.animation_base=self.picture.pixels
                    if palette:self.palette=self.app.content.intro_picture(f'PAL{asset}').palette
                background=self.animation_base if redraw else self.picture.pixels
                pixels=draw_frame(self.app.content.intro_animation(asset),frame,background)
                self.picture=Picture(320,200,pixels,self.palette)
            elif kind=='shake':
                call,amplitude,x,y=args
                if call!=self.shake_call:self.shake_call=call;self.shake_source=self.picture.pixels
                pixels=shake_frame(self.picture.pixels,self.shake_source,amplitude,x,y)
                self.picture=Picture(320,200,pixels,self.palette)
            elif kind=='scroll':
                call,name,remaining=args
                incoming=self.app.content.intro_picture(name)
                if call!=self.scroll_call:self.scroll_call=call;self.scroll_base=self.picture.pixels
                pixels=scroll_frame(self.scroll_base,incoming.pixels,remaining)
                if remaining==0:self.palette=incoming.palette
                self.picture=Picture(320,200,pixels,self.palette)
            elif kind=='flight':
                _,frame,reduced=args
                stars=self.app.content.intro_picture('STARS');planet=self.app.content.intro_picture('PLANET2' if reduced else 'PLANET')
                ship=None if reduced else self.app.content.intro_picture('SHIP')
                self.palette=(planet if reduced else ship).palette
                self.picture=Picture(320,200,flight_frame(stars.pixels,planet.pixels,None if ship is None else ship.pixels,frame),self.palette)
            else:raise AssertionError('Unknown intro visual operation: '+kind)
        base=bytes(value>>2 for value in self.palette)
        if shot.flash>=0:
            self.dac=white_flash_dac(self.dac,base,shot.flash)
            palette=bytes(value*255//63 for value in self.dac)
        else:
            palette=shot_palette(self.palette,PaletteShot(level=shot.level,divisor=shot.divisor,white=shot.white))
            self.dac=bytes(round(value*63/255) for value in palette)
        self.picture=Picture(self.picture.width,self.picture.height,self.picture.pixels,palette)

    def draw(self):
        target=min(self.position,len(self.entries)-1)
        if target<self.rendered_position:self.reset_render()
        for index in range(self.rendered_position+1,target+1):self.apply(self.entries[index])
        self.rendered_position=target
        return self.picture


class IntroBar(ttk.Frame):
    def __init__(self,app):
        super().__init__(app.root);self.app=app;self.view=app.intro_view
        self.play=ttk.Button(self,text='Pause (Space)',command=lambda:app.guard(self.view.toggle));self.play.pack(side='left')
        ttk.Button(self,text='Replay',command=lambda:app.guard(self.view.replay)).pack(side='left',padx=3)
        ttk.Button(self,text='Back (Esc)',command=lambda:app.guard(app.open_startup)).pack(side='left',padx=3)
        self.status=ttk.Label(self);self.status.pack(side='left',padx=8)

    def sync(self):
        self.play.configure(text='Pause (Space)' if self.view.running else 'Play (Space)',state='disabled' if self.view.done else 'normal')
        text='Intro complete — press Replay to repeat' if self.view.done else 'Original intro' if self.view.running else 'Original intro paused'
        if self.view.music.error:text+=' | Music unavailable: '+self.view.music.error
        self.status.configure(text=text)
