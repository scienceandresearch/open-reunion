"""Original options/hero artwork with cancellable, atomic New Game flow."""
from dataclasses import dataclass
from .original_screen import ScreenPixels


@dataclass
class StartupView:
    owner: object
    stage: str='menu'
    hero: int=2

    def targets(self):
        if self.stage=='menu':
            return [((75,y,176,h),label,('startup',action)) for y,h,label,action in
                    ((48,29,'New game','new'),(77,29,'Load game','load'),
                     (106,29,'Exit','quit'),(145,29,'Play intro','intro'))]
        if self.stage=='choose':
            return [((0,0,160,200),'Choose female hero',('hero',2)),
                    ((160,0,160,200),'Choose male hero',('hero',1))]
        return [((0,0,320,200),'Start new game',('startup','start'))]

    def draw(self,renderer):
        name='OPTIONS' if self.stage=='menu' else 'CHOISE' if self.stage=='choose' else f'HERO{self.hero}'
        target=ScreenPixels();target.blit(renderer.asset(name),0,0)
        if self.stage=='menu':
            renderer.text(target,'PLAY INTRO',130,156,color=(182,182,182),shadow=(67,67,67))
        return target

    def hint(self):
        return {'menu':'Choose New game, Load game, Play intro or Exit. Esc returns to play.',
                'choose':'Choose a hero: left or right. Esc returns to the menu.',
                'portrait':'Click or press Enter to start. Esc changes the hero.'}[self.stage]

    def dispatch(self,app,action):
        if app.session is not self.owner:return
        if action[0]=='hero':self.hero=action[1];self.stage='portrait'
        elif action==('startup','new'):self.stage='choose'
        elif action==('startup','load'):app.load();return
        elif action==('startup','intro'):
            app.intro_view.open();return
        elif action==('startup','quit'):app.close();return
        elif action==('startup','start'):app.new_game(hero=self.hero);return
        app.pointer.cancel(reset=True);app.render_original()

    def back(self,app):
        if self.stage=='menu':app.startup=None;app.show_original()
        else:
            self.stage='choose' if self.stage=='portrait' else 'menu'
            app.pointer.cancel(reset=True);app.render_original()
