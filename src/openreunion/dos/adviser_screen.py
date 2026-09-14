"""Original DUMA consultation and university menus over shared transactions."""
import textwrap
from tkinter import ttk
from ..core import GameError
from .advice import unavailable
from .commanders import ROLES,training_available

MENUS={1:(1,2,3,4,5),2:(6,7),3:(8,9,10,11)}


def portrait_source(rank):return (5+106*(rank-1),1,98,109)
def menu_rect(index):return (112,93+9*index,97,9)


class AdviserScreen:
    def __init__(self,app):
        self.app=app;self.owner=None;self.role=None;self.rank=None;self.signature=None
        self.menu=1;self.question='';self.answer='';self.offset=0;self.hovered=None

    @property
    def active(self):return self.owner is not None

    def close(self):
        self.owner=None;self.signature=None;self.app.pointer.cancel(reset=True)

    def open(self,role):
        reason=unavailable(self.app.session.state,role)
        if reason:raise GameError(reason)
        self.questions=self.app.content.text('KERDES1.SP')
        self.compact=self.app.content.text('RKERDES1.SP')
        self.replies=self.app.content.text('VALASZ1.SP')
        if len(self.questions)<11 or len(self.compact)<11 or len(self.replies)<15:
            raise GameError('Commander conversation text is incomplete.')
        self.role=role;self.rank=self.app.session.state['ranks'][role];self.owner=self.app.session
        self.menu=1;self.question='';self.answer='';self.offset=0;self.hovered=None;self.signature=None
        quote=self.quote()
        if quote and quote['role']==role:
            self.menu=2;self.answer=self.price_text(quote)
        self.app.clock_panel.clock.pause();self.sync();self.app.show_original('adviser')

    def quote(self):return self.app.session.state['campaign']['training']['quote']
    def price_text(self,quote):return f"Training will cost {quote['cost']:,} credits."

    def sync(self):
        if not self.active:return
        state=self.app.session.state
        if self.owner is not self.app.session or self.rank!=state['ranks'][self.role] or unavailable(state,self.role) or \
                state['active_dialog'] is not None or state['active_scene'] is not None or state['presentation_requests'] or \
                state['campaign_phase']!='starmap' or any((state[k] or {}).get('phase','closed')!='closed' for k in ('space_encounter','ground_encounter')):
            self.close();return
        signature=(state['resources']['credits'],repr(state['campaign']['training']),state['campaign']['training_role'],
                   tuple(state['levels'].items()),tuple(state['skills'].items()),tuple(p['research_state'] for p in state['products']))
        if signature!=self.signature:
            self.app.pointer.cancel(reset=True);self.hovered=None;self.signature=signature
            if self.menu==2:
                quote=self.quote()
                if quote and quote['role']==self.role:self.answer=self.price_text(quote)
                else:self.menu=1;self.answer=''

    def lines(self):
        return [line for p in self.answer.splitlines() for line in (textwrap.wrap(p,width=51) or [''])]

    def targets(self):
        return [(menu_rect(i),self.questions[q-1],('adviser_choice',q)) for i,q in enumerate(MENUS[self.menu])]

    def draw(self):
        app=self.app;renderer=app.screen_renderer;role=ROLES.index(self.role)
        name=app.catalog['commanders'][role*3+self.rank-1]['name']
        target=renderer.frame(app.session.state,'DUMA',24,0,app.caption or name)
        target.blit(renderer.asset('FACES'+str(role+1)),5,90,source=portrait_source(self.rank))
        from .hero import adviser_source
        target.blit(renderer.asset('YOU'),217,90,source=adviser_source(app.hero))
        renderer.text(target,self.question,6,54,columns=52)
        for i,line in enumerate(self.lines()[self.offset:self.offset+3]):renderer.text(target,line,12,62+8*i,columns=51)
        for i,q in enumerate(MENUS[self.menu]):
            renderer.text(target,self.compact[q-1],112,93+9*i,columns=17,
                          color=(255,255,96) if q==self.hovered else (182,170,0))
        return target

    def scroll(self,lines):
        self.offset=max(0,min(max(0,len(self.lines())-3),self.offset+lines))
        self.app.pointer.cancel(reset=True);self.app.render_original()

    def reply(self,number,menu=1):
        self.answer=self.replies[number-1][3:].replace('|','\n');self.menu=menu

    def request_training(self,course):
        state=self.app.session.state
        if state['campaign']['training_role']:self.reply(9);return
        if not training_available(self.app.catalog['training_rules'],state['levels'],state['ranks'],state['skills'],
                                  state['campaign']['training']['phase'],self.role,course):
            self.reply(15);return
        self.app.act('quote_training',role=self.role,course=course)
        self.answer=self.price_text(self.quote());self.menu=2

    def dispatch(self,action):
        if action==24:self.close();self.app.show_original();return
        if not self.active or not isinstance(action,tuple) or action[0]!='adviser_choice':return
        q=action[1]
        if q not in MENUS[self.menu]:return
        self.question=self.questions[q-1];self.offset=0;self.hovered=None;self.app.pointer.cancel(reset=True)
        if q<=4:self.answer=self.app.act('consult_commander',role=self.role,question=q)[0]['answer']
        elif q==5:
            if self.app.session.state['campaign']['training_role']:self.reply(9)
            elif self.role=='developer':self.reply(14,3)
            else:self.request_training(0)
        elif q==6:
            quote=self.quote()
            if quote is None or quote['role']!=self.role:raise GameError('This university quote has changed. Request a new quote.')
            if self.app.session.state['resources']['credits']<quote['cost']:self.reply(12)
            else:
                self.app.act('train');self.close();self.app.show_original();return
        elif q==7:self.reply(11)
        else:self.request_training(q-7)
        self.app.render_original()


class AdviserBar(ttk.Frame):
    def __init__(self,app):
        super().__init__(app.root);self.app=app
        for name,callback in (('Leave',lambda:app.adviser_view.dispatch(24)),('Save',app.save),('Load',app.load)):
            ttk.Button(self,text=name,command=lambda fn=callback:app.guard(fn)).pack(side='left',padx=3)
        self.status=ttk.Label(self);self.status.pack(side='left',padx=8)

    def sync(self):
        view=self.app.adviser_view;count=len(view.lines());text='Choose a question'
        if view.menu==2:text='Accept or decline the saved training quote'
        elif view.menu==3:text='Choose a university course'
        if count>3:text+=f' | Scroll answer: {view.offset+1}-{min(view.offset+3,count)} of {count}'
        self.status.configure(text=text)
