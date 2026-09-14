"""Original battle control panels with native accessible action equivalents."""
import tkinter as tk
from tkinter import ttk
from .control_panel import ControlPictures,validate_buttons,pointer_slot
from .control_layouts import select_layout
from .control_playback import ControlPagePlayback
from .control_wipe import ControlWipePlayback
from .control_input import PanelPress
from ..core import GameError


class ControlPanelView(ttk.Frame):
    """Original panel pixels and pointer grid; accessible actions stay in ttk.

    Page changes, press gestures and hover captions are presentation state only.
    """
    def __init__(self,parent,content,guard):
        super().__init__(parent)
        self.content=content;self.buttons=None;self.layouts=None;self.pictures=None
        self.number=None;self.slots=[0]*12;self.page=0;self.commands={};self.images={};self.origin=0
        self.slides={};self.playback=ControlPagePlayback(self,guard)
        self.wipe=ControlWipePlayback(self,guard);self.displayed_picture=None;self.picture_data={}
        self.press_state=PanelPress();self.locked=False
        self.canvas=tk.Canvas(self,width=640,height=66,highlightthickness=0,background='#101114')
        self.canvas.pack(fill='x');self.item=self.canvas.create_image(0,0,anchor='nw')
        self.caption=tk.StringVar();ttk.Label(self,textvariable=self.caption).pack(anchor='center')
        self.canvas.bind('<Configure>',lambda _:self.position())
        self.canvas.bind('<Motion>',self.motion)
        self.canvas.bind('<Leave>',lambda _:self.caption.set(''))
        for button in (1,3):
            self.canvas.bind(f'<ButtonPress-{button}>',lambda event:guard(lambda:self.press(event)))
            self.canvas.bind(f'<ButtonRelease-{button}>',lambda event:guard(lambda:self.release(event)))
        self.canvas.bind('<FocusOut>',lambda _:self.press_state.cancel(reset=True))
        self.canvas.bind('<Unmap>',lambda _:self.press_state.cancel(reset=True))
        self.bind('<Destroy>',self.destroyed)

    @property
    def busy(self):return self.playback.active or self.wipe.active

    @property
    def locked(self):return self._locked

    @locked.setter
    def locked(self,value):
        self._locked=bool(value)
        if value:self.press_state.cancel()

    def destroyed(self,event):
        if event.widget is self:
            self.press_state.cancel(reset=True)
            self.playback.cancel();self.wipe.cancel();self.picture_data.clear()

    def show(self,number,commands):
        if self.pictures is None:
            if 'control_buttons' not in self.content.catalog or 'control_layouts' not in self.content.catalog:
                raise GameError('Control panel metadata is missing; re-extract the content bundle.')
            self.buttons=self.content.catalog['control_buttons'];validate_buttons(self.buttons)
            self.layouts=self.content.catalog['control_layouts'];self.pictures=ControlPictures(self.content)
        changed=number!=self.number
        if changed:
            self.press_state.cancel()
            slots=select_layout(self.layouts,number)['buttons']
            self.playback.cancel();self.wipe.cancel()
            self.slots=slots;self.number=number;self.page=0
            self.caption.set('')
        self.commands=commands
        if self.busy:return
        key=(number,self.page)
        if key not in self.images:
            picture=self.pictures.panel(self.buttons,self.slots,self.page)
            self.images[key]=self.make_image(picture)
        if changed:
            self.wipe.start(self.picture_data[str(self.images[key])]);return
        self.paint(self.images[key])

    def make_image(self,picture):
        image=tk.PhotoImage(master=self.canvas,data=picture.ppm(),format='PPM').zoom(2)
        self.picture_data[str(image)]=picture
        return image

    def paint(self,image):
        self.displayed_picture=self.picture_data[str(image)]
        self.canvas.itemconfigure(self.item,image=image);self.position()

    def slide_images(self):
        key=(self.number,self.page)
        if key not in self.slides:
            steps=self.content.catalog.get('control_slide')
            if steps is None:raise GameError('Control slide metadata is missing; re-extract the content bundle.')
            pictures=self.pictures.slide(self.buttons,self.slots,steps,self.page)
            self.slides[key]=tuple(self.make_image(p) for p in pictures)
        return self.slides[key]

    def position(self):
        self.origin=max(0,(self.canvas.winfo_width()-640)//2)
        self.canvas.coords(self.item,self.origin,0)

    def slot(self,event):
        px=(event.x-self.origin)//2;py=event.y//2
        if not (0<=px<320 and 0<=py<=32):return 0
        slot=pointer_slot(px,py)
        return slot+6*self.page if 1<=slot<=6 else slot

    def motion(self,event):
        if self.busy or self.locked or self.buttons is None:return
        slot=self.slot(event);action=self.slots[slot-1] if 1<=slot<=12 else 0
        self.caption.set(self.buttons[action]['label'] if action else 'Previous controls' if slot==13 and self.slots[6] and self.page else 'More controls' if slot==13 and self.slots[6] else '')
        active=action in self.commands or (slot==13 and bool(self.slots[6]))
        self.canvas.configure(cursor='hand2' if active else '')

    def press(self,event):
        self.canvas.focus_set()
        slot=self.slot(event)
        enabled=not (self.busy or self.locked) and (slot==13 or 1<=slot<=12 and bool(self.slots[slot-1]))
        self.press_state.press(event.num,slot,enabled)

    def release(self,event):
        slot=self.press_state.release(event.num,self.slot(event),not (self.busy or self.locked))
        if slot:self.activate(slot)

    def activate(self,slot):
        if self.busy or self.locked:return
        if slot==13 and self.slots[6]:
            self.playback.start()
        elif 1<=slot<=12:
            callback=self.commands.get(self.slots[slot-1])
            if callback is not None:callback()
