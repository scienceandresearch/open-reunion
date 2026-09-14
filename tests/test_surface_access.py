"""Surface viewing cannot grant construction or disclose unscanned structures."""
from copy import deepcopy
import unittest
from test_surface import surface_session
from test_colony import building
from openreunion.core import GameError
from openreunion.dos.surface import surface_revealed
from openreunion.dos.surface_screen import SurfaceView,local_group,surface_buttons


def viewing_session():
    session=surface_session()
    definition=deepcopy(next(w for w in session.catalog['worlds'] if w['id']=='1:5:0'))
    definition.update(id='1:6:0',planet=6,name='Viewing fixture')
    session.catalog['worlds'].append(definition)
    session.state['worlds']['1:6:0']=deepcopy(session.state['worlds']['1:5:0'])
    return session


class SurfaceAccessTests(unittest.TestCase):
    def test_spaceport_requires_matching_owned_colony_group(self):
        session=viewing_session();state=session.state
        row=[0]*161;row[0]=5;row[19:23]=[1,6,0,7]
        state['fleets']['local']=[row[:],row[:]]
        self.assertEqual(local_group(state,'1:6:0'),1)
        self.assertEqual(surface_buttons(state,'1:6:0'),[24,46,9,43,66])
        state['worlds']['1:6:0']['raw'][6]=0
        self.assertEqual(surface_buttons(state,'1:6:0'),[24,46,9,43])
        state['worlds']['1:6:0']['raw'][6]=1
        state['worlds']['1:6:0']['raw'][0]=2
        self.assertNotIn(66,surface_buttons(state,'1:6:0'))
        state['worlds']['1:6:0']['raw'][0]=1
        for row in state['fleets']['local']:row[20]=5
        self.assertIsNone(local_group(state,'1:6:0'))
        self.assertNotIn(66,surface_buttons(state,'1:6:0'))

    def test_unscanned_foreign_surface_does_not_place_hidden_buildings(self):
        session=viewing_session();raw=session.state['worlds']['1:6:0']['raw']
        raw[0]=2;raw[6]=0;raw[8]=226;raw[9]=raw[10]=0;raw[12]=60
        row=building(4);row[1:6]=[1,6,0,255,255];session.state['buildings']=[row]
        before=deepcopy(session.state)
        session.apply('prepare_surface',world_id='1:6:0')
        self.assertEqual(session.state,before)
        view=SurfaceView(world_id='1:6:0');view.sync(session.state,session.catalog)
        self.assertEqual(view.targets(),[])
        self.assertFalse(surface_revealed(raw))
        session.state['worlds']['1:6:0']['raw'][8]=2
        session.apply('prepare_surface',world_id='1:6:0')
        self.assertNotIn(255,session.state['buildings'][0][4:6])
        view.sync(session.state,session.catalog)
        self.assertTrue(view.revealed)
        self.assertFalse(view.editable)
        self.assertFalse(view.inspectable)
        self.assertTrue(all(t[2][0] in ('surface_pan','surface_radar') for t in view.targets()))
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply('build',world_id='1:6:0',building_id=4,x=6,y=6)
        with self.assertRaises(GameError):session.apply('demolish',world_id='1:6:0',building_index=0)
        self.assertEqual(session.state,before)

    def test_station_is_visible_and_inspectable_but_not_a_colony_editor(self):
        session=viewing_session();raw=session.state['worlds']['1:6:0']['raw']
        raw[0]=1;raw[6]=0;raw[10]=1;raw[8]=raw[9]=0
        session.apply('prepare_surface',world_id='1:6:0')
        view=SurfaceView(world_id='1:6:0');view.sync(session.state,session.catalog)
        self.assertTrue(view.revealed and view.inspectable)
        self.assertFalse(view.editable)
        self.assertFalse(any(t[2][0]=='surface_mode' for t in view.targets()))
        self.assertTrue(any(t[2][0]=='surface_tile' for t in view.targets()))

    def test_alien_base_marker_is_presentation_only(self):
        session=viewing_session();raw=session.state['worlds']['1:6:0']['raw']
        raw[0]=2;raw[8]=2;raw[6]=0
        view=SurfaceView(world_id='1:6:0');view.sync(session.state,session.catalog)
        before=deepcopy(session.state);overlays=view.overlays(session.state,session.catalog)
        self.assertTrue(overlays)
        self.assertTrue(all(index is None for tile,index in overlays.values()))
        self.assertEqual(session.state,before)
        raw[8]=0;self.assertEqual(view.overlays(session.state,session.catalog),{})

    def test_hidden_world_is_rejected_and_lost_signal_cancels_modes(self):
        session=viewing_session();view=SurfaceView(world_id='1:6:0',mode='build')
        raw=session.state['worlds']['1:6:0']['raw'];raw[0]=0;raw[6]=raw[10]=raw[8]=raw[9]=0
        view.sync(session.state,session.catalog)
        self.assertEqual(view.mode,'inspect')
        session.state['campaign']['navigation']['planet_visibility'][5]=128
        before=deepcopy(session.state)
        with self.assertRaisesRegex(GameError,'discovered'):session.apply('prepare_surface',world_id='1:6:0')
        self.assertEqual(session.state,before)


if __name__=='__main__':unittest.main()
