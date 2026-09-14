"""Intro playback lifecycle and incremental renderer stay campaign-independent."""
from copy import deepcopy
import struct
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest

from openreunion.dos.assets import Picture
from openreunion.dos.intro_cinema import Film,Shot
from openreunion.dos.intro_screen import IntroScreen
from openreunion.dos.startup_screen import StartupView


class Scheduler:
    def __init__(self):self.jobs={};self.index=0
    def after(self,delay,callback):
        self.index+=1;self.jobs[self.index]=callback;return self.index
    def after_cancel(self,key):self.jobs.pop(key,None)


def fixture():
    session=SimpleNamespace(state={'sentinel':[1,2,3]},audio=None)
    app=SimpleNamespace(session=session,screen='intro',root=Scheduler(),content=Mock(),
        original=SimpleNamespace(winfo_ismapped=lambda:True),render_original=Mock(),
        guard=lambda fn:fn(),clock_panel=SimpleNamespace(clock=Mock()))
    app.show_original=lambda screen='bridge':setattr(app,'screen',screen)
    app.open_startup=Mock()
    view=IntroScreen(app);view.music=Mock();return app,view


class IntroScreenTests(unittest.TestCase):
    def test_startup_exposes_intro_without_replacing_menu_before_open_succeeds(self):
        owner=object();view=StartupView(owner);app=SimpleNamespace(session=owner,startup=view,intro_view=Mock())
        self.assertIn(('startup','intro'),[action for _,_,action in view.targets()])
        self.assertEqual(view.targets()[2][2],('startup','quit'))
        # Nonblack pixel bounds from the original OPTIONS artwork plus the
        # native-font intro label must each lie wholly inside one hit target.
        bands=((100,56,225,69,('startup','new')),
               (95,85,230,98,('startup','load')),
               (86,113,239,127,('startup','quit')),
               (130,156,188,163,('startup','intro')))
        for left,top,right,bottom,action in bands:
            matching=[]
            for (x,y,width,height),_,candidate in view.targets():
                if x<=left and right<x+width and y<=top and bottom<y+height:
                    matching.append(candidate)
            self.assertEqual(matching,[action])
        view.dispatch(app,('startup','intro'))
        app.intro_view.open.assert_called_once_with();self.assertIs(app.startup,view)

    def test_startup_draws_visible_intro_label_below_original_exit(self):
        renderer=Mock();renderer.asset.return_value=Picture(320,200,bytes(64000),bytes(768))
        StartupView(object()).draw(renderer)
        renderer.text.assert_called_once_with(unittest.mock.ANY,'PLAY INTRO',130,156,
            color=(182,182,182),shadow=(67,67,67))

    def test_muted_play_pause_replay_and_stale_callback_preserve_campaign(self):
        app,view=fixture();before=deepcopy(app.session.state)
        film=Film(((0,Shot()),(1_000_000_000,Shot())),2_000_000_000,((0,'INTRO1'),),1995)
        with patch('openreunion.dos.intro_screen.timeline',return_value=film),patch.object(view,'prepare'):
            view.open()
        self.assertTrue(view.running);old=app.root.jobs[view.timer]
        with patch('openreunion.dos.intro_screen.time.perf_counter_ns',return_value=view.wall_start+500_000_000):view.pause()
        self.assertEqual(view.elapsed,500_000_000)
        view.play();current=view.timer;old();self.assertEqual(view.timer,current)
        del view.songs
        view.replay();self.assertEqual((view.position,view.elapsed),(0,0))
        self.assertEqual(app.session.state,before);view.close();self.assertEqual(app.root.jobs,{})

    def test_input_aborts_midfilm_and_repeats_at_final_gate(self):
        app,view=fixture();view.owner=app.session;view.opened=True;view.entries=(Shot(),);view.starts=(0,)
        view.input();app.open_startup.assert_called_once_with()
        app.open_startup.reset_mock();view.position=1
        with patch.object(view,'replay') as replay:view.input();replay.assert_called_once_with()
        app.open_startup.assert_not_called()

    def test_renderer_applies_picture_then_original_animation_payload(self):
        app,view=fixture();palette=bytes(range(256))*3
        app.content.intro_picture.return_value=Picture(320,200,bytes([1])*64000,palette)
        raw=b'SpidyAnim'+struct.pack('<HH',320,200)+b'\xc0'+struct.pack('<H',64000)+b'\2'
        app.content.intro_animation.return_value=(raw,)
        view.entries=(Shot(('picture','PAL20')),Shot(('animation',1,1,1,False,False)))
        view.position=1
        picture=view.draw()
        self.assertEqual(picture.pixels,bytes([2])*64000)
        self.assertEqual(view.rendered_position,1)

    def test_show_loaded_fetches_attack_instead_of_reusing_old_pal1(self):
        app,view=fixture();palette=bytes(range(256))*3
        pal1=Picture(320,200,bytes([1])*64000,palette)
        attack=Picture(320,200,bytes([2])*64000,palette)
        app.content.intro_picture.side_effect=lambda name:{'PAL1':pal1,'ATTACK':attack}[name]
        view.apply(Shot(('load','PAL1')))
        view.apply(Shot(('show_loaded','ATTACK')))
        self.assertIs(view.loaded,attack)
        self.assertEqual(view.picture.pixels,attack.pixels)
        self.assertEqual(app.content.intro_picture.call_args_list,
                         [unittest.mock.call('PAL1'),unittest.mock.call('ATTACK')])


if __name__=='__main__':unittest.main()
