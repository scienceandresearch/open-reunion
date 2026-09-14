"""Cancelable presentation clock; simulation remains in the hourly command."""


def pause_reason(session):
    state=session.state
    if session.defeated() or state['campaign_phase']=='victory':return 'Campaign ended'
    if state['active_dialog'] is not None:return 'Conversation needs attention'
    if state['active_scene'] is not None or state['presentation_requests']:return 'Story needs attention'
    if (state['campaign']['bar'] or {}).get('conversation') is not None:return 'Bar conversation in progress'
    if state['battle_requests'] or any((state[key] or {}).get('phase','closed')!='closed' for key in ('ground_encounter','space_encounter')):
        return 'Battle needs attention'
    return None


class CampaignClock:
    def __init__(self,scheduler,get_session,step,changed=lambda:None,blocked=lambda:None):
        self.scheduler,self.get_session,self.step=scheduler,get_session,step
        self.changed,self.blocked=changed,blocked
        self.running=False;self.pending=None;self.generation=0;self.session=None
        self.interval=1000;self.reason='Paused'

    def pause(self,reason='Paused',*,notify=True):
        self.generation+=1
        if self.pending is not None:self.scheduler.after_cancel(self.pending)
        self.pending=None;self.running=False;self.session=None;self.reason=reason
        if notify:self.changed()

    def start(self):
        if self.running:return
        reason=self.blocked() or pause_reason(self.get_session())
        if reason:self.pause(reason);return
        self.generation+=1;self.session=self.get_session();self.running=True;self.reason='Running'
        self.schedule();self.changed()

    def set_interval(self,interval):
        if type(interval) is not int or interval not in (1000,250,83):raise ValueError('Unknown campaign clock speed.')
        self.interval=interval
        if self.running:
            self.generation+=1
            if self.pending is not None:self.scheduler.after_cancel(self.pending)
            self.pending=None;self.schedule()

    def schedule(self):
        generation=self.generation
        self.pending=self.scheduler.after(self.interval,lambda:self.tick(generation))

    def sync(self):
        if not self.running:return
        if self.get_session() is not self.session:self.pause('Loaded game is paused');return
        reason=self.blocked() or pause_reason(self.session)
        if reason:self.pause(reason)

    def tick(self,generation):
        if not self.running or generation!=self.generation:return
        self.pending=None
        try:
            self.sync()
            if not self.running:return
            self.step()
            self.sync()
        except Exception:
            self.pause('Paused after an error');raise
        # A refresh, load, pause or speed change inside step can invalidate
        # this callback. It must never install a second timer afterward.
        if self.running and generation==self.generation:self.schedule()
