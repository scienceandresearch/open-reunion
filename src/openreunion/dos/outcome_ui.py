"""Visible campaign completion with save/load actions and assistance status."""
import tkinter as tk
from tkinter import ttk


class OutcomePanel(ttk.LabelFrame):
    def __init__(self, parent, app):
        super().__init__(parent, text='Campaign result', padding=12)
        self.app = app
        self.title = tk.StringVar()
        self.description = tk.StringVar()
        self.details = tk.StringVar()
        ttk.Label(self, textvariable=self.title, font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        self.description_label = ttk.Label(self, textvariable=self.description, wraplength=1000)
        self.description_label.pack(anchor='w', pady=(4, 0))
        self.details_label = ttk.Label(self, textvariable=self.details, wraplength=1000)
        self.details_label.pack(anchor='w', pady=(4, 8))
        actions = ttk.Frame(self)
        actions.pack(fill='x')
        ttk.Button(actions, text='Save result', command=lambda: app.guard(app.save)).pack(side='left', padx=(0, 8))
        ttk.Button(actions, text='Load another save', command=lambda: app.guard(app.load)).pack(side='left')
        self.bind('<Configure>', self.resize)

    def resize(self, event):
        width = max(200, event.width - 30)
        self.description_label.configure(wraplength=width)
        self.details_label.configure(wraplength=width)

    def refresh(self):
        state = self.app.session.state
        victory = state['campaign_phase'] == 'victory'
        ended = victory or self.app.session.defeated()
        for button in self.app.hour_buttons:
            button.configure(state='disabled' if ended else 'normal')
        if not ended:
            self.pack_forget()
            return
        self.title.set('Earth is free' if victory else 'New Earth has fallen')
        self.description.set(
            'Earth has been liberated. Your Reunion campaign is complete.' if victory else
            'Your colony has been lost. Load an earlier save to try again.')
        year, month, day, hour = state['date']
        assistance = 'Admin assistance used' if state['assisted'] else 'No admin assistance'
        self.details.set(f'{year:04d}-{month:02d}-{day:02d} {hour:02d}:00  |  {assistance}')
        self.pack(fill='x', pady=(8, 0), before=self.app.toolbar)
