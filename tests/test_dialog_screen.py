"""Conversation presentation stages cannot repeat transactional answers."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_story_session import scripted
from openreunion.dos.dialog_screen import DialogScreen,text_lines,choice_rows
from openreunion.dos.control_input import PanelPress
from openreunion.dos.session import RecoveredSession


def fixture():
    session=scripted();definition=session.catalog['dialogs']['2']
    definition['nodes']=[[1],[1],[4,5]];definition['answers'][0]['next']=2
    session.state['presentation_requests']=[{'kind':'dialog','id':2}];session.apply('start_presentation')
    app=SimpleNamespace(session=session,catalog=session.catalog,pointer=PanelPress(),render_original=Mock(),act=Mock())
    view=DialogScreen(app);view.sync();return app,view


class DialogScreenTests(unittest.TestCase):
    def test_answer_is_read_before_choices_and_continue_does_not_repeat_it(self):
        app,view=fixture();self.assertFalse(view.reading)
        app.session.apply('dialog_answer',question=1);view.sync();self.assertTrue(view.reading)
        before=deepcopy(app.session.state);view.dispatch(('dialog_choice',4));app.act.assert_not_called()
        view.dispatch(('dialog_continue',));self.assertFalse(view.reading)
        self.assertEqual(app.session.state,before);app.act.assert_not_called()
        view.dispatch(('dialog_choice',4));app.act.assert_called_once_with('dialog_answer',question=4)

    def test_load_identical_state_restores_answer_and_cancels_held_choice(self):
        app,view=fixture();app.session.apply('dialog_answer',question=1);view.sync();view.dispatch(('dialog_continue',))
        app.pointer.press(1,21,True);app.session=RecoveredSession(app.catalog,deepcopy(app.session.state));view.sync()
        self.assertTrue(view.reading);self.assertFalse(app.pointer.buttons)

    def test_terminal_continue_dispatches_acknowledgement_once_per_state(self):
        app,view=fixture();app.session.apply('dialog_answer',question=1);app.session.apply('dialog_answer',question=4);view.sync()
        self.assertTrue(view.current()['closed']);view.dispatch(('dialog_continue',))
        app.act.assert_called_once_with('dialog_acknowledge')

    def test_wrapped_overflow_preserves_full_text_and_scrolling_invalidates_input(self):
        text='A'*37+'\nEnd';lines=text_lines(text)
        self.assertEqual(''.join(lines),'A'*37+'End');self.assertTrue(all(len(s)<=36 for s in lines))
        app,view=fixture();app.catalog['dialogs']['2']['questions'][0]['text']='\n'.join(str(i) for i in range(10))
        self.assertEqual(len(view.rows()),10);self.assertEqual(len(view.targets()),7)
        app.pointer.press(1,21,True);view.scroll(3)
        self.assertFalse(app.pointer.buttons);self.assertEqual(view.offset,3);self.assertEqual(view.rows()[view.offset][1],'3')
