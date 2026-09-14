"""Discovery presentation delivery and delayed landing callback ownership."""
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from openreunion.dos.ui import RecoveredApp
from openreunion.dos.original_ui import OriginalApp
from openreunion.dos.cockpit_cinema import CockpitCinema


def state():
    return {'assisted':False,'presentation_requests':[],'active_scene':None,
            'active_dialog':None,'space_encounter':None,'ground_encounter':None}


class DiscoveryHandoffTests(unittest.TestCase):
    def app(self):
        current=state()
        def apply(action,**kwargs):
            current['presentation_requests'].append({'kind':'scene','id':4})
            return [{'kind':'scene','id':4}]
        return SimpleNamespace(session=SimpleNamespace(state=current,apply=Mock(side_effect=apply)),
            admin=SimpleNamespace(get=lambda:False),refresh=Mock(),effects=SimpleNamespace(error=None,warning=None),
            status=SimpleNamespace(set=Mock()),show_presentation=Mock(),show_space_battle=Mock(),show_ground_battle=Mock())

    def test_landing_and_satellite_discoveries_open_the_pending_story(self):
        for action in ('orbit','deploy_survey_satellite','deploy_spy_satellite'):
            with self.subTest(action=action):
                app=self.app();RecoveredApp.act(app,action,fleet_index=0)
                app.show_presentation.assert_called_once_with()
                app.session.apply.assert_called_once_with(action,fleet_index=0)

    def test_cockpit_can_defer_delivery_without_changing_the_game_command(self):
        app=self.app();RecoveredApp.act(app,'orbit',fleet_index=0,defer_presentation=True)
        app.show_presentation.assert_not_called();app.refresh.assert_called_once_with()
        app.session.apply.assert_called_once_with('orbit',fleet_index=0)
        self.assertEqual(app.session.state['presentation_requests'],[{'kind':'scene','id':4}])

    def cinema(self):
        callbacks={}
        def after(delay,callback):callbacks[len(callbacks)+1]=callback;return len(callbacks)
        app=SimpleNamespace(session=object(),screen='cockpit',cockpit_view=SimpleNamespace(index=0),
            root=SimpleNamespace(after=after,after_cancel=lambda key:callbacks.pop(key,None)),
            render_original=Mock(),guard=lambda callback:callback(),status=SimpleNamespace(set=Mock()))
        cinema=CockpitCinema(app);cinema.owner=app.session;cinema.index=0
        cinema.frames=(object(),);cinema.duration=0;cinema.origin=time.perf_counter_ns()
        cinema.player=SimpleNamespace(playing=True,completed=False,error=None,stop=Mock())
        cinema.on_complete=Mock();return app,cinema,callbacks,cinema.on_complete

    def test_story_waits_for_landing_sound_and_is_delivered_once(self):
        app,cinema,callbacks,delivered=self.cinema();cinema.tick()
        self.assertFalse(cinema.running);delivered.assert_not_called()
        self.assertEqual(len(callbacks),1)
        cinema.player.completed=True;next(iter(callbacks.values()))()
        delivered.assert_called_once_with();self.assertIsNone(cinema.owner)
        cinema.tick();delivered.assert_called_once_with()

    def test_loading_another_session_discards_delayed_landing_story(self):
        app,cinema,callbacks,delivered=self.cinema();cinema.tick()
        app.session=object();cinema.player.completed=True;next(iter(callbacks.values()))()
        delivered.assert_not_called();self.assertIsNone(cinema.owner)
        cinema.player.stop.assert_called_once_with()

    def test_back_cannot_leave_a_landing_story_stranded(self):
        app=self.app();app.session.state['presentation_requests']=[{'kind':'scene','id':4}]
        app.startup=None;app.cockpit_cinema=SimpleNamespace(handoff=False,cancel=Mock())
        app.disk_cinema=SimpleNamespace(cancel=Mock())
        app.bar_view=SimpleNamespace(active=False)
        OriginalApp.show_original(app)
        app.cockpit_cinema.cancel.assert_called_once_with();app.show_presentation.assert_called_once_with()

    def test_notice_and_deferred_dialog_render_without_restarting_presentation(self):
        for kind,phase,bar_active,expected_screen in (
                ('message','starmap',False,'scene'),
                ('report','starmap',False,'scene'),
                ('civilization_destroyed','starmap',False,'scene'),
                ('dialog','victory',False,'bridge'),
                ('scene','starmap',True,'bar')):
            with self.subTest(kind=kind,phase=phase,bar_active=bar_active):
                app=Mock();app.startup=None;app.cockpit_cinema.handoff=False
                app.session.state=state();app.session.state['campaign_phase']=phase
                app.session.state['presentation_requests']=[{'kind':kind,'id':14}]
                for view in ('dialog','scene','space','ground','bar','adviser','victory','defeat'):
                    getattr(app,view+'_view').active=False
                app.scene_view.active=expected_screen=='scene';app.bar_view.active=bar_active
                app.clock_bar_height=0
                OriginalApp.show_original(app)
                app.show_presentation.assert_not_called()
                self.assertEqual(app.screen,expected_screen)
                app.render_original.assert_called_once_with()


if __name__=='__main__':unittest.main()
