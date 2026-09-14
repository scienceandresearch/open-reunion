"""Original KOCSMA room and BESZED conversations over saved bar commands."""
import struct
from tkinter import ttk
from ..core import GameError
from .bar import agent_status
from .bar_dialogs import available_agents,choices,answer_text,question_text,eligible_targets
from .strategy import campaign_work
from .dialog_screen import text_lines


def agent_name(row):return bytes(row['prefix'][1:1+min(row['prefix'][0],13)]).decode('cp437').strip()


def agent_rect(row):
    raw=bytes(row['suffix'])
    return struct.unpack_from('<h',raw,3)[0]+1,raw[5]+50,raw[6]-2,raw[7]-2


def agent_source(row):
    raw=bytes(row['suffix'])
    return struct.unpack_from('<h',raw)[0]+1,raw[2]+1,raw[6]-2,raw[7]-2


def clipped_copy(target,picture,rect,source,*,transparent=None):
    x,y,w,h=rect;sx,sy,_,_=source
    # Original records can ask for the row past the end of the sprite sheet.
    # Clip source and destination instead of reading outside either image.
    dx=max(0,-x,-sx);dy=max(0,-y,-sy);x+=dx;sx+=dx;y+=dy;sy+=dy;w-=dx;h-=dy
    w=min(w,320-x,picture.width-sx);h=min(h,200-y,picture.height-sy)
    if w>0 and h>0:target.blit(picture,x,y,source=(sx,sy,w,h),transparent=transparent)


class BarScreen:
    def __init__(self,app):self.app=app;self.context=None;self.offset=0;self.hovered=None

    def bar(self):return self.app.session.state['campaign']['bar']
    def current(self):return (self.bar() or {}).get('conversation')
    @property
    def active(self):return self.current() is not None
    @property
    def reading(self):return self.active and self.current()['phase']=='answer'

    def sync(self):
        work=campaign_work(self.app.session.state)
        context=(self.app.session,repr(self.bar()),tuple(eligible_targets(work).items()))
        if context!=self.context:
            self.context=context;self.offset=0;self.hovered=None;self.app.pointer.cancel(reset=True)

    def rows(self):
        current=self.current();rules=self.app.catalog['bar_dialogs']
        if self.reading:return [(None,line) for line in text_lines(answer_text(current,rules))]
        return [(q,line) for q in choices(campaign_work(self.app.session.state),rules,current)
                for line in text_lines(question_text(current,q,rules))] if current else []

    def targets(self):
        if not self.active:
            return [(agent_rect(self.bar()['agents'][i-1]),agent_name(self.bar()['agents'][i-1]),('bar_talk',i))
                    for i in available_agents(campaign_work(self.app.session.state))]
        if self.reading:return [((6,134,211,63),'Continue conversation',('bar_continue',))]
        return [((6,134+9*i,211,9),'Choose response',('bar_choice',q))
                for i,(q,_) in enumerate(self.rows()[self.offset:self.offset+7])]

    def draw(self):
        app=self.app;renderer=app.screen_renderer;bar=self.bar()
        if bar is None:raise GameError('This save lacks bar records. Start a new game or import a complete DOS save.')
        current=self.current()
        if current is None:
            target=renderer.frame(app.session.state,'KOCSMA',23,0,app.caption or 'SPACE LOCAL')
            sheet=renderer.asset('PIRATES');work=campaign_work(app.session.state)
            for i in range(10,0,-1):
                row=bar['agents'][i-1]
                if agent_status(work,i) in (2,3) and row['remaining']==0:
                    clipped_copy(target,sheet,agent_rect(row),agent_source(row),transparent=0)
            return target
        agent=current['agent'];row=bar['agents'][agent-1]
        target=renderer.frame(app.session.state,'BESZED2' if agent==6 else 'BESZED',25,0,app.caption or agent_name(row))
        if agent!=6:
            target.blit(renderer.path_asset(f'ALIEN/KOCSMB{agent}.PIC'),77,49,source=(1,1,79,76),transparent=0)
        target.blit(renderer.path_asset(f"ALIEN/ALIEN{row['prefix'][14]}.PIC"),224,50,source=(1,1,95,143))
        target.fill((6,134,216,64),(0,0,0))
        for i,(q,line) in enumerate(self.rows()[self.offset:self.offset+7]):
            color=(255,255,96) if q is not None and q==self.hovered else (182,170,0)
            renderer.text(target,line,6,134+9*i,columns=36,color=color)
        return target

    def scroll(self,lines):
        if self.active:
            self.offset=max(0,min(max(0,len(self.rows())-7),self.offset+lines))
            self.hovered=None;self.app.pointer.cancel(reset=True);self.app.render_original()

    def dispatch(self,action):
        if action==24:
            if self.active:self.app.act('bar_leave')
            else:self.app.show_original()
        elif action==('bar_continue',) and self.reading:self.app.act('bar_acknowledge')
        elif isinstance(action,tuple):
            if action[0]=='bar_talk' and not self.active:self.app.act('bar_talk',agent=action[1])
            elif action[0]=='bar_choice' and self.active and not self.reading:self.app.act('bar_answer',question=action[1])


class BarControls(ttk.Frame):
    def __init__(self,app):
        super().__init__(app.root);self.app=app;self.view=app.bar_view
        self.next=ttk.Button(self,text='Continue',command=lambda:app.guard(lambda:self.view.dispatch(('bar_continue',))))
        self.next.pack(side='left')
        self.leave=ttk.Button(self,text='Leave',command=lambda:app.guard(lambda:self.view.dispatch(24)))
        self.leave.pack(side='left')
        for label,callback in (('Save',app.save),('Load',app.load)):
            ttk.Button(self,text=label,command=lambda fn=callback:app.guard(fn)).pack(side='left',padx=(6,0))
        self.status=ttk.Label(self);self.status.pack(side='left',padx=8)

    def sync(self):
        view=self.view;self.next.configure(state='normal' if view.reading else 'disabled')
        text='Read answer, then Continue' if view.reading else 'Choose a response'
        count=len(view.rows())
        if count>7:text+=f' | Scroll: lines {view.offset+1}-{min(view.offset+7,count)} of {count}'
        self.status.configure(text=text)
