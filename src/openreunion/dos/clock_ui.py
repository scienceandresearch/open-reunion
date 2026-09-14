"""Run/pause controls for the native hourly campaign clock."""
import tkinter as tk
from tkinter import ttk
from .campaign_clock import CampaignClock,pause_reason

SPEEDS={'1x':1000,'4x':250,'12x':83}


class ClockPanel(ttk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent);self.app=app;self.alive=True
        self.pack(fill='x',pady=(0,6))
        self.button=ttk.Button(self,text='Run',command=self.toggle);self.button.pack(side='left')
        ttk.Label(self,text='Speed:').pack(side='left',padx=(12,4))
        self.speed=tk.StringVar(value='1x')
        self.selector=ttk.Combobox(self,textvariable=self.speed,values=tuple(SPEEDS),state='readonly',width=5)
        self.selector.pack(side='left');self.selector.bind('<<ComboboxSelected>>',lambda _:self.clock.set_interval(SPEEDS[self.speed.get()]))
        ttk.Label(self,text='1x = 1 game hour/second').pack(side='left',padx=12)
        self.message=tk.StringVar(value='Paused');ttk.Label(self,textvariable=self.message).pack(side='left')
        self.clock=CampaignClock(app.root,lambda:app.session,lambda:app.guard(lambda:app.act('advance',hours=1)),
                                 changed=self.render,blocked=self.modal_reason)
        self.bind('<Destroy>',self.on_destroy,add='+')

    def on_destroy(self,event):
        if event.widget==self:
            self.alive=False;self.clock.pause(notify=False)

    def modal_reason(self):
        return 'Dialog in progress' if self.app.root.grab_current() is not None else None

    def toggle(self):
        self.app.guard(lambda:self.clock.pause() if self.clock.running else self.clock.start())

    def render(self):
        if not self.alive:return
        reason=pause_reason(self.app.session)
        self.button.configure(text='Pause' if self.clock.running else 'Run',state='normal' if self.clock.running or not reason else 'disabled')
        self.message.set(('Paused: '+reason) if reason and not self.clock.running else self.clock.reason)
        for button in self.app.hour_buttons:
            button.configure(state='disabled' if self.clock.running or self.app.session.defeated() or self.app.session.state['campaign_phase']=='victory' else 'normal')

    def refresh(self):
        self.clock.sync();self.render()
