"""Deployment editing, cancellation, saved continuation and original targeting."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from test_strategy_session import battle_session
from test_space_session import prepared,finish_space
from openreunion.dos.aliens import store_fleet
from openreunion.core import GameError
from openreunion.dos.ground_setup_screen import setup_buttons,setup_targets,setup_signature,group_report
from openreunion.dos.session import RecoveredSession


class GroundSetupScreenTests(unittest.TestCase):
    def test_cancel_after_space_victory_keeps_applied_space_casualties(self):
        session=prepared();finish_space(session);session.apply('space_acknowledge')
        before=deepcopy(session.state);session.apply('ground_cancel')
        expected=deepcopy(before);expected['ground_encounter']=None;expected['campaign_phase']='starmap'
        self.assertEqual(session.state,expected)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'after-space.json';session.save(path)
            self.assertEqual(RecoveredSession.load(session.catalog,path).state,session.state)

    def test_cancel_dispatches_waiting_defense_without_advancing_campaign_hour(self):
        session=prepared();finish_space(session);session.apply('space_acknowledge')
        civ=session.state['campaign']['civilizations'][2];civ[27]=2;civ[38]=1
        row=[0]*27;row[0]=2;row[2]=1;row[8:11]=[1,5,0];row[11]=3;store_fleet(civ,1,row)
        session.state['battle_requests']=[{'race':4,'slot':1,'world':[1,5,0],'ground':True,'special':False}]
        date=session.state['date'][:];session.apply('ground_cancel')
        self.assertIsNone(session.state['ground_encounter']);self.assertEqual(session.state['battle_requests'],[])
        self.assertEqual(session.state['space_encounter']['destination'],[1,5,0])
        self.assertFalse(session.state['space_encounter']['player_attacking'])
        self.assertEqual(session.state['date'],date)

    def test_cancel_after_edits_preserves_forces_world_diplomacy_rng_and_date(self):
        session=battle_session();session.apply('ground_edit',operation='remove',selection=1)
        before=deepcopy(session.state);expected=deepcopy(before)
        expected['ground_encounter']=None;expected['campaign_phase']='starmap'
        session.apply('ground_cancel');self.assertEqual(session.state,expected)
        self.assertEqual(before['worlds']['1:5:1']['raw'][0],3)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cancelled.json';session.save(path)
            self.assertEqual(RecoveredSession.load(session.catalog,path).state,session.state)
        session.begin_ground_battle([1,5,1],player_attacking=True,conquering_owner=3)
        self.assertEqual(session.state['ground_encounter']['battle']['friendly_totals'],before['ground_encounter']['battle']['friendly_totals'])

    def test_defenders_and_started_battles_cannot_cancel(self):
        for defending,started in ((True,False),(False,True)):
            session=battle_session(attacking=not defending)
            if started:session.apply('ground_start')
            before=deepcopy(session.state)
            with self.assertRaises(GameError):session.apply('ground_cancel')
            self.assertEqual(before,session.state)
        session=battle_session(attacking=False)
        self.assertNotIn(42,setup_buttons(session.state))

    def test_counts_change_signature_and_removal_compacts_mouse_targets(self):
        session=battle_session();before=setup_signature(session.state)
        self.assertEqual(len(setup_targets(session.state)),4)
        session.apply('ground_edit',operation='decrease',selection=1)
        self.assertNotEqual(before,setup_signature(session.state))
        session.apply('ground_edit',operation='remove',selection=1)
        self.assertEqual([t[2] for t in setup_targets(session.state)],[('ground_remove',1),('ground_quantity',1)])
        self.assertEqual(group_report(session.state['ground_encounter']['battle'],0),(4,5,0))

    def test_add_menu_uses_total_not_reserve_and_zero_group_remains_editable(self):
        session=battle_session();self.assertEqual(setup_buttons(session.state),[11,42,36])
        before=deepcopy(session.state)
        with self.assertRaises(GameError):session.apply('ground_edit',operation='add',selection=4)
        self.assertEqual(before,session.state)
        for _ in range(5):session.apply('ground_edit',operation='decrease',selection=1)
        self.assertEqual(group_report(session.state['ground_encounter']['battle'],0),(4,0,0))
        session.apply('ground_edit',operation='increase',selection=1)
        self.assertEqual(group_report(session.state['ground_encounter']['battle'],0),(4,1,0))
