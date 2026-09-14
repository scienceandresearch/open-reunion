"""Read-only race rendering preserves disclosure and exact unsigned stocks."""
from copy import deepcopy
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from openreunion.dos.race_screen import RaceView


def fixture():
    raw=[0]*65;raw[0]=2;raw[12]=40
    raw[27:59]=list(struct.pack('<8I',4294967295,876543210,0,0,0,0,0,0))
    civilization=[0]*228;civilization[19:22]=[1,0,1]
    state={'worlds':{'w':{'raw':raw}},'campaign':{'civilizations':[civilization],
        'bar':{'intelligence':[0]*12}}}
    session=SimpleNamespace(state=state)
    renderer=SimpleNamespace(frame=Mock(return_value=SimpleNamespace(blit=Mock())),
        path_asset=Mock(),text=Mock(),content=SimpleNamespace(text=lambda _:['Profile']*144,
        catalog={'products':[{'name':f'Weapon {i}'} for i in range(1,36)]}))
    return session,RaceView(session,'w'),renderer


class RaceScreenTests(unittest.TestCase):
    def test_rendered_intelligence_is_gated_and_exact_without_mutating_state(self):
        session,view,renderer=fixture()
        def draw():
            renderer.text.reset_mock();before=deepcopy(session.state)
            view.draw(renderer,session.state,'Planet',[24],0)
            self.assertEqual(session.state,before)
            return [call.args[1] for call in renderer.text.call_args_list]
        view.details=True
        self.assertFalse(any('Weapon' in text for text in draw()))
        session.state['campaign']['bar']['intelligence'][1]=2
        texts=draw()
        self.assertIn('4294967295',texts)
        self.assertIn('Weapon 10',texts)
        self.assertIn('Weapon 23',texts)
        self.assertNotIn('Weapon 16',texts)
        self.assertNotIn(' 876543210',texts)
        self.assertIn('         0',texts)
        session.state['campaign']['bar']['intelligence'][1]=0
        self.assertFalse(any('Weapon' in text for text in draw()))
        view.sync(session.state);self.assertFalse(view.details)

    def test_view_does_not_transfer_to_another_session_world_or_owner(self):
        session,view,_=fixture()
        self.assertTrue(view.current(session,'w'))
        self.assertFalse(view.current(SimpleNamespace(state=deepcopy(session.state)),'w'))
        self.assertFalse(view.current(session,'other'))
        raw=session.state['worlds']['w']['raw']
        raw[0]=3;self.assertFalse(view.current(session,'w'))
        raw[0]=2;raw[12]=128;self.assertFalse(view.current(session,'w'))


if __name__=='__main__':unittest.main()
