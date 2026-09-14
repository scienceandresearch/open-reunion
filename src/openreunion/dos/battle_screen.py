"""Shared main-screen battle timer, fade and accessible controls."""
from tkinter import ttk


class BattleScreen:
    @property
    def won(self):return (self.encounter() or {}).get('player_won',False)

    def __init__(self, app):
        self.app=app;self.session=app.session;self.pixels=None
        self.running=False;self.timer=None;self.fade_timer=None;self.fade_step=5
        self.phase=None;self.interval=50;self.generation=0


    def encounter(self):return self.app.session.state[self.family+'_encounter']


    @property
    def active(self):return (self.encounter() or {}).get('phase') in ('fighting','result')


    def owns_effect(self):
        return self.session is self.app.session and (self.app.session.effects or {}).get('sample') in self.samples


    def cancel_fade(self):
        if self.fade_timer is not None:self.app.root.after_cancel(self.fade_timer)
        self.fade_timer=None;self.fade_step=5


    def pause(self, *, audio=True, fade=True):
        self.generation+=1
        self.running=False
        if self.timer is not None:self.app.root.after_cancel(self.timer)
        self.timer=None
        if audio and self.owns_effect():self.app.effects.pause()
        if fade:self.cancel_fade()
        if getattr(self.app,self.family+'_bar',None) is not None:getattr(self.app,self.family+'_bar').sync()


    def sync(self):
        phase=(self.encounter() or {}).get('phase')
        if self.session is not self.app.session:
            self.pause();self.session=self.app.session;self.phase=phase
            self.app.pointer.cancel(reset=True)
        previous=self.phase;self.phase=phase
        if phase!=previous:self.app.pointer.cancel(reset=True)
        if phase!='fighting':self.pause(audio=False,fade=False)
        if phase=='result' and previous=='fighting':
            self.cancel_fade();self.fade_step=0;self.schedule_fade()
        elif phase!='result':self.cancel_fade()


    def schedule_fade(self):
        if self.fade_step<5 and self.fade_timer is None:
            self.fade_timer=self.app.root.after(14,lambda:self.app.guard(self.advance_fade))


    def advance_fade(self):
        self.fade_timer=None
        if self.session is not self.app.session or (self.encounter() or {}).get('phase')!='result':
            self.cancel_fade();return
        self.fade_step=min(5,self.fade_step+1)
        if self.app.screen==self.family:self.app.render_original()
        self.schedule_fade()


    def step(self):self.pause();self.tick()


    def toggle(self):
        if self.running:self.pause()
        elif (self.encounter() or {}).get('phase')=='fighting':
            self.running=True
            if self.owns_effect():self.app.effects.resume()
            self.schedule()
        self.app.render_original()


    def schedule(self):
        if self.running and self.timer is None:
            generation=self.generation
            self.timer=self.app.root.after(self.interval,lambda:self.app.guard(lambda:self.frame(generation)))


    def frame(self,generation):
        if generation!=self.generation:return
        self.timer=None
        if not self.running:return
        if self.session is not self.app.session or self.app.screen!=self.family or not self.app.original.winfo_ismapped():
            self.pause();return
        if not self.app.pointer.buttons:self.tick()
        self.schedule()



class BattleBar(ttk.Frame):
    """Small accessible controls below the unchanged original framebuffer."""
    def __init__(self,app,family):
        super().__init__(app.root);self.app=app;self.view=getattr(app,family+'_view')
        if family=='space':
            self.notice=ttk.Label(self,anchor='w',justify='left',font=('TkDefaultFont',10,'bold'))
            self.notice.pack(side='top',fill='x',padx=8,pady=(3,4))
            self.bind('<Configure>',lambda event:self.notice.configure(wraplength=max(1,event.width-16)))
        self.run=ttk.Button(self,text='Run (Space)',command=lambda:app.guard(self.view.toggle));self.run.pack(side='left')
        self.step=ttk.Button(self,text='Step',command=lambda:app.guard(self.view.step));self.step.pack(side='left')
        ttk.Label(self,text='Speed').pack(side='left',padx=(8,3))
        self.speed=ttk.Combobox(self,values=('5','10','20','40'),state='readonly',width=3)
        self.speed.set('20');self.speed.pack(side='left')
        self.speed.bind('<<ComboboxSelected>>',lambda _:setattr(self.view,'interval',1000//int(self.speed.get())))
        for name,callback in (('Save',app.save),('Load',app.load)):
            ttk.Button(self,text=name,command=lambda callback=callback:app.guard(callback)).pack(side='left',padx=(6,0))
        self.status=ttk.Label(self);self.status.pack(side='left',padx=8)

    def sync(self):
        view=self.view;encounter=view.encounter() or {};fighting=encounter.get('phase')=='fighting'
        self.run.configure(text='Pause (Space)' if view.running else 'Run (Space)',state='normal' if fighting else 'disabled')
        self.step.configure(state='normal' if fighting else 'disabled')
        self.status.configure(text=('Battle running' if view.running else 'Battle paused') if fighting else
                              'Victory: Continue' if view.won else 'Defeat: Continue')
