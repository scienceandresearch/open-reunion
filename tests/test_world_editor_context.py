"""World editor identity and optional fleet-index lifetime."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from test_world_lists import fixture
from openreunion.core import GameError
from openreunion.dos.editor_context import WorldContext


class WorldEditorTests(unittest.TestCase):
    def context(self,**kwargs):
        catalog,state=fixture();session=SimpleNamespace(state=state,fleet_revision=0)
        return session,WorldContext(session,catalog['worlds'][0],**kwargs)

    def test_same_saved_world_in_a_different_session_is_rejected(self):
        session,context=self.context();other=deepcopy(session)
        self.assertFalse(context.current(other))
        with self.assertRaises(GameError):context.require(other)

    def test_ownership_colony_establishment_or_terrain_change_invalidates(self):
        for field in (0,6,7,21):
            session,context=self.context();session.state['worlds']['1:1:0']['raw'][field]+=1
            self.assertFalse(context.current(session))
            with self.assertRaises(GameError):context.require(session)

    def test_normal_population_tax_survey_and_building_updates_remain_current(self):
        session,context=self.context();raw=session.state['worlds']['1:1:0']['raw']
        for field in (10,12,13,18,19):raw[field]+=1
        session.state['buildings']=[[1]*14];session.state['resources']={'credits':123}
        context.require(session)

    def test_loss_of_system_or_planet_discovery_invalidates(self):
        session,context=self.context();session.state['known_systems'][0]=0
        self.assertFalse(context.current(session));session.state['known_systems'][0]=1
        session.state['campaign']['navigation']['planet_visibility'][0]=128
        self.assertFalse(context.current(session))

    def test_roster_change_only_invalidates_editors_that_retain_fleet_indices(self):
        session,ordinary=self.context();indexed=WorldContext(session,ordinary.definition,fleets=True)
        session.fleet_revision+=1;ordinary.require(session)
        with self.assertRaises(GameError):indexed.require(session)


if __name__=='__main__':unittest.main()
