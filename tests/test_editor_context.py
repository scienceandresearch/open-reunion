"""Fleet editor identity across successful transactions, removal and loading."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from test_cargo import cargo_session
from test_space_session import prepared
from openreunion.core import GameError
from openreunion.dos.editor_context import FleetContext
from openreunion.dos.session import RecoveredSession


class EditorContextTests(unittest.TestCase):
    def test_regular_commands_and_rejections_keep_editor_bound(self):
        s=cargo_session();context=FleetContext(s);revision=s.fleet_revision
        s.apply('rename_fleet',fleet_index=0,name='Freighter')
        s.apply('transfer_cargo',fleet_index=0,slot=13,quantity=1)
        s.apply('advance',hours=1)
        with self.assertRaises(GameError):s.apply('create_fleet',fleet_type=2,name='')
        self.assertEqual(s.fleet_revision,revision)
        context.require(s)

    def test_new_group_invalidates_previous_roster_even_with_duplicate_names(self):
        s=cargo_session();context=FleetContext(s)
        name=bytes(s.state['fleets']['moving'][0][2:2+s.state['fleets']['moving'][0][1]]).decode('ascii')
        s.apply('create_fleet',fleet_type=2,name=name)
        self.assertFalse(context.current(s))
        with self.assertRaises(GameError):context.require(s)

    def test_actual_home_retreat_invalidates_editor_after_disbanding(self):
        s=prepared(attacking=False);context=FleetContext(s)
        before=len(s.state['fleets']['moving'])
        s.apply('space_retreat')
        self.assertTrue(context.current(s))
        s.apply('space_acknowledge')
        self.assertLess(len(s.state['fleets']['moving']),before)
        self.assertFalse(context.current(s))

    def test_load_has_new_context_without_persisting_runtime_revision(self):
        s=cargo_session();context=FleetContext(s)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'saved.json';s.save(path)
            loaded=RecoveredSession.load(s.catalog,path)
            self.assertEqual(loaded.state,s.state)
            self.assertNotIn('fleet_revision',loaded.state)
            self.assertFalse(context.current(loaded))
        other=RecoveredSession(s.catalog,deepcopy(s.state))
        self.assertFalse(context.current(other))


if __name__=='__main__':unittest.main()
