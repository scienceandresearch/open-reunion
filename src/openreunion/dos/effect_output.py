"""Session-aware effect output shared by story windows and application saves."""
from copy import deepcopy
import tkinter as tk
from ..core import GameError
from .effect_control import initial_effects,validate_effects
from .battle_samples import sample_folder,SPACE_SAMPLES,GROUND_SAMPLES
from .sample_output import SamplePlayer

_UNPREPARED=object()


class EffectOutput:
    def __init__(self,app):
        self.app=app;self.player=SamplePlayer();self.timer=None;self.error=None;self.warning=None
        self._session=None;self._revision=None;self._samples={};self._started=False
        self._voice=None
        app.refresh_listeners.append(self.sync)
        app.root.bind('<Destroy>',lambda event:self.close() if event.widget is app.root else None,add='+')
        self.poll()

    def prepare(self,session,*,refresh=False):
        value=session.effects;validate_effects(value)
        if value is None or value['sample'] is None:return None
        name=value['sample']
        if refresh or name not in self._samples:
            folder=sample_folder(name)
            self._samples[name]=self.app.content.sample(name) if folder=='SOUND' else self.app.content.sample(name,folder)
        sample=self._samples[name]
        if value['frames']>sample.frames():raise GameError('Saved effect position exceeds the sample duration.')
        return sample

    def sync(self):
        session=self.app.session
        if self._session is session and self._revision==session.effect_revision:return
        navigation=getattr(self.app,'navigation_sound',None)
        if navigation is not None:navigation.cancel()
        changed=self._session is not session
        value=session.effects
        prepared=_UNPREPARED
        if not changed and value is not None and value['sample'] in SPACE_SAMPLES+GROUND_SAMPLES:
            # Original numbered loaders do not stop their previous voice until
            # the replacement file has opened and loaded successfully.
            try:prepared=self.prepare(session,refresh=value['sample']!=(self._voice or {}).get('sample'))
            except (GameError,OSError) as exc:
                self.reject_numbered(session,str(exc));return
        self._session=session;self._revision=session.effect_revision;self.error=None;self.warning=None
        if changed and value is not None and value['sample'] is not None:
            scene=session.state['active_scene']
            battle=any((session.state.get(key) or {}).get('phase') in ('setup','fighting')
                       for key in ('space_encounter','ground_encounter'))
            if battle or scene is not None and scene['playback']['phase']!='done':value['paused']=True
        self.launch(prepared)

    def reject_numbered(self,session,message):
        value=deepcopy(self._voice) if self._voice is not None else initial_effects()
        value['enabled']=session.effects['enabled']
        if value['sample'] is not None and self._started and not self.error:
            value.update(frames=self.player.position(),paused=self.player.paused and not self.player.completed)
        validate_effects(value)
        # Record the voice that actually survived the failed request, so save,
        # pause and resume cannot replay the missing name or rewind the old one.
        session.effects=value;self._voice=value;self._revision=session.effect_revision
        self.warning=message;self.app.status.set('Sound effect unavailable: '+message)

    def launch(self,prepared=_UNPREPARED):
        self.player.stop();self.player.error=None;self.error=None
        self._started=False;self._voice=None;self.warning=None
        try:
            sample=self.prepare(self.app.session) if prepared is _UNPREPARED else prepared
            value=self.app.session.effects
            if sample is not None:
                self.player.start(sample,frames=value['frames'],paused=value['paused']);self._started=True;self._voice=value
        except (GameError,OSError) as exc:self.failed(str(exc))

    def failed(self,message):
        self.error=message
        value=self.app.session.effects
        if value is not None and value['sample'] is not None:
            if self._started:
                try:value['frames']=self.player.position()
                except GameError:pass
            value['paused']=True
        self.app.status.set('Sound effect unavailable: '+message)

    def capture(self):
        if self._session is not self.app.session or self._revision!=self.app.session.effect_revision:return
        value=self.app.session.effects
        if value is not None and value['sample'] is not None and not self.error:
            value.update(frames=self.player.position(),paused=self.player.paused and not self.player.completed)
        validate_effects(value)

    def pause(self):
        if self._session is not self.app.session:return
        self.sync()
        try:
            if self.player.playing:self.player.pause(True)
        except GameError as exc:
            self.failed(str(exc));self.player.stop()
        self.capture()

    def suspend(self):
        self.pause();self.player.stop()

    def resume(self):
        self.sync();value=self.app.session.effects
        if value is None or value['sample'] is None:return
        if self.error or self.player.error or not self.player.playing and not self.player.completed:
            value['paused']=False;self.launch()
        else:
            self.player.pause(False);value['paused']=False

    def set_enabled(self,enabled):
        navigation=getattr(self.app,'navigation_sound',None)
        if not enabled and navigation is not None:navigation.cancel(restore=False)
        value=deepcopy(self.app.session.effects) or initial_effects()
        value['enabled']=enabled
        if not enabled:value.update(sample=None,frames=0,paused=False)
        validate_effects(value)
        self.app.session.effects=value;self.app.session.effect_revision+=1;self.sync()

    def poll(self):
        self.sync()
        if self.player.error and self.error!=self.player.error:self.failed(self.player.error)
        if self.player.completed:self.capture()
        self.timer=self.app.root.after(50,self.poll)

    def close(self):
        if self.timer is not None:
            try:self.app.root.after_cancel(self.timer)
            except tk.TclError:pass
            self.timer=None
        self.player.stop()
