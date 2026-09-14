"""Original ground battle, orders and results on the main framebuffer."""
import time
from ..core import GameError
from .battle_screen import BattleScreen,BattleBar
from .battle_samples import GROUND_SAMPLES
from .ground_pixels import GroundPixels
from .ground_presentation import ground_render_plan
from .battle_results import BattleResultPictures
from .control_layouts import result_control_enabled
from .video_timing import RetraceClock


class GroundScreen(BattleScreen):
    family='ground'
    samples=GROUND_SAMPLES

    def __init__(self,app):
        super().__init__(app)
        self.terrain=None;self.result_pixels=None;self.signature=None
        self.result_timer=None;self.result_clock=None;self.result_generation=0

    @property
    def won(self):return ((self.encounter() or {}).get('battle') or {}).get('player_won',False)

    def pause(self,*,audio=True,fade=True):
        if fade:self.stop_result()
        super().pause(audio=audio,fade=fade)

    def sync(self):
        super().sync()
        battle=(self.encounter() or {}).get('battle') or {}
        signature=(battle.get('control_mode'),battle.get('selected_group'),battle.get('selected_friendly'),
                   tuple(tuple(r) for r in battle.get('friendly_groups',[])),
                   tuple(tuple(r) for r in battle.get('hostile_groups',[])))
        if signature!=self.signature:self.app.pointer.cancel(reset=True)
        self.signature=signature
        self.sync_result()

    def enabled(self,action):
        phase=(self.encounter() or {}).get('phase')
        return (action==72 and phase=='fighting' or action==65 and self.fade_step==5
                and result_control_enabled(self.app.catalog,phase))

    def targets(self):
        if (self.encounter() or {}).get('phase')!='fighting':return []
        return [((0,168,64,16),'Move selected group (M)',('ground_order','move')),
                ((0,184,64,16),'Attack selected target (A)',('ground_order','attack')),
                ((0,49,64,119),'Cancel targeting',('ground_order','cancel')),
                ((64,49,256,151),'Select group or order destination',('ground_board',))]

    def draw(self):
        encounter=self.encounter()
        if not self.active:raise GameError('There is no active ground battle.')
        identity=':'.join(map(str,encounter['destination']))
        name=next(w['name'] for w in self.app.catalog['worlds'] if w['id']==identity)
        if encounter['phase']=='fighting':
            terrain=self.app.session.state['worlds'][identity]['raw'][21]
            if self.pixels is None or terrain!=self.terrain:
                self.pixels=GroundPixels(self.app.content,terrain);self.terrain=terrain
            rules=self.app.catalog['battle_rules']
            calls=ground_render_plan(encounter['battle'],rules['ground_motion'],self.app.catalog['ground_presentation'],rules['ground_controls'])
            body=self.pixels.ppm(calls);layout=32
        else:
            self.prepare_results()
            value=self.app.session.result_animation
            body=self.result_pixels.picture('ground',self.won,encounter['losses'],
                frame=value['shown'] if value else 1,fade_step=self.fade_step).ppm();layout=30
        return self.app.screen_renderer.battle(self.app.session.state,body,layout,self.app.caption or name)

    def tick(self):
        if (self.encounter() or {}).get('phase')!='fighting':return
        self.app.session.apply('ground_tick');self.app.effects.sync();self.sync()
        if self.phase=='result':self.app.refresh()
        else:self.app.render_original()

    def command(self,action,**args):
        if (self.encounter() or {}).get('phase')!='fighting':return
        self.app.act('ground_command',command=action,**args)

    def dispatch(self,action):
        if not self.enabled(action):return
        self.pause()
        if action==72:self.command('retreat')
        else:self.app.act('ground_acknowledge')

    def prepare_results(self):
        if self.result_pixels is None:self.result_pixels=BattleResultPictures(self.app.content)

    def stop_result(self,*,pause=True):
        self.result_generation+=1
        if self.result_timer is not None:self.app.root.after_cancel(self.result_timer)
        self.result_timer=None;self.result_clock=None
        if pause:self.session.pause_result_animation()

    def sync_result(self):
        value=self.app.session.result_animation
        if self.phase!='result' or value is None or value['paused']:
            self.stop_result(pause=False);return
        if self.result_timer is None:
            self.prepare_results()
            for frame in (1,2,3):self.result_pixels.picture('ground',False,self.encounter()['losses'],frame=frame)
            if self.result_clock is None:self.result_clock=RetraceClock(time.perf_counter_ns())
            generation=self.result_generation
            self.result_timer=self.app.root.after(self.result_clock.delay_ms(time.perf_counter_ns()),
                lambda:self.app.guard(lambda:self.result_tick(generation)))

    def result_tick(self,generation):
        if generation!=self.result_generation:return
        self.result_timer=None
        if self.session is not self.app.session or self.app.screen!='ground' or not self.app.original.winfo_ismapped():
            self.stop_result();return
        if self.fade_step==5 and not self.app.pointer.buttons:
            if self.session.tick_result_animation():self.app.render_original()
        self.sync_result()

    def toggle(self):
        if self.phase=='result':
            value=self.session.result_animation
            if value is not None:
                if value['paused']:self.session.pause_result_animation(False);self.sync_result()
                else:self.stop_result()
            self.app.render_original()
        else:super().toggle()


class GroundBar(BattleBar):
    def __init__(self,app):super().__init__(app,'ground')

    def sync(self):
        super().sync()
        view=self.view
        if (view.encounter() or {}).get('phase')=='fighting':
            mode=view.encounter()['battle']['control_mode']
            if mode in (3,4):self.status.configure(text='Choose destination' if mode==3 else 'Choose enemy target')
        if (view.encounter() or {}).get('phase')=='result':
            value=view.app.session.result_animation
            self.run.configure(text='Play animation' if not value or value['paused'] else 'Pause animation',state='normal' if value else 'disabled')
