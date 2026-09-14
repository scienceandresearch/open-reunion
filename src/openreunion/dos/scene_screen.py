"""Main-canvas cinematic playback over the existing scene transactions."""
from copy import deepcopy
import textwrap
import time
from tkinter import ttk
from .scene_display import render_scene,draw_display,fade_display,finish_display
from .video_timing import RetraceClock


class SceneScreen:
    def __init__(self,app):
        self.app=app;self.context=None;self.snapshot=None;self.display=None
        self.running=False;self.timer=None;self.clock=None;self.generation=0
        self.mouse=False;self.key_pending=False;self.offset=0

    @property
    def active(self):
        state=self.app.session.state
        if state['active_scene'] is not None:return True
        if state['active_dialog'] is not None:return False
        if any((state[key] or {}).get('phase','closed')!='closed' for key in ('space_encounter','ground_encounter')):return False
        queue=state['presentation_requests']
        return bool(queue and queue[0]['kind'] in ('message','civilization_destroyed','report'))

    @property
    def playable(self):
        current=self.app.session.state['active_scene']
        return current is not None and current['notice'] is None and current['playback']['phase']!='done'

    def clear_input(self):self.mouse=False;self.key_pending=False

    def pause(self):
        self.generation+=1;self.running=False;self.clock=None;self.clear_input()
        if self.timer is not None:self.app.root.after_cancel(self.timer)
        self.timer=None
        if self.context is not None and self.context[0] is self.app.session and self.playable:self.app.effects.pause()
        if getattr(self.app,'scene_bar',None) is not None:self.app.scene_bar.sync()

    def sync(self):
        state=self.app.session.state;current=state['active_scene']
        queue=state['presentation_requests']
        context=(self.app.session,self.app.session.scene_revision,
                 current['notice'] if current else None,
                 tuple((r['kind'],r['id'],tuple(r.get('report',[]))) for r in queue) if current is None else None)
        if context!=self.context:
            self.pause();self.context=context;self.offset=0;self.snapshot=None
            self.app.pointer.cancel(reset=True)
        playback=current['playback'] if current else None
        if playback!=self.snapshot:
            # Full-frame cinematics replace the RGB campaign view. The palette
            # envelope uses a black prior display, also for loaded scenes.
            self.display=render_scene(self.app.content,playback,pixels=bytes(64000),palette=bytes(768)) if playback else None
            self.snapshot=deepcopy(playback)
        if not self.playable:self.pause()

    def lines(self):
        state=self.app.session.state;current=state['active_scene']
        if current is not None:
            notice=current['notice']
            text=self.app.event_text['message'][notice-1] if notice is not None else ''
        else:
            request=state['presentation_requests'][0]
            text=('' if request['kind']=='report' else self.app.event_text['message'][request['id']-1] if request['kind']=='message' else
                  self.app.catalog['alien_names'][request['id']-2]+' has been defeated.')
            from .mission_messages import append_report_text
            text=append_report_text(text.replace('|','\n'),request)
        return [line for paragraph in text.replace('|','\n').split('\n') for line in (textwrap.wrap(paragraph,width=50) or [''])]

    @property
    def notice(self):
        current=self.app.session.state['active_scene']
        return self.active and (current is None or current['notice'] is not None)

    def draw(self):
        if not self.notice:return self.display.picture()
        renderer=self.app.screen_renderer
        target=renderer.frame(self.app.session.state,'UZENET',11,0,'CAMPAIGN MESSAGE',buttons=[65])
        for i,line in enumerate(self.lines()[self.offset:self.offset+17]):renderer.text(target,line,8,55+8*i,columns=50)
        return target

    def scroll(self,lines):
        if self.notice:
            self.offset=max(0,min(max(0,len(self.lines())-17),self.offset+lines))
            self.app.pointer.cancel(reset=True);self.app.render_original()

    def play(self):
        if not self.playable or self.running:return
        self.app.content.prepare_story_scene(self.app.session.state['active_scene']['playback']['scene'])
        self.running=True;self.clock=RetraceClock(time.perf_counter_ns());self.app.effects.resume()
        self.app.original.focus_set();self.schedule();self.app.render_original()

    def toggle(self):
        if self.running:self.pause();self.app.render_original()
        else:self.play()

    def schedule(self):
        if self.running and self.timer is None:
            generation=self.generation
            self.timer=self.app.root.after(self.clock.delay_ms(time.perf_counter_ns()),lambda:self.app.guard(lambda:self.tick(generation)))

    def tick(self,generation):
        if generation!=self.generation:return
        self.timer=None
        if not self.running:return
        if self.context[0] is not self.app.session or self.context[1]!=self.app.session.scene_revision or self.app.screen!='scene' or not self.app.original.winfo_ismapped():
            self.pause();return
        events=self.app.session.apply('scene_tick',mouse=self.mouse,key=self.key_pending)
        self.app.effects.sync();current=self.app.session.state['active_scene'];state=current['playback']
        if state['key_seen']:self.key_pending=False
        for event in events:
            if event[0]=='fade':self.display=fade_display(self.display,event[1])
            elif event[0]=='frame':
                _,asset,frame,offset=event
                self.display=draw_display(self.display,self.app.content.story_animation(asset,frame),x=offset%320,y=offset//320)
            elif event[0]=='done':self.display=finish_display(self.display)
        self.snapshot=deepcopy(state)
        if state['phase']=='done':self.pause()
        self.app.render_original();self.schedule()

    def acknowledge(self):
        if not self.active or self.playable:return
        self.pause()
        self.app.act('scene_acknowledge' if self.app.session.state['active_scene'] is not None else 'dismiss_presentation')


class SceneBar(ttk.Frame):
    def __init__(self,app):
        super().__init__(app.root);self.app=app;self.view=app.scene_view
        self.play=ttk.Button(self,text='Play (P)',command=lambda:app.guard(self.view.toggle));self.play.pack(side='left')
        self.next=ttk.Button(self,text='Continue',command=lambda:app.guard(self.view.acknowledge));self.next.pack(side='left')
        for name,callback in (('Save',app.save),('Load',app.load)):
            ttk.Button(self,text=name,command=lambda fn=callback:app.guard(fn)).pack(side='left',padx=(6,0))
        self.status=ttk.Label(self);self.status.pack(side='left',padx=8)

    def sync(self):
        view=self.view
        self.play.configure(text='Pause (P)' if view.running else 'Play (P)',state='normal' if view.playable else 'disabled')
        self.next.configure(state='normal' if view.active and not view.playable else 'disabled')
        text='Click picture / Space at input waits' if view.running else 'Scene paused' if view.playable else 'Continue when ready'
        if view.notice and len(view.lines())>17:
            text+=f' | Scroll: lines {view.offset+1}-{min(view.offset+17,len(view.lines()))} of {len(view.lines())}'
        self.status.configure(text=text)
