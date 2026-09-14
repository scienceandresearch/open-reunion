"""Research commands remain transactional while native disc effects play."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from test_campaign import session_fixture
from openreunion.dos.research_cinema import ResearchCinema
from openreunion.dos.session import RecoveredSession


class Root:
    def __init__(self):self.pending = {};self.next_id = 0
    def after(self, delay, callback):
        self.next_id += 1
        self.pending[self.next_id] = callback
        return self.next_id
    def after_cancel(self, handle):self.pending.pop(handle, None)
    def fire(self):
        handle = min(self.pending)
        self.pending.pop(handle)()


def app_fixture():
    session = session_fixture()
    for row in session.state['products']:
        row.update(research_state=0, research_remaining=10000)
    for product in (17, 23):session.state['products'][product - 1]['research_state'] = 1
    app = SimpleNamespace(root=Root(), session=session, catalog=session.catalog,
        screen='research', startup=None, pointer=SimpleNamespace(buttons=set()),
        original=SimpleNamespace(winfo_ismapped=lambda:True), research_selected=None,
        commands=[], copies=[], renders=0)
    app.screen_renderer = SimpleNamespace(asset=lambda name:name)
    target = SimpleNamespace(blit=lambda picture,x,y,source:app.copies.append((x,y,source)))
    cinema = ResearchCinema(app)
    def render():
        app.renders += 1
        cinema.draw(target)
    def act(command, **kwargs):
        app.commands.append((command, kwargs))
        app.session.apply(command, **kwargs)
        render()
    app.act = act
    app.guard = lambda callback:callback()
    app.render_original = render
    app.render_original()
    return app, cinema


def finish(app, cinema):
    ticks = 0
    while cinema.running:
        app.root.fire()
        ticks += 1
        if ticks > 100:raise AssertionError('Research transition did not finish')
    return ticks


class ResearchCinemaTests(unittest.TestCase):
    def test_start_and_switch_use_distinct_product_cells_and_commit_only_once(self):
        app, cinema = app_fixture()
        cinema.select(17)
        after_start = deepcopy(app.session.state)
        self.assertEqual(app.session.state['products'][16]['research_state'], 2)
        self.assertEqual(cinema.disc.destination_offset, 101 * 320 + 32)
        self.assertEqual(finish(app, cinema), 33)
        self.assertEqual(app.session.state, after_start)
        self.assertEqual(len(app.commands), 1)
        app.root.fire()
        self.assertEqual(cinema.spinner.source_frame_argument, 40)
        cinema.select(23)
        after_switch = deepcopy(app.session.state)
        self.assertEqual(cinema.disc.destination_offset, 101 * 320 + 32)
        self.assertEqual(cinema.disc.source_frame_argument, 19)
        self.assertEqual(finish(app, cinema), 66)
        self.assertEqual(app.session.state['products'][16]['research_state'], 1)
        self.assertEqual(app.session.state['products'][22]['research_state'], 2)
        self.assertEqual(app.session.state, after_switch)
        self.assertEqual(len(app.commands), 2)
        self.assertTrue(any((x,y)==(64,117) for x,y,_ in app.copies))

    def test_stop_and_completed_product_effect_do_not_advance_research(self):
        app, cinema = app_fixture()
        cinema.select(17);finish(app, cinema)
        cinema.select(17)
        stopped = deepcopy(app.session.state)
        self.assertEqual(finish(app, cinema), 33)
        self.assertEqual(app.session.state, stopped)
        self.assertIsNone(cinema.spinner)
        app.session.state['products'][22].update(research_state=5, research_remaining=0)
        completed = deepcopy(app.session.state)
        cinema.select(23)
        self.assertEqual(finish(app, cinema), 66)
        self.assertEqual(app.session.state, completed)
        self.assertEqual(len(app.commands), 2)

    def test_load_replacement_invalidates_queued_callback_without_touching_new_session(self):
        app, cinema = app_fixture()
        cinema.select(17)
        old_callback = next(iter(app.root.pending.values()))
        app.session = RecoveredSession(app.catalog, deepcopy(app.session.state))
        state = deepcopy(app.session.state)
        app.render_original()
        current_timer = cinema.timer
        old_callback()
        self.assertFalse(cinema.running)
        self.assertEqual(cinema.timer, current_timer)
        self.assertEqual(app.session.state, state)
        self.assertEqual(len(app.root.pending), 1)

    def test_held_input_hidden_view_departure_and_cancel_stop_visual_work(self):
        app, cinema = app_fixture()
        cinema.select(17)
        app.pointer.buttons.add(1)
        for _ in range(10):app.root.fire()
        self.assertEqual(cinema.wait, 1)
        self.assertEqual(cinema.disc.source_frame_argument, 10)
        app.pointer.buttons.clear()
        app.original.winfo_ismapped = lambda:False
        app.root.fire()
        self.assertFalse(cinema.running)
        self.assertFalse(app.root.pending)
        app.original.winfo_ismapped = lambda:True
        app.render_original()
        app.screen = 'bridge'
        app.root.fire()
        self.assertIsNone(cinema.timer)
        self.assertFalse(app.root.pending)
        self.assertEqual(len(app.commands), 1)

    def test_pause_training_block_and_skill_threshold_freeze_spinner_only(self):
        for change in ('pause', 'training', 'block', 'level', 'threshold'):
            with self.subTest(change=change):
                app, cinema = app_fixture()
                cinema.select(17);finish(app, cinema)
                state = app.session.state
                if change == 'pause':state['research_paused'] = True
                elif change == 'training':state['campaign']['training_role'] = 4
                elif change == 'block':state['campaign']['research_block_remaining'] = 1
                elif change == 'level':state['levels']['developer'] = 0
                else:state['products'][16]['research_remaining'] = cinema.guard().threshold
                before = deepcopy(state)
                app.render_original()
                for _ in range(8):app.root.fire()
                self.assertIsNone(cinema.spinner)
                self.assertEqual(app.session.state, before)

    def test_story_redirect_after_research_command_does_not_start_hidden_sequence(self):
        app, cinema = app_fixture()
        original_act = app.act
        def redirect(command, **kwargs):
            original_act(command, **kwargs)
            app.screen = 'dialog'
        app.act = redirect
        cinema.select(17)
        self.assertFalse(cinema.running)
        self.assertIsNone(cinema.timer)
        self.assertEqual(len(app.commands), 1)


if __name__ == '__main__':unittest.main()
