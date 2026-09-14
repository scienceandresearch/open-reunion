"""Original conversation room, alternating question/answer pane and portraits."""
import textwrap
from tkinter import ttk

PORTRAITS=(0,2,2,2,2,4,3,5,4,6,11)


def text_lines(text):
    # Preserve original explicit lines, but retain over-width text by wrapping
    # instead of clipping it. The viewport scrolls when more than seven result.
    return [line for paragraph in text.splitlines() for line in
            (textwrap.wrap(paragraph,width=36,replace_whitespace=False) or [''])] or ['']


def choice_rows(definition,current):
    return [(question,line) for question in definition['nodes'][current['node']]
            for line in text_lines(definition['questions'][question-1]['text'])] if not current['closed'] else []


class DialogScreen:
    def __init__(self,app):
        self.app=app;self.context=None;self.reading=False;self.offset=0;self.hovered=None

    @property
    def active(self):return self.app.session.state['active_dialog'] is not None

    def current(self):return self.app.session.state['active_dialog']

    def definition(self):return self.app.catalog['dialogs'][str(self.current()['script'])]

    def sync(self):
        current=self.current()
        context=(self.app.session,tuple(current.items()) if current else None)
        if context!=self.context:
            self.context=context;self.reading=bool(current and current['answer']);self.offset=0;self.hovered=None
            self.app.pointer.cancel(reset=True)

    def rows(self):
        current=self.current();definition=self.definition()
        if self.reading:return [(None,line) for line in text_lines(definition['answers'][current['answer']-1]['text'])]
        return choice_rows(definition,current)

    def targets(self):
        if self.reading:return [((6,134,211,63),'Continue conversation',('dialog_continue',))]
        return [((6,134+9*i,211,9),'Choose response',('dialog_choice',question))
                for i,(question,_) in enumerate(self.rows()[self.offset:self.offset+7])]

    def draw(self):
        app=self.app;renderer=app.screen_renderer;portrait=PORTRAITS[self.current()['script']]
        target=renderer.frame(app.session.state,'PICS/ATVEZETO.PIC',34,0,app.caption or 'CONVERSATION')
        target.blit(renderer.path_asset(f'PICS/SZEK{portrait}.PIC'),115,50,source=(1,1,106,80))
        from .hero import dialog_path
        target.blit(renderer.path_asset(dialog_path(app.hero)),23,50,source=(1,1,65,80))
        target.blit(renderer.path_asset(f'ALIEN/ALIEN{portrait}.PIC'),224,50,source=(2,1,95,149))
        target.fill((6,134,216,64),(0,0,0))
        for i,(question,line) in enumerate(self.rows()[self.offset:self.offset+7]):
            color=(255,255,96) if question is not None and question==self.hovered else (182,170,0)
            renderer.text(target,line,6,134+9*i,columns=36,color=color)
        return target

    def scroll(self,lines):
        self.offset=max(0,min(max(0,len(self.rows())-7),self.offset+lines))
        self.app.pointer.cancel(reset=True);self.hovered=None;self.app.render_original()

    def dispatch(self,action):
        if not self.active:return
        if action==('dialog_continue',) and self.reading:
            if self.current()['closed']:self.app.act('dialog_acknowledge')
            else:
                self.reading=False;self.offset=0;self.hovered=None
                self.app.pointer.cancel(reset=True);self.app.render_original()
        elif isinstance(action,tuple) and action[0]=='dialog_choice' and not self.reading:
            self.app.act('dialog_answer',question=action[1])


class DialogBar(ttk.Frame):
    def __init__(self,app):
        super().__init__(app.root);self.app=app;self.view=app.dialog_view
        self.next=ttk.Button(self,text='Continue',command=lambda:app.guard(lambda:self.view.dispatch(('dialog_continue',))))
        self.next.pack(side='left')
        for label,callback in (('Save',app.save),('Load',app.load)):
            ttk.Button(self,text=label,command=lambda fn=callback:app.guard(fn)).pack(side='left',padx=(6,0))
        self.status=ttk.Label(self);self.status.pack(side='left',padx=8)

    def sync(self):
        view=self.view;self.next.configure(state='normal' if view.reading else 'disabled')
        text='Read answer, then Continue' if view.reading else 'Choose a response'
        count=len(view.rows())
        if count>7:text+=f' | Scroll: lines {view.offset+1}-{min(view.offset+7,count)} of {count}'
        self.status.configure(text=text)
