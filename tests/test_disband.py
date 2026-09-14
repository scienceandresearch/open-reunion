from copy import deepcopy
import struct
import unittest

from test_equipment import equipment_session
from openreunion.core import GameError
from openreunion.dos.disband import disband_available,hulls_empty
from openreunion.dos.editor_context import FleetContext
from openreunion.dos.equipment import new_fleet


def session_for(kind=2):
    session=equipment_session()
    session.state['fleets']['moving']=[new_fleet(2,'Before'),new_fleet(kind,'Remove'),new_fleet(4,'After')]
    local=new_fleet(1,'Home defense');local[0]=5;local[22]=7
    session.state['fleets']['local']=[local]
    return session


class DisbandTests(unittest.TestCase):
    def test_removes_only_selected_empty_group_for_each_type_and_invalidates_editors(self):
        for kind in range(1,5):
            session=session_for(kind);before=deepcopy(session.state);context=FleetContext(session)
            self.assertTrue(disband_available(session.state,1))
            session.apply('disband_fleet',fleet_index=1)
            self.assertFalse(context.current(session))
            before['fleets']['moving'].pop(1);before['log']=session.state['log']
            self.assertEqual(session.state,before)

    def test_all_hull_banks_block_disbanding(self):
        for kind in range(1,5):
            for bank in ((0,1) if kind in (1,3) else (0,)):
                for h in range(1 if kind==4 else 4):
                    session=session_for(kind)
                    session.state['fleets']['moving'][1][29+40*bank+10*h]=1
                    self.assertFalse(hulls_empty(session.state['fleets']['moving'][1]))
                    before=deepcopy(session.state)
                    with self.assertRaises(GameError):session.apply('disband_fleet',fleet_index=1)
                    self.assertEqual(session.state,before)

    def test_invalid_indexes_local_groups_or_unavailable_locations_are_atomic(self):
        for args in ({'fleet_index':-1},{'fleet_index':True},{'fleet_index':3},{'bank':'local'},{'bank':'unknown'}):
            session=session_for();before=deepcopy(session.state)
            with self.assertRaises(GameError):session.apply('disband_fleet',**({'fleet_index':1}|args))
            self.assertEqual(session.state,before)
        for status,owner,colony in ((2,1,1),(4,1,1),(7,1,1),(1,2,1),(1,1,0)):
            session=session_for();session.state['fleets']['moving'][1][22]=status
            raw=session.state['worlds']['1:5:0']['raw'];raw[0]=owner;raw[6]=colony
            before=deepcopy(session.state)
            with self.assertRaises(GameError):session.apply('disband_fleet',fleet_index=1)
            self.assertEqual(session.state,before)

    def test_stranded_cargo_and_untransferred_equipment_are_never_discarded(self):
        for kind,offset in ((1,109),(1,157),(2,31),(2,109),(2,129),(2,133),(2,157),
                            (3,71),(3,109),(4,31),(4,109)):
            session=session_for(kind);session.state['fleets']['moving'][1][offset]=1
            before=deepcopy(session.state)
            self.assertFalse(disband_available(session.state,1))
            with self.assertRaises(GameError):session.apply('disband_fleet',fleet_index=1)
            self.assertEqual(session.state,before)

    def test_army_and_pirate_remaining_weapons_go_to_last_exact_local_record(self):
        for kind,offsets in ((1,(31,71)),(3,(31,))):
            session=session_for(kind)
            session.state['fleets']['local'].append(list(session.state['fleets']['local'][0]))
            wrong=list(session.state['fleets']['local'][0]);wrong[21]=1
            session.state['fleets']['local'].append(wrong)
            for at in offsets:
                session.state['fleets']['moving'][1][at]=2
                session.state['fleets']['local'][1][at]=3
            before=deepcopy(session.state)
            session.apply('disband_fleet',fleet_index=1)
            before['fleets']['moving'].pop(1)
            for at in offsets:before['fleets']['local'][1][at]=5
            before['log']=session.state['log']
            self.assertEqual(session.state,before)

    def test_missing_destination_and_signed_overflow_reject_without_partial_transfers(self):
        for mode in ('missing','overflow','negative','negative_incoming'):
            session=session_for(1);row=session.state['fleets']['moving'][1];row[31]=1;row[33]=1
            if mode=='missing':session.state['fleets']['local']=[]
            elif mode=='negative_incoming':row[31:33]=struct.pack('<h',-1)
            else:session.state['fleets']['local'][0][33:35]=struct.pack('<h',32767 if mode=='overflow' else -1)
            before=deepcopy(session.state)
            with self.assertRaises(GameError):session.apply('disband_fleet',fleet_index=1)
            self.assertEqual(session.state,before)

    def test_empty_group_can_be_removed_without_a_local_receiver(self):
        session=session_for(1);session.state['fleets']['local']=[]
        session.apply('disband_fleet',fleet_index=1)
        self.assertEqual(len(session.state['fleets']['moving']),2)


if __name__=='__main__':unittest.main()
