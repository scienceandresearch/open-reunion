"""Visible clock controls beside the unchanged original game framebuffer."""
import tkinter as tk
from tkinter import ttk

from .campaign_clock import pause_reason
from .clock_ui import SPEEDS


class OriginalClockBar(tk.Frame):
    def __init__(self,app):
        super().__init__(app.root,background='#172323',padx=8,pady=4)
        self.app=app
        self.menu=ttk.Button(self,text='Main menu (F10)',command=lambda:app.guard(app.open_startup))
        self.menu.pack(side='right',padx=4)
        self.save_file=ttk.Button(self,text='Save file...',command=lambda:app.guard(app.save))
        self.load_file=ttk.Button(self,text='Load file...',command=lambda:app.guard(app.load))
        self.research_pause=ttk.Button(self,text='Pause research',command=lambda:app.guard(self.toggle_research))
        self.run=ttk.Button(self,text='Run (Space)',width=13,
                            command=lambda:app.guard(self.toggle))
        self.run.pack(side='left')
        self.speed=tk.StringVar(value='4x')
        self.selector=ttk.Combobox(self,textvariable=self.speed,values=tuple(SPEEDS),
                                  state='readonly',width=4,takefocus=False)
        self.selector.pack(side='left',padx=8)
        self.selector.bind('<<ComboboxSelected>>',lambda _:app.guard(self.change_speed))
        self.message=tk.StringVar()
        tk.Label(self,textvariable=self.message,background='#172323',foreground='#deeeee',
                 anchor='w').pack(side='left',fill='x',expand=True)
        clock=app.clock_panel.clock
        clock.set_interval(250)
        previous_changed,previous_blocked=clock.changed,clock.blocked
        def changed():
            previous_changed()
            if self.winfo_exists():self.refresh()
        clock.changed=changed
        clock.blocked=lambda:app.clock_edit_reason() or previous_blocked()
        self.refresh()

    def toggle(self):
        self.app.toggle_time()
        self.app.original.focus_set()

    def change_speed(self):
        self.app.clock_panel.clock.set_interval(SPEEDS[self.speed.get()])
        self.refresh()
        self.app.original.focus_set()

    def toggle_research(self):
        if self.app.screen!='research':return
        self.app.act('pause_research',paused=not self.app.session.state['research_paused'])
        self.app.original.focus_set()

    def refresh(self):
        if self.app.screen=='research':
            self.research_pause.configure(text='Resume research' if self.app.session.state['research_paused'] else 'Pause research')
            self.research_pause.pack(side='right',padx=2)
        else:self.research_pause.pack_forget()
        for button in (self.save_file,self.load_file):
            if self.app.screen=='disk':button.pack(side='right',padx=2)
            else:button.pack_forget()
        clock=self.app.clock_panel.clock
        self.speed.set(next(label for label,interval in SPEEDS.items() if interval==clock.interval))
        self.app.clock_panel.speed.set(self.speed.get())
        reason=self.app.clock_edit_reason() or pause_reason(self.app.session)
        self.run.configure(text='Pause (Space)' if clock.running else 'Run (Space)',
                           state='disabled' if reason and not clock.running else 'normal')
        if clock.running:
            self.message.set(f'Running at {self.speed.get()} - 1x = 1 game hour/second')
        elif reason:self.message.set('Paused: '+reason)
        elif clock.reason=='Paused':self.message.set('Paused - Space or Run advances time')
        else:self.message.set(clock.reason)
