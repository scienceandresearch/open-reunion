"""Twelve original-screen slots backed by independent modern JSON saves."""
import json
from pathlib import Path
from tkinter import messagebox
from ..core import GameError,integer
from ..persistence import MAX_SAVE_BYTES,_unique_object

SLOT_RECT=(11,64,130,108)


def slot_at(y):return max(1,min(12,int((y-64)/9)+1))


def slot_path(directory,slot):
    integer(slot,'Save slot',minimum=1,maximum=12)
    directory=Path(directory).resolve();path=directory/f'recovered-slot-{slot:02}.json'
    if path.is_symlink() or path.resolve().parent!=directory:
        raise GameError('Save slot points outside the save folder.')
    if path.exists() and not path.is_file():raise GameError('Save slot is not a regular file.')
    return path


def slot_label(directory,slot):
    try:
        path=slot_path(directory,slot)
        if not path.exists():return f'{slot:02} -- Empty --'
        with path.open('rb') as stream:raw=stream.read(MAX_SAVE_BYTES+1)
        if len(raw)>MAX_SAVE_BYTES:raise ValueError('Too large')
        data=json.loads(raw,object_pairs_hook=_unique_object);date=data.get('date')
        if not isinstance(date,list) or len(date)!=4 or any(type(v)is not int for v in date):raise ValueError('Invalid date')
        year,month,day,hour=date
        if not (0<=year<=9999 and 1<=month<=12 and 1<=day<=31 and 0<=hour<=23):raise ValueError('Invalid date')
        return f'{slot:02} {year:04}/{month:02}/{day:02}/{hour:02}'
    except (OSError,ValueError,RecursionError,AttributeError,GameError):return f'{slot:02} Unreadable save'


class DiskSlots:
    def __init__(self,app):self.app=app;self.selected=1;self.labels=[]

    def refresh(self):self.labels=[slot_label(self.app.save_dir,i) for i in range(1,13)]

    def select(self,y):self.selected=slot_at(y);self.app.render_original()

    def save(self):
        self.app.pause_battles();owner=self.app.session;slot=self.selected
        path=slot_path(self.app.save_dir,slot)
        if path.exists() and not messagebox.askyesno('Replace saved game',f'Replace save slot {slot}?',parent=self.app.root):return
        if owner is not self.app.session:raise GameError('The current game changed; choose the save slot again.')
        path=slot_path(self.app.save_dir,slot)
        self.app.save_path(path);self.refresh();self.app.show_original()

    def load(self):
        path=slot_path(self.app.save_dir,self.selected)
        if not path.exists():raise GameError('This save slot is empty. Choose an occupied slot or Load file.')
        self.app.load_path(path);self.refresh();self.app.show_original()

    def draw(self,renderer,target):
        for i,label in enumerate(self.labels,1):
            selected=i==self.selected
            palette=renderer.asset('DISK').palette;start=115 if selected else 112
            colors=[palette[3*j:3*j+3] for j in range(start,start+3)]
            renderer.text(target,label,16,64+9*(i-1),columns=19,
                background=colors[0],color=colors[1],shadow=colors[2])
