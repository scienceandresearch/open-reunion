"""Original launch/landing drawing operations, in retrace order.

Presentation only: the orbit command owns validation and campaign changes.
"""
from bisect import bisect_right
from dataclasses import dataclass
import time
from .assets import Picture
from .cockpit_screen import instrument_copies
from .sample_output import SamplePlayer
from .video_timing import FRAME_DOTS,PIXEL_CLOCK_HZ


def transition(landing):
    events=[]
    def emit(*event):events.append(event)
    def fade(first,last,level):emit('fade',first,last,level)
    emit('sound','landing' if landing else 'launch')
    emit('load','space' if landing else 'terrain')
    emit('lever',2)
    for y in (range(1,44) if landing else range(43,-1,-1)):
        if y==(3 if landing else 41):emit('lever',3)
        if y==(5 if landing else 38):emit('lever',4)
        emit('wait',1)
        progress=y if landing else 43-y
        if progress>28:fade(128,239,43-progress)
        if progress>41:fade(64,127,56-progress)
        emit('window',y)
    emit('load','terrain' if landing else 'space')
    emit('wait',20)
    emit('window',0 if landing else 44)
    for y in (range(1,44) if landing else range(43,10,-1)):
        emit('wait',1)
        progress=y if landing else 43-y
        if progress<=15:fade(128,239,progress)
        if progress<=2:fade(64,127,progress+13)
        emit('window',y)
    if landing:
        emit('lever',3)
        for y,lever in ((42,None),(41,2),(42,None),(43,1),(42,None),(43,None)):
            emit('wait',1)
            if lever is not None:emit('lever',lever)
            emit('window',y)
    else:
        for wait,y,lever in ((2,10,None),(1,9,None),(2,8,None),(1,7,3),
                             (2,6,2),(2,5,1),(2,4,None),(3,3,None),(3,2,None),(4,1,None)):
            emit('wait',wait);emit('window',y)
            if lever is not None:emit('lever',lever)
    return tuple(events)


def lever_copy(frame):
    return (1+48*(frame-1),73,47,43),(15,157)


def route_lever_copy(frame):
    return (1+22*(frame-1),32,21,39),(151,161)


def route_sequence(reverse=False):
    return tuple((frame,3) for frame in (range(4,0,-1) if reverse else range(1,5)))


def white_palette(source,current,first,last,level):
    """3560A..35705: six-bit DAC channels, preserving the untouched range."""
    result=bytearray(current)
    for i in range(first*3,(last+1)*3):result[i]=63-(63-source[i])*level//15
    return bytes(result)


@dataclass(frozen=True)
class Shot:
    texture:str
    row:int
    lever:int=1
    sky_level:int=15
    cockpit_level:int=15


def timeline(landing):
    texture='space' if landing else 'terrain';pending=texture
    row=0 if landing else 43;lever=1;sky=15;cockpit=15;at=0;frames=[]
    for event in transition(landing):
        kind=event[0]
        if kind=='load':pending=event[1]
        elif kind=='window':texture=pending;row=event[1]
        elif kind=='lever':lever=event[1]
        elif kind=='fade':
            if event[1]==128:sky=event[3]
            else:cockpit=event[3]
        elif kind=='wait':
            frames.append((at,Shot(texture,row,lever,sky,cockpit)));at+=event[1]
    return tuple(frames),at


