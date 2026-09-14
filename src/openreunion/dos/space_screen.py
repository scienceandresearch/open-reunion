"""Original space radar/cinematics/results in the main framebuffer."""
from ..core import GameError
from .space_pixels import SpacePixels
from .battle_samples import SPACE_SAMPLES
from .control_layouts import result_control_enabled
from .battle_screen import BattleScreen,BattleBar
from .battle_identity import space_notice,space_opponents


class SpaceScreen(BattleScreen):
    family='space'
    samples=SPACE_SAMPLES

    def enabled(self, action):
        phase=(self.encounter() or {}).get('phase')
        return (action==62 and phase=='fighting' or action==65 and self.fade_step==5
                and result_control_enabled(self.app.catalog,phase))


    def draw(self):
        encounter=self.encounter()
        if not self.active:raise GameError('There is no active space battle.')
        if self.pixels is None:self.pixels=SpacePixels(self.app.content,self.app.catalog['space_presentation'])
        result=None if encounter['phase']=='fighting' else encounter['player_won']
        cinema=encounter.get('cinema')
        body=self.pixels.ppm(encounter['radar'],result=result,
            losses=encounter['losses'] if result is not None else None,
            cinema=cinema['view'] if cinema else None,fade_step=self.fade_step)
        name='Vs '+space_opponents(self.app.session.state,self.app.catalog,encounter)
        return self.app.screen_renderer.battle(self.app.session.state,body,
            29 if result is None else 30,self.app.caption or name)


    def tick(self):
        if (self.encounter() or {}).get('phase')!='fighting':return
        self.app.session.apply('space_tick',render=True);self.app.effects.sync();self.sync()
        if self.phase=='result':self.app.refresh()
        else:self.app.render_original()


    def dispatch(self, action):
        if not self.enabled(action):return
        self.pause()
        self.app.act('space_retreat' if action==62 else 'space_acknowledge')



class SpaceBar(BattleBar):
    def __init__(self,app):super().__init__(app,'space')

    def sync(self):
        super().sync()
        self.notice.configure(text=space_notice(self.app.session.state,self.app.catalog,self.view.encounter()))
