"""Transient original control-panel navigation samples.

These sounds are presentation state, not campaign effects: they never enter a
save. A saved scene or battle voice is paused while the short navigation
sample owns output and is resumed only if that exact voice still belongs to
the same session and effect revision.
"""
import tkinter as tk

from ..core import GameError
from .sample_output import SamplePlayer


class NavigationSound:
    def __init__(self,app):
        self.app=app;self.player=SamplePlayer();self.timer=None
        self.owner=None;self.destination=None
        self.background=None;self.background_paused=None
        self.background_session=None;self.background_revision=None;self.background_voice=None

    @property
    def active(self):return self.owner is not None

    def enabled(self):
        value=self.app.session.effects
        return value is None or value['enabled']

    def report(self,message):
        self.app.status.set('Sound effect unavailable: '+message)

    def start(self,name,destination):
        self.cancel()
        if not self.enabled():return False
        try:sample=self.app.content.sample(name)
        except (GameError,OSError) as exc:
            self.report(str(exc));return False
        self.owner=self.app.session;self.destination=destination
        output=self.app.effects;background=output.player
        if background.playing and not background.completed:
            self.background=background;self.background_paused=background.paused
            self.background_session=output._session
            self.background_revision=output._revision
            self.background_voice=output._voice
            try:background.pause(True)
            except (GameError,OSError) as exc:
                self.report(str(exc));self._clear();return False
        try:self.player.start(sample)
        except (GameError,OSError) as exc:
            self.report(str(exc));self.cancel();return False
        self.timer=self.app.root.after(25,self.poll)
        return True

    def retain(self,destination):
        return (self.owner is self.app.session and self.destination==destination
                and self.enabled())

    def poll(self):
        self.timer=None
        if self.owner is not self.app.session or self.app.screen!=self.destination:
            self.cancel();return
        if not self.enabled():
            self.cancel(restore=False);return
        if self.player.error:
            self.report(self.player.error);self.cancel();return
        if self.player.playing and not self.player.completed:
            self.timer=self.app.root.after(25,self.poll)
        else:self.cancel()

    def cancel(self,restore=True):
        if self.timer is not None:
            try:self.app.root.after_cancel(self.timer)
            except tk.TclError:pass
            self.timer=None
        try:self.player.stop()
        except GameError as exc:self.report(str(exc))
        if restore:self._restore()
        self._clear()

    def _restore(self):
        output=self.app.effects
        if (self.background is not None and self.owner is self.app.session
                and self.background is output.player
                and self.background_session is output._session
                and self.background_revision==output._revision
                and self.background_voice is output._voice):
            try:self.background.pause(self.background_paused)
            except (GameError,OSError) as exc:self.report(str(exc))

    def _clear(self):
        self.owner=None;self.destination=None;self.background=None
        self.background_paused=None;self.background_session=None;self.background_revision=None
        self.background_voice=None
