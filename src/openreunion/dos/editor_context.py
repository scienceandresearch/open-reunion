"""Runtime guards for windows that retain an index into a mutable fleet bank."""
from ..core import GameError


class FleetContext:
    def __init__(self,session):
        self.session=session
        self.revision=session.fleet_revision

    def current(self,session):
        return session is self.session and session.fleet_revision==self.revision

    def require(self,session):
        if not self.current(session):
            raise GameError("The campaign or fleet list changed. Reopen this fleet editor.")


class WorldContext:
    """A world editor's session, ownership, settlement and terrain identity."""
    def __init__(self,session,definition,*,fleets=False):
        self.session,self.definition=session,definition
        self.signature=self.world_signature(session)
        self.fleet=FleetContext(session) if fleets else None

    def world_signature(self,session):
        raw=session.state['worlds'][self.definition['id']]['raw']
        return tuple(raw[i] for i in (0,6,7,21))

    def current(self,session):
        from .world_lists import world_visible
        return (session is self.session and world_visible(session.state,self.definition)
                and self.world_signature(session)==self.signature
                and (self.fleet is None or self.fleet.current(session)))

    def require(self,session):
        if not self.current(session):
            raise GameError('The campaign, world or fleet list changed. Reopen this world editor.')
