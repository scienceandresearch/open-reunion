from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from test_orbital import orbital_session,fleet
from openreunion.core import GameError
from openreunion.dos.orbital import survey_landing
from openreunion.dos.session import RecoveredSession


def session():
    s=orbital_session();s.state['fleets']['moving']=[fleet(4,stock=2,offset=31),fleet(4,stock=3,offset=31)]
    s.state['campaign']['carrier_failure_reported']=True
    return s


class CarrierSurveyTests(unittest.TestCase):
    def test_launch_after_direct_failure_consumes_preferred_carrier_only(self):
        s=session();before=deepcopy(s.state)
        s.apply('deploy_survey_satellite',world_id='1:5:1',fleet_index=1)
        self.assertEqual(s.state['worlds']['1:5:1']['raw'][8],1)
        self.assertEqual(s.state['fleets']['moving'][0],before['fleets']['moving'][0])
        expected=before['fleets']['moving'][1];expected[31]=2
        self.assertEqual(s.state['fleets']['moving'][1],expected)
        self.assertEqual(s.state['products'],before['products'])
        self.assertEqual(s.state['campaign'],before['campaign'])

    def test_transit_support_and_wrong_orbit_reject_atomically(self):
        for field,value in ((8,226),(8,1),(6,1),(10,1)):
            s=session();s.state['worlds']['1:5:1']['raw'][field]=value;before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply('deploy_survey_satellite',world_id='1:5:1')
            self.assertEqual(s.state,before)
        s=session()
        for row in s.state['fleets']['moving']:row[20]=4
        before=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply('deploy_survey_satellite',world_id='1:5:1')
        self.assertEqual(s.state,before)

    def test_negative_payload_and_invalid_selection_preserve_state(self):
        for change in (lambda s:s.state['fleets']['moving'][0].__setitem__(slice(31,33),[255,255]),lambda s:None):
            s=session();change(s);before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply('deploy_survey_satellite',world_id='1:5:1',fleet_index=99)
            self.assertEqual(s.state,before)
        s=session();s.state['fleets']['moving'][0][31:33]=[255,255];before=deepcopy(s.state)
        with self.assertRaises(GameError):s.apply('deploy_survey_satellite',world_id='1:5:1')
        self.assertEqual(s.state,before)

    def test_alien_world_consumes_satellite_and_reports_loss_without_survey(self):
        s=session();s.state['worlds']['1:5:1']['raw'][0]=2
        before=s.state['fleets']['moving'][0][31]
        s.apply('deploy_survey_satellite',world_id='1:5:1')
        self.assertEqual(s.state['worlds']['1:5:1']['raw'][8],0)
        self.assertEqual(s.state['fleets']['moving'][0][31],before-1)
        self.assertIn('lost at alien-controlled',s.state['log'][-1])

    def test_special_site_reward_and_timer_are_once_only(self):
        raw=[0]*65;products=[{'research_state':0} for _ in range(35)]
        campaign={'rng':1994,'idea_timers':[-1]*35}
        updated,landed,events=survey_landing(raw,(7,1,0),campaign,products)
        self.assertTrue(landed);self.assertEqual(updated[8],1)
        self.assertEqual(events,[('message',31),('scene',6)])
        self.assertEqual([products[i]['research_state'] for i in (30,31)],[3,3])
        before=deepcopy(campaign)
        self.assertEqual(survey_landing(raw,(7,1,0),campaign,products)[2],[])
        self.assertEqual(campaign,before)

    def test_saved_satellite_continues_daily_survey(self):
        s=session();s.apply('deploy_survey_satellite',world_id='1:5:1')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'survey.json';s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            before=s.state['worlds']['1:5:1']['raw'][12]
            s.apply('advance',hours=48);loaded.apply('advance',hours=48)
            self.assertEqual(s.state,loaded.state)
            self.assertGreater(s.state['worlds']['1:5:1']['raw'][12],before)
