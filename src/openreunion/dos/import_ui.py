"""A quiet first-run setup window. Conversion never plays audio."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from .asset_import import import_assets


class ImportWindow:
    def __init__(self, root, output):
        self.root = root
        self.output = Path(output).resolve()
        self.complete = False
        self.running = False
        self.events = queue.Queue()
        root.title('Open Reunion - Import original game')
        root.geometry('650x430')
        root.minsize(550, 380)
        panel = ttk.Frame(root, padding=24)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Bring your own copy of Reunion', font=('Segoe UI', 17)).pack(anchor='w')
        ttk.Label(panel, text='Choose the full extracted English game folder from your legally obtained copy.\n'
                  'It must include GRWAR, SAVE, graphics, text and sound folders.\n'
                  'The executable alone is not enough. Nothing is downloaded.', wraplength=580).pack(anchor='w', pady=12)
        self.choose = ttk.Button(panel, text='Choose game folder and import...', command=self.browse)
        self.choose.pack(anchor='w')
        self.progress = ttk.Progressbar(panel, mode='indeterminate')
        self.progress.pack(fill='x', pady=14)
        self.status = tk.StringVar(value='Your original files and personal saves will stay unchanged.')
        ttk.Label(panel, textvariable=self.status, wraplength=575, justify='left').pack(anchor='w', fill='x')
        self.finish = ttk.Button(panel, text='Continue to game', command=root.destroy)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def browse(self):
        selected = filedialog.askdirectory(parent=self.root, title='Select the original Reunion game folder', mustexist=True)
        if selected:
            self.start(selected)

    def start(self, selected):
        if self.running:
            return
        self.running = True
        self.choose.configure(state='disabled')
        self.status.set('Checking your copy...')
        self.progress.start(20)

        def worker():
            try:
                import_assets(selected, self.output, progress=lambda message: self.events.put(('progress', message)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
            else:
                self.events.put(('complete', 'Import complete. You can start a fresh game.'))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, message = self.events.get_nowait()
                self.status.set(message)
                if kind in ('complete', 'error'):
                    self.running = False
                    self.progress.stop()
                    if kind == 'complete':
                        self.complete = True
                        self.finish.pack(anchor='w', pady=14)
                    else:
                        self.choose.configure(state='normal')
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.running:
            self.status.set('Import is still running. Please wait; your original files are unchanged.')
        else:
            self.root.destroy()


def choose_and_import(output):
    root = tk.Tk()
    window = ImportWindow(root, output)
    root.mainloop()
    return window.complete