def faded(picture,level):
    if level==15:return picture
    palette=bytes((63-(63-(v>>2))*level//15)*4 for v in picture.palette)
    return Picture(picture.width,picture.height,picture.pixels,palette)


class CockpitCinema:
    def __init__(self,app):
        self.app=app;self.frames=();self.timer=None;self.audio_timer=None;self.owner=None
        self.player=SamplePlayer();self.background=None;self.cache={}
        self.mode='flight';self.on_complete=None;self.handoff=False

    @property
    def running(self):return bool(self.frames)

    def prepare(self,landing):
        app=self.app;row=app.selected_cockpit_fleet();wid=app.cockpit_view.world_id(app.session.state)
        raw=app.session.state['worlds'][wid]['raw'];terrain=raw[21] if 1<=raw[21]<=12 else 0
        if wid=='1:7:0' and raw[0] not in (1,2):terrain=12
        renderer=app.screen_renderer
        assets={key:renderer.path_asset(path) for key,path in (
            ('terrain',f'PLANETS/NAGY{terrain}.PIC'),('space','PLANETS/NAGY0.PIC'),
            ('cockpit','PLANETS/MUSZI.PIC'),('instruments','PLANETS/MUSZIANM.PIC'))}
        enabled=app.session.effects is None or app.session.effects['enabled']
        sample=app.content.sample('LANDING' if landing else 'LAUNCH') if enabled else None
        return assets,sample

    def start(self,index,landing,prepared,callback=None):
        navigation=getattr(self.app,'navigation_sound',None)
        if navigation is not None:navigation.cancel()
        self.cancel()
        if self.app.screen!='cockpit':return
        self.mode='flight';self.on_complete=callback
        self.owner=self.app.session;self.index=index;self.assets,sample=prepared;self.cache={}
        self.base=bytes(self.app.screen_renderer.frame(self.app.session.state,'PLANETS/MUSZI.PIC',17,
            self.app.menu_page,self.app.caption or 'CONTROL PANEL',
            buttons=self.app.cockpit_view.buttons(self.app.session.state,self.app.catalog)).rgb)
        entries,self.duration=timeline(landing)
        self.starts=tuple(t for t,_ in entries);self.frames=tuple(s for _,s in entries);self.position=0
        self.app.clock_panel.clock.pause();self.app.stop_model_timer()
        self.start_sound(sample)
        self.origin=time.perf_counter_ns();self.tick()

    def start_sound(self,sample):
        if sample is not None:
            self.background=self.app.effects.player;self.background_paused=self.background.paused
            self.background.pause(True);self.player.start(sample)

    def start_route(self,index,callback):
        navigation=getattr(self.app,'navigation_sound',None)
        if navigation is not None:navigation.cancel()
        self.cancel();app=self.app
        if app.screen!='cockpit':return
        instruments=app.screen_renderer.path_asset('PLANETS/MUSZIANM.PIC')
        enabled=app.session.effects is None or app.session.effects['enabled']
        sample=app.content.sample('CONTROLL') if enabled else None
        self.mode='route';self.owner=app.session;self.index=index;self.on_complete=callback
        self.assets={'instruments':instruments}
        self.base=bytes(app.screen_renderer.cockpit(app.session.state,app.cockpit_view,
            app.caption or 'CONTROL PANEL',app.menu_page).rgb)
        at=0;starts=[];frames=[]
        for frame,wait in route_sequence():starts.append(at);frames.append(frame);at+=wait
        self.starts=tuple(starts);self.frames=tuple(frames);self.duration=at;self.position=0
        app.clock_panel.clock.pause();app.stop_model_timer();self.start_sound(sample)
        self.origin=time.perf_counter_ns();self.tick()

    def cancel(self):
        if self.timer is not None:self.app.root.after_cancel(self.timer);self.timer=None
        if self.audio_timer is not None:self.app.root.after_cancel(self.audio_timer);self.audio_timer=None
        self.player.stop()
        if self.background is not None and self.owner is self.app.session and self.background is self.app.effects.player:
            self.background.pause(self.background_paused)
        self.background=None;self.owner=None;self.frames=();self.cache={}
        self.on_complete=None;self.handoff=False

    def tick(self):
        self.timer=None
        if not self.running:return
        if self.owner is not self.app.session or self.app.screen!='cockpit' or self.app.cockpit_view.index!=self.index:
            self.cancel();return
        elapsed=(time.perf_counter_ns()-self.origin)*PIXEL_CLOCK_HZ/(FRAME_DOTS*1_000_000_000)
        if elapsed>=self.duration:
            self.frames=();self.cache={}
            if self.mode=='flight' and self.on_complete is not None:
                # A landing discovery follows the complete transition/sample.
                # Cancellation or loading another session discards this callback.
                self.app.render_original();self.finish_audio();return
            callback=self.on_complete;self.on_complete=None
            if callback is not None:
                self.handoff=True
                try:self.app.guard(callback)
                finally:self.handoff=False
            else:self.app.render_original()
            if self.owner is not None:self.finish_audio()
            return
        self.position=max(0,bisect_right(self.starts,elapsed)-1)
        self.app.render_original();self.timer=self.app.root.after(10,self.tick)

    def finish_audio(self):
        self.audio_timer=None
        screens=('cockpit','starmap') if self.mode=='route' else ('cockpit',)
        if self.owner is not self.app.session or self.app.screen not in screens:self.cancel();return
        if self.player.error:self.app.status.set('Sound effect unavailable: '+self.player.error)
        if self.player.playing and not self.player.completed:
            self.audio_timer=self.app.root.after(25,self.finish_audio)
        else:
            callback=self.on_complete if self.mode=='flight' else None
            self.cancel()
            if callback is not None:self.app.guard(callback)

    def draw(self,renderer,target):
        if not self.running:return
        if self.mode=='route':
            source,(x,y)=route_lever_copy(self.frames[self.position])
            target.blit(self.assets['instruments'],x,y,source=source)
            return
        shot=self.frames[self.position]
        def asset(name,level):
            key=name,level
            if key not in self.cache:self.cache[key]=faded(self.assets[name],level)
            return self.cache[key]
        cockpit=asset('cockpit',shot.cockpit_level);sky=asset(shot.texture,shot.sky_level)
        colors=[cockpit.palette[i*3:i*3+3] for i in range(256)]
        sky_colors=[sky.palette[i*3:i*3+3] for i in range(256)]
        pixels=b''.join(sky_colors[sky.pixels[shot.row*320+i]] if value==64 else colors[value]
                        for i,value in enumerate(cockpit.pixels))
        target.rgb[49*320*3:]=pixels
        instruments=asset('instruments',shot.cockpit_level)
        for (x,y),(sx,sy,w,h) in instrument_copies(self.app.cockpit_view):
            target.blit(instruments,x,y,source=(sx,sy,w,min(h,200-y)))
        source,(x,y)=lever_copy(shot.lever);target.blit(instruments,x,y,source=source)

    def frame(self):
        from .original_screen import ScreenPixels
        target=ScreenPixels();target.rgb[:]=self.base
        self.draw(self.app.screen_renderer,target)
        return target
