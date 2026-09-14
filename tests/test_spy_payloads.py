"""Spy cargo transactions, intelligence disclosure and saved survey continuity."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest
from test_orbital import orbital_session,fleet
from openreunion.core import GameError
from openreunion.dos.fleets import payload_count
from openreunion.dos.orbital import can_deploy_spy_ship,spy_landing
from openreunion.dos.session import RecoveredSession
from openreunion.dos.worlds import FORCE_PRODUCTS,force_intelligence


def session():
    s=orbital_session()
    s.state['fleets']['moving']=[fleet(4,stock=2,offset=33),fleet(4,identity=(1,5,8),stock=3,offset=33)]
    for row in s.state['fleets']['moving']:row[35:37]=[2,0]
    raw=s.state['worlds']['1:5:1']['raw'];raw[0]=3;raw[12]=30
    return s


class SpyPayloadTests(unittest.TestCase):
    def test_alien_deployments_consume_only_preferred_cargo_across_moons(self):
        for action,offset,field,value in (('deploy_spy_satellite',33,8,2),('deploy_spy_ship',35,9,1)):
            with self.subTest(action=action):
                s=session();before=deepcopy(s.state)
                s.apply(action,world_id='1:5:1',fleet_index=1)
                expected=deepcopy(before['fleets']);expected['moving'][1][offset]-=1
                self.assertEqual(s.state['fleets'],expected)
                expected_raw=before['worlds']['1:5:1']['raw'];expected_raw[field]=value
                self.assertEqual(s.state['worlds']['1:5:1']['raw'],expected_raw)
                for key in ('resources','products','campaign','assisted'):self.assertEqual(s.state[key],before[key])

    def test_spy_ship_offer_signed_boundaries(self):
        raw=[0]*65
        for owner in (0,1,2,12,127,128,255):
            for survey in (0,29,30,60,127,128,255):
                for deployed in (0,1,255):
                    for cargo in (0,1):
                        raw[0]=owner;raw[12]=survey;raw[9]=deployed
                        self.assertEqual(can_deploy_spy_ship(raw,cargo),2<=owner<128 and 30<=survey<128 and not deployed and cargo>0)

    def test_spy_ship_prerequisites_reject_atomically(self):
        for field,value in ((0,0),(0,1),(0,255),(12,29),(12,128),(9,1)):
            s=session();s.state['worlds']['1:5:1']['raw'][field]=value;before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply('deploy_spy_ship',world_id='1:5:1')
            self.assertEqual(s.state,before)

    def test_satellite_support_gate_and_duplicate_reject(self):
        for owner,colony,mines,existing,accepted in ((0,0,0,0,True),(1,1,0,0,False),(1,0,1,0,False),
                (3,1,1,0,True),(3,0,0,1,False),(3,0,0,226,False)):
            s=session();raw=s.state['worlds']['1:5:1']['raw'];raw[0]=owner;raw[6]=colony;raw[10]=mines;raw[8]=existing
            before=deepcopy(s.state)
            if accepted:
                s.apply('deploy_spy_satellite',world_id='1:5:1');self.assertEqual(s.state['worlds']['1:5:1']['raw'][8],2)
                before=deepcopy(s.state)
            with self.assertRaises(GameError):s.apply('deploy_spy_satellite',world_id='1:5:1')
            self.assertEqual(s.state,before)

    def test_bad_stock_wrong_orbit_transit_and_selection_reject_without_writes(self):
        for kind,offset in (('spy_satellite',33),('spy_ship',35)):
            for problem in ('negative','empty','wrong_orbit','transit','invalid_selection'):
                s=session()
                for row in s.state['fleets']['moving']:
                    if problem=='negative':row[offset:offset+2]=[255,255]
                    if problem=='empty':row[offset:offset+2]=[0,0]
                    if problem=='wrong_orbit':row[20]=4
                    if problem=='transit':row[22]=4
                before=deepcopy(s.state)
                with self.assertRaises(GameError):s.apply('deploy_'+kind,world_id='1:5:1',fleet_index=99 if problem=='invalid_selection' else None)
                self.assertEqual(s.state,before)

    def test_both_payloads_run_once_only_discovery_even_on_alien_worlds(self):
        for ship in (False,True):
            raw=[0]*65;raw[0]=3;products=[{'research_state':0} for _ in range(35)]
            campaign={'rng':1994,'idea_timers':[-1]*35}
            updated,events=spy_landing(raw,(7,1,0),campaign,products,ship=ship)
            self.assertEqual(updated[9 if ship else 8],1 if ship else 2)
            self.assertEqual(events,[('message',31),('scene',6)])
            self.assertEqual([products[i]['research_state'] for i in (30,31)],[3,3])
            before=deepcopy(campaign)
            self.assertEqual(spy_landing(updated,(7,1,0),campaign,products,ship=ship)[1],[])
            self.assertEqual(campaign,before)

    def test_hidden_primary_also_blocks_moon_deployment(self):
        for action in ('deploy_spy_satellite','deploy_spy_ship'):
            s=session();s.state['campaign']['navigation']['planet_visibility'][4]=254
            before=deepcopy(s.state)
            with self.assertRaisesRegex(GameError,'Discover this planet'):s.apply(action,world_id='1:5:1')
            self.assertEqual(s.state,before)

    def test_saved_spy_satellite_surveys_and_allows_later_spy_ship(self):
        s=session();s.state['worlds']['1:5:1']['raw'][12]=29
        s.apply('deploy_spy_satellite',world_id='1:5:1')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'spy.json';s.save(path);loaded=RecoveredSession.load(s.catalog,path)
            for current in (s,loaded):
                current.apply('advance',hours=48)
                self.assertGreaterEqual(current.state['worlds']['1:5:1']['raw'][12],30)
                current.apply('deploy_spy_ship',world_id='1:5:1')
            self.assertEqual(s.state,loaded.state)
            loaded.save(path);self.assertEqual(RecoveredSession.load(s.catalog,path).state,s.state)
            self.assertEqual(payload_count(s.state['fleets'],(1,5,1),'spy_ship'),3)

    def test_force_disclosure_requires_spy_ship_or_forces_mission_not_relations_or_survey(self):
        raw=[0]*65;raw[0]=3;raw[12]=60;raw[8]=2
        civilizations=[[0]*228 for _ in range(11)];civilizations[1][19:27]=[1]*8
        raw[27:59]=struct.pack('<8I',*range(11,19))
        bar={'intelligence':[0]*12}
        self.assertIsNone(force_intelligence(raw,civilizations))
        for intel in (0,1):
            bar['intelligence'][2]=intel;self.assertIsNone(force_intelligence(raw,civilizations,bar))
        bar['intelligence'][2]=2;raw[12]=0
        expected=dict(zip(FORCE_PRODUCTS,range(11,19)))
        self.assertEqual(force_intelligence(raw,civilizations,bar),expected)
        bar['intelligence'][2]=0;raw[9]=1
        self.assertEqual(force_intelligence(raw,civilizations,bar),expected)

    def test_only_known_weapon_types_including_zero_and_unsigned_stocks(self):
        raw=[0]*65;raw[0]=12;raw[9]=1
        raw[27:59]=struct.pack('<8I',0,2**32-1,222,3,4,5,6,7)
        civilizations=[[0]*228 for _ in range(11)];civilizations[10][19:27]=[1,1,0,0,0,0,0,1]
        self.assertEqual(force_intelligence(raw,civilizations),{10:0,16:2**32-1,32:7})
        for owner in (0,1,13,127,128,255):
            raw[0]=owner;self.assertIsNone(force_intelligence(raw,civilizations))
