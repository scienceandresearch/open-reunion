"""Recovered main/combat/dialog music and resumable listening controls."""
import tkinter as tk
from tkinter import ttk

from .audio_output import AudioPlayer
from .fm_music import MUSIC_NAMES
from .music_control import initial_audio,campaign_scene,scene_music,validate_audio
from ..core import GameError,integer


class MusicPanel:
    def __init__(self,app,tab):
        self.app=app;self.player=AudioPlayer();self.timer=None;self.active_track=None
        self._session=None;self._scene=None
        self.track=tk.StringVar(value='MAIN1');self.message=tk.StringVar(value='Choose a track, then Play.')
        self.automatic=tk.BooleanVar(value=True);self.main=tk.StringVar(value='Main 1')
        ttk.Checkbutton(tab,text='Follow game music',variable=self.automatic,command=lambda:app.guard(self.set_automatic)).pack(anchor='w',pady=(0,8))
        main=ttk.Combobox(tab,textvariable=self.main,values=('Off','Main 1','Main 2'),state='readonly',width=32)
        main.pack(anchor='w',pady=(0,8));main.bind('<<ComboboxSelected>>',lambda _:app.guard(self.set_main))
        ttk.Combobox(tab,textvariable=self.track,values=[name for name in MUSIC_NAMES if name!='FAILURE'],state='readonly',width=32).pack(anchor='w')
        controls=ttk.Frame(tab);controls.pack(anchor='w',pady=12)
        self.buttons={}
        for label,command in (('Play',self.play),('Pause',lambda:self.pause(True)),
                              ('Resume',lambda:self.pause(False)),('Stop',self.stop)):
            button=ttk.Button(controls,text=label,command=lambda fn=command:app.guard(fn))
            button.pack(side='left',padx=(0,8));self.buttons[label]=button
        ttk.Label(tab,textvariable=self.message,wraplength=880).pack(anchor='w')
        ttk.Label(tab,text='Game music follows battles and story conversations. Play selects a track manually; Stop disables automatic playback.',wraplength=880).pack(anchor='w',pady=12)
        app.refresh_listeners.append(self.sync)
        self.poll()
        app.root.bind('<Destroy>',lambda event:self.close() if event.widget is app.root else None,add='+')

    def play(self):
        value=self.app.session.audio
        value.update(track=self.track.get(),scene='manual',automatic=False,frames=0,paused=False)
        self.automatic.set(False);self.launch()

    def launch(self):
        value=self.app.session.audio;validate_audio(value);self.active_track=value['track']
        self.player.stop()
        self.player.error=None
        if value['track'] is None:self.message.set('Stopped.');return
        try:self.player.start(self.app.content.fm_music(value['track']),frames=value['frames'],paused=value['paused'])
        except (GameError,OSError) as exc:self.player.error=str(exc)

    def pause(self,paused):
        self.player.pause(paused)
        self.app.session.audio['paused']=paused

    def capture(self):
        value=self.app.session.audio
        if value and value['track'] and self.player.playing:
            paused=self.player.paused
            self.player.pause(True)
            try:value.update(frames=self.player.position(),paused=paused)
            finally:self.player.pause(paused)
        validate_audio(value)

    def set_automatic(self):
        self.capture();value=self.app.session.audio;value['automatic']=self.automatic.get()
        if value['automatic']:
            # Explicitly enabling returns from a manual selection even when the
            # underlying campaign screen has not changed.
            value['scene']='manual'
            self.app.session.audio,_=scene_music(value,campaign_scene(self.app.session.state))
            self.launch()

    def set_main(self):
        self.select_main(('Off','Main 1','Main 2').index(self.main.get()))

    def select_main(self,mode,*,follow_game=False):
        integer(mode,'Main music',maximum=2)
        value=self.app.session.audio;value['main']=mode
        self.main.set(('Off','Main 1','Main 2')[mode])
        if follow_game:value['automatic']=True;self.automatic.set(True)
        value.update(scene='main',track='MAIN'+str(value['main']) if value['main'] else None,frames=0,paused=False)
        self.launch()

    def sync(self):
        scene=campaign_scene(self.app.session.state)
        context=(scene,self.app.session.dialog_revision if scene=='talk' else self.app.session.scene_revision if scene.startswith('cinema') else 0)
        if self._session is not self.app.session:
            self._session=self.app.session
            if self._session.audio is None:
                self._session.audio,_=scene_music(initial_audio(),scene)
            validate_audio(self._session.audio)
            self.automatic.set(self._session.audio['automatic'])
            self.main.set(('Off','Main 1','Main 2')[self._session.audio['main']])
            self._scene=context;self.launch()
        elif self.app.session.audio['automatic'] and context!=self._scene:
            self.app.session.audio,changed=scene_music(self.app.session.audio,scene,previous_scene=self._scene[0])
            if changed:self.launch()
        self._scene=context

    def stop(self):
        self.player.stop();self.message.set('Stopped.')
        self.player.error=None
        self.app.session.audio.update(track=None,scene='manual',frames=0,paused=False,automatic=False)
        self.automatic.set(False)

    def poll(self):
        self.sync()
        playing=self.player.playing
        for name,enabled in (('Pause',playing and not self.player.paused),('Resume',playing and self.player.paused),('Stop',playing)):
            self.buttons[name].state(['!disabled'] if enabled else ['disabled'])
        if self.player.error:self.message.set(self.player.error)
        elif playing:self.message.set(('Restoring ' if self.player.seeking else 'Paused ' if self.player.paused else 'Playing ')+self.active_track)
        self.timer=self.app.root.after(100,self.poll)

    def close(self):
        if self.timer:
            try:self.app.root.after_cancel(self.timer)
            except tk.TclError:pass
            self.timer=None
        self.player.stop()
