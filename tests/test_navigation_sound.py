"""Original cockpit navigation samples and their transient ownership."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from openreunion.core import GameError
from openreunion.dos.effect_control import initial_effects
from openreunion.dos.effect_output import EffectOutput
from openreunion.dos.navigation_sound import NavigationSound
from openreunion.dos.original_ui import OriginalApp


class Player:
    def __init__(self):
        self.playing=False;self.paused=False;self.completed=False;self.error=None
        self.frames=0;self.starts=[];self.pauses=[];self.stops=0
    def start(self,sample,**kwargs):
        self.starts.append(sample);self.frames=kwargs.get('frames',0);self.playing=True;self.completed=False
    def pause(self,value):
        self.pauses.append(value);self.paused=value
    def position(self):return self.frames
    def stop(self):self.stops+=1;self.playing=False


class Root:
    def __init__(self):self.callbacks={};self.cancelled=[]
    def after(self,delay,callback):
        key=len(self.callbacks)+1;self.callbacks[key]=callback;return key
    def after_cancel(self,key):self.cancelled.append(key);self.callbacks.pop(key,None)


class NavigationSoundTests(unittest.TestCase):
    def app(self):
        session=SimpleNamespace(effects=initial_effects(),effect_revision=4)
        background=Player();voice=object()
        effects=SimpleNamespace(player=background,_session=session,_revision=4,_voice=voice)
        return SimpleNamespace(session=session,screen='cockpit',root=Root(),effects=effects,
            content=SimpleNamespace(sample=Mock(side_effect=lambda name:name)),
            status=SimpleNamespace(set=Mock()))

    def sound(self,app):
        with patch('openreunion.dos.navigation_sound.SamplePlayer',Player):return NavigationSound(app)

    def test_natural_completion_and_screen_departure_restore_saved_voice(self):
        app=self.app();app.effects.player.playing=True;sound=self.sound(app)
        self.assertTrue(sound.start('BASEEFF','fleets'))
        self.assertEqual(app.content.sample.call_args.args,('BASEEFF',))
        self.assertEqual(app.effects.player.pauses,[True]);self.assertTrue(sound.retain('fleets'))
        app.screen='fleets';sound.player.completed=True;sound.player.playing=False;sound.poll()
        self.assertEqual(app.effects.player.pauses,[True,False]);self.assertFalse(sound.active)

        app.screen='cockpit';app.effects.player.playing=True
        sound.start('GROUP','equipment');app.screen='bridge';sound.poll()
        self.assertEqual(app.effects.player.pauses[-2:],[True,False]);self.assertFalse(sound.active)

    def test_replacement_voice_and_loaded_session_are_never_unpaused_as_stale_audio(self):
        app=self.app();app.effects.player.playing=True;sound=self.sound(app)
        sound.start('CPANEL','cockpit');app.effects._revision+=1;app.effects._voice=object()
        sound.cancel()
        self.assertEqual(app.effects.player.pauses,[True])

        app.effects.player.pause(False);app.effects.player.playing=True
        sound.start('CPANEL','cockpit');app.session=SimpleNamespace(effects=initial_effects(),effect_revision=0)
        sound.cancel()
        self.assertEqual(app.effects.player.pauses[-2:],[False,True])

    def test_disabled_missing_and_failed_samples_do_not_block_navigation(self):
        app=self.app();app.session.effects['enabled']=False;sound=self.sound(app)
        self.assertFalse(sound.start('BASEEFF','fleets'));app.content.sample.assert_not_called()

        app.session.effects['enabled']=True
        app.content.sample.side_effect=GameError('missing BASEEFF')
        self.assertFalse(sound.start('BASEEFF','fleets'))
        app.status.set.assert_called_with('Sound effect unavailable: missing BASEEFF')

        app.content.sample.side_effect=lambda name:name
        sound.start('GROUP','equipment');app.screen='equipment';sound.player.error='device lost';sound.poll()
        app.status.set.assert_called_with('Sound effect unavailable: device lost')
        self.assertFalse(sound.active)

    def test_new_effect_revision_cancels_navigation_before_numbered_prepare(self):
        app=self.app();app.refresh_listeners=[];app.root.bind=lambda *a,**k:None
        app.effects=None
        with patch('openreunion.dos.effect_output.SamplePlayer',Player):output=EffectOutput(app)
        self.addCleanup(output.close);app.effects=output
        prior=dict(initial_effects(),sample='WARSND1')
        app.session.effects=prior;output._voice=prior;output._started=True
        output.player.playing=True;output.player.frames=73
        sound=self.sound(app);app.navigation_sound=sound
        sound.start('CPANEL','cockpit')
        app.session.effects=dict(initial_effects(),sample='WARSND2')
        app.session.effect_revision+=1
        app.content.sample.side_effect=GameError('missing numbered voice')
        output.sync()
        self.assertFalse(sound.active)
        self.assertFalse(output.player.paused,'The surviving voice must be restored before failed replacement capture')
        self.assertEqual(app.session.effects,dict(initial_effects(),sample='WARSND1',frames=73))

    def test_disable_cancels_navigation_immediately_without_restoring_old_voice(self):
        app=self.app();app.refresh_listeners=[];app.root.bind=lambda *a,**k:None
        with patch('openreunion.dos.effect_output.SamplePlayer',Player):output=EffectOutput(app)
        self.addCleanup(output.close);app.effects=output
        navigation=self.sound(app);app.navigation_sound=navigation
        navigation.start('BASEEFF','fleets');self.assertTrue(navigation.active)
        output.set_enabled(False)
        self.assertFalse(navigation.active);self.assertGreater(navigation.player.stops,0)


class NavigationRouteTests(unittest.TestCase):
    def test_cockpit_buttons_use_only_the_two_traced_forward_samples(self):
        app=SimpleNamespace(selected_cockpit_fleet=Mock(return_value=[0]*40),
            cockpit_view=SimpleNamespace(index=3),open_fleets=Mock(),open_equipment=Mock())
        OriginalApp.cockpit_action(app,'cockpit_fleets')
        app.open_fleets.assert_called_once_with('moving',3,navigation_sound='BASEEFF')
        OriginalApp.cockpit_action(app,'cockpit_equipment')
        app.open_equipment.assert_called_once_with('moving',3,navigation_sound='GROUP')

    def returning(self,screen):
        app=SimpleNamespace(screen=screen,startup=None,cockpit_cinema=SimpleNamespace(running=False),
            open_cockpit=Mock())
        if screen=='fleets':
            app.fleet_view=SimpleNamespace(bank='moving',selected={'moving':2})
            app.selected_overview_fleet=Mock(return_value=[0]*40)
        elif screen=='equipment':
            app.equipment_view=SimpleNamespace(bank='moving',index=4)
            app.selected_equipment_fleet=Mock(return_value=[0]*40)
        else:
            app.cargo_view=SimpleNamespace(index=5);app.selected_cargo_fleet=Mock(return_value=[0]*40)
        OriginalApp.dispatch(app,16);return app

    def test_cpanel_return_is_limited_to_traced_ships_and_group_screens(self):
        self.returning('fleets').open_cockpit.assert_called_once_with(2,navigation_sound='CPANEL')
        self.returning('equipment').open_cockpit.assert_called_once_with(4,navigation_sound='CPANEL')
        self.returning('cargo').open_cockpit.assert_called_once_with(5,navigation_sound=None)

    def test_cpanel_starts_after_cockpit_commit_before_render_and_skips_redirect(self):
        def app(active=False):
            current={'presentation_requests':[],'active_scene':None,'active_dialog':None,
                'space_encounter':None,'ground_encounter':None,'campaign_phase':'starmap'}
            mock=Mock();mock.startup=None;mock.screen='equipment';mock.session.state=current
            mock.cockpit_cinema.handoff=False;mock.bar_view.active=False
            for name in ('dialog','scene','space','ground','adviser','victory','defeat'):
                getattr(mock,name+'_view').active=False
            mock.bar_view.active=False;mock.clock_bar_height=0
            if active:mock.dialog_view.active=True
            return mock
        normal=app();order=[]
        normal.navigation_sound.start.side_effect=lambda *args:order.append(('start',normal.screen,args))
        normal.render_original.side_effect=lambda:order.append(('render',normal.screen))
        OriginalApp.show_original(normal,'cockpit',navigation_sound='CPANEL')
        self.assertEqual(order,[('start','cockpit',('CPANEL','cockpit')),('render','cockpit')])

        redirected=app(active=True)
        OriginalApp.show_original(redirected,'cockpit',navigation_sound='CPANEL')
        self.assertEqual(redirected.screen,'dialog');redirected.navigation_sound.start.assert_not_called()


if __name__=='__main__':unittest.main()
