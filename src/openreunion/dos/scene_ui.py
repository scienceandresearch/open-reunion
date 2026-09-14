"""Cancellable desktop playback for transactional story scenes and notices."""
import time
import tkinter as tk
from tkinter import ttk
from .scene_display import render_scene,draw_display,fade_display,finish_display

from .video_timing import RetraceClock,RETRACE_HZ


class SceneWindow:
    def __init__(self,app):
        self.app=app;self.timer=None;self.paused=True;self.mouse=False;self.key_pending=False
        self.context=None;self.display=None;self.image=None;self.clock=None
        self.window=tk.Toplevel(app.root);self.window.title('Story')
        self.window.geometry('700x640');self.window.minsize(680,610)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        body=ttk.Frame(self.window,padding=14);body.pack(fill='both',expand=True)
        self.caption=tk.StringVar();ttk.Label(body,textvariable=self.caption,font=('Segoe UI',14,'bold')).pack(anchor='w')
        self.sound=app.sound
        ttk.Checkbutton(body,text='Sound effects',variable=self.sound,
                        command=lambda:app.guard(app.set_sound)).pack(anchor='w')
        self.canvas=tk.Canvas(body,width=640,height=400,background='black',highlightthickness=0,takefocus=True)
        self.canvas.pack(pady=10)
        self.item=self.canvas.create_image(0,0,anchor='nw')
        self.notice=ttk.Label(body,wraplength=640,justify='left');self.notice.pack(fill='x',pady=8)
        self.message=tk.StringVar();ttk.Label(body,textvariable=self.message,wraplength=640).pack(fill='x',pady=5)
        controls=ttk.Frame(body);controls.pack(fill='x')
        self.play_button=ttk.Button(controls,text='Play',command=lambda:app.guard(self.play));self.play_button.pack(side='left',padx=3)
        self.pause_button=ttk.Button(controls,text='Pause',command=self.pause);self.pause_button.pack(side='left',padx=3)
        self.next_button=ttk.Button(controls,text='Continue',command=lambda:app.guard(self.continue_story));self.next_button.pack(side='left',padx=3)
        for label,fn in (('Save session',app.save),('Load session',app.load),('Close',self.close)):
            ttk.Button(controls,text=label,command=lambda f=fn:app.guard(f)).pack(side='left',padx=3)
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.window.bind('<ButtonRelease-1>',lambda _:setattr(self,'mouse',False),add='+')
        self.canvas.bind('<KeyPress>',lambda _:setattr(self,'key_pending',True))
        self.window.bind('<Destroy>',self.destroyed,add='+')
        app.watch_session(self.window,self.refresh);self.refresh()

    def press(self,event):self.mouse=True;self.canvas.focus_set()

    def pause(self):
        self.paused=True
        current=self.app.session.state['active_scene']
        if current is not None and current['playback']['phase']!='done':self.app.effects.pause()
        if self.timer is not None:
            self.window.after_cancel(self.timer);self.timer=None
        if self.window.winfo_exists():self.message.set('Paused. Use Play to resume.');self.update_controls()

    def close(self):self.pause();self.window.destroy()

    def destroyed(self,event):
        if event.widget==self.window:
            current=self.app.session.state['active_scene']
            if current is not None and current['playback']['phase']!='done':self.app.effects.suspend()
            if self.timer is not None:
                try:self.window.after_cancel(self.timer)
                except tk.TclError:pass
                self.timer=None
            if self.app.scene_window is self:self.app.scene_window=None

    def refresh(self):
        self.sound.set((self.app.session.effects or {'enabled':True})['enabled'])
        current=self.app.session.state['active_scene'];queue=self.app.session.state['presentation_requests']
        if current is None and (not queue or queue[0]['kind'] not in ('message','civilization_destroyed','report')):
            self.close();return
        context=(id(self.app.session),self.app.session.scene_revision)
        if context!=self.context:
            self.pause();self.context=context;self.mouse=False;self.key_pending=False
        if current is not None:
            state=current['playback'];self.caption.set('Incoming transmission' if current['dialog'] is not None else 'Story')
            # A standalone native scene window has a black prior display;
            # campaign UI redraw happens when the window closes.
            self.display=render_scene(self.app.content,state,pixels=bytes(64000),palette=bytes(768))
            self.draw();notice=current['notice']
        else:
            self.pause();self.caption.set('Campaign message');notice=queue[0]['id'] if queue[0]['kind']=='message' else None
            self.canvas.itemconfigure(self.item,image='')
        text=self.app.event_text['message'][notice-1].replace('|','\n') if notice is not None else ''
        if current is None and queue[0]['kind']=='civilization_destroyed':
            text=self.app.catalog['alien_names'][queue[0]['id']-2]+' has been defeated.'
        if current is None:
            from .mission_messages import append_report_text
            text=append_report_text(text,queue[0])
        self.notice.configure(text=text)
        if text:
            self.canvas.pack_forget()
        elif not self.canvas.winfo_manager():self.canvas.pack(pady=10,before=self.notice)
        self.update_controls()

    def update_controls(self):
        current=self.app.session.state['active_scene']
        playable=current is not None and current['notice'] is None and current['playback']['phase']!='done'
        self.play_button.configure(state='normal' if playable and self.paused else 'disabled')
        self.pause_button.configure(state='normal' if playable and not self.paused else 'disabled')
        self.next_button.configure(state='disabled' if playable else 'normal')

    def draw(self):
        self.image=tk.PhotoImage(data=self.display.picture().png(),master=self.canvas).zoom(2)
        self.canvas.itemconfigure(self.item,image=self.image)

    def play(self):
        current=self.app.session.state['active_scene']
        if current is None or current['notice'] is not None or current['playback']['phase']=='done':return
        if not self.paused:return
        self.app.content.prepare_story_scene(current['playback']['scene'])
        self.paused=False;self.clock=RetraceClock(time.perf_counter_ns());self.canvas.focus_set()
        self.app.effects.resume()
        self.message.set('Click the picture when prompted. Space or another key continues an input wait.')
        self.update_controls();self.schedule()

    def schedule(self):
        if self.paused:return
        # Slow work waits for the next reference retrace; it never schedules
        # an immediate catch-up step or drops a logical scene transaction.
        if self.clock is None:self.clock=RetraceClock(time.perf_counter_ns())
        self.timer=self.window.after(self.clock.delay_ms(time.perf_counter_ns()),lambda:self.app.guard(self.tick))

    def tick(self):
        self.timer=None
        if self.paused:return
        events=self.app.session.apply('scene_tick',mouse=self.mouse,key=self.key_pending)
        self.app.effects.sync()
        current=self.app.session.state['active_scene'];state=current['playback']
        if state['key_seen']:self.key_pending=False
        changed=False
        for event in events:
            if event[0]=='fade':self.display=fade_display(self.display,event[1]);changed=True
            elif event[0]=='frame':
                _,asset,frame,offset=event
                self.display=draw_display(self.display,self.app.content.story_animation(asset,frame),x=offset%320,y=offset//320);changed=True
            elif event[0]=='done':self.display=finish_display(self.display);changed=True
            # Committed sound requests are handled by the shared effect output.
        if changed:self.draw()
        if state['phase']=='done':self.pause();self.message.set('Scene complete. Continue when ready.');self.update_controls()
        else:self.schedule()

    def continue_story(self):
        self.pause()
        self.app.act('scene_acknowledge' if self.app.session.state['active_scene'] is not None else 'dismiss_presentation')
