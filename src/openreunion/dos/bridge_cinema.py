"""Nonblocking original control-room ambience and three animated exits."""
from collections import deque
from time import monotonic_ns
import tkinter as tk

from .bridge import COMMANDER_RECTS, COMMANDER_SOURCES, available_commanders
from .bridge_animation import BridgeAmbient, transition_plan
from .commanders import ROLES
from .hero import bridge_source
from .video_timing import RetraceClock


DESTINATIONS = {2: "commanders", 5: "production", 16: "fleets"}


class BridgeCinema:
    """Own presentation-only state for the persistent control-room picture.

    Campaign state and commands remain outside this object.  A cached body is
    changed by exact original copy/pixel events, while :meth:`draw` composes a
    new control-panel header so the date and balance never become stale.
    """

    def __init__(self, app, *, seed=1994):
        self.app = app
        self.seed = seed
        self.owner = None
        self.ambient = None
        self.signature = None
        self.body = None
        self.assets = {}
        self.events = deque()
        self.wait = 0
        self.target = None
        self.timer = None
        self.clock = None
        self.generation = 0
        self.entered = False

    @property
    def running(self):
        return bool(self.events or self.wait or self.target)

    def _rules(self):
        return self.app.catalog["story_cinema"][:6]

    def _state_signature(self, state, hero):
        campaign = state["campaign"]
        return (hero, tuple(state["ranks"][role] for role in ROLES),
                campaign["training_role"], bool(campaign["research_block_remaining"]))

    def _cancel_timer(self):
        self.generation += 1
        if self.timer is not None:
            try:
                self.app.root.after_cancel(self.timer)
            except tk.TclError:
                pass
        self.timer = None
        self.clock = None

    def _cancel_navigation(self):
        navigation = getattr(self.app, "navigation_sound", None)
        if (navigation is not None
                and (navigation.owner is self.owner or navigation.owner is self.app.session)
                and navigation.destination == "bridge"):
            navigation.cancel()

    def cancel(self):
        """Cancel a partial exit and discard its rendered body."""
        self._cancel_timer()
        self._cancel_navigation()
        self.events.clear()
        self.wait = 0
        self.target = None
        self.body = None
        self.signature = None
        self.entered = False

    def leave(self):
        """Leave the bridge while preserving this session's ambient phase."""
        self.cancel()

    def sync(self):
        """Reset private cosmetic state after Load/New Game session replacement."""
        if self.owner is self.app.session:
            return False
        self.cancel()
        self.owner = self.app.session
        self.ambient = BridgeAmbient(seed=self.seed)
        self.ambient.initialize_generic(self._rules())
        return True

    def _asset(self, name):
        if name not in self.assets:
            self.assets[name] = self.app.screen_renderer.asset(name)
        return self.assets[name]

    def _ensure_body(self, state, page, caption, hero):
        signature = self._state_signature(state, hero)
        if signature != self.signature:
            if self.running:
                self.cancel()
                self.owner = self.app.session
            self.body = self.app.screen_renderer.bridge(state, page, caption, hero)
            self.signature = signature
        elif self.body is None:
            self.body = self.app.screen_renderer.bridge(state, page, caption, hero)

    def draw(self, state, page, caption, hero):
        """Return the current body under a newly rendered original header."""
        self.sync()
        if not self.entered:
            self.ambient.enter_bridge()
            self.entered = True
        self._ensure_body(state, page, caption, hero)
        target = self.app.screen_renderer.frame(state, None, 1, page, caption)
        target.rgb[49 * 320 * 3:] = self.body.rgb[49 * 320 * 3:]
        self.schedule()
        return target

    def start(self, target):
        """Start one original animation-gated bridge exit, if bridge is ready."""
        if target not in ("commanders", "production", "fleets"):
            transition_plan(target)  # retain the model's bounded GameError
        if (self.running or self.app.screen != "bridge" or self.app.startup is not None
                or not self.app.original.winfo_ismapped()):
            return False
        self.sync()
        state = self.app.session.state
        self._ensure_body(state, self.app.menu_page,
                          self.app.caption or "CONTROL ROOM", self.app.hero)
        self.target = target
        self.events.extend(transition_plan(
            target, a4_direction=self.ambient.a4_direction))
        try:
            self._consume()
        except Exception:
            self.cancel()
            raise
        self.schedule()
        return True

    def _commander_visible(self, role):
        index = ROLES.index(role)
        return index in available_commanders(self.app.session.state)

    def _commander_overlay(self, role):
        index = ROLES.index(role)
        if index not in available_commanders(self.app.session.state):
            return
        rank = self.app.session.state["ranks"][role]
        x, y, width, height = COMMANDER_RECTS[index]
        sx, sy = COMMANDER_SOURCES[index][rank - 1]
        self.body.blit(self._asset("MAINFACE"), x, y,
                       source=(sx, sy, width, height), transparent=0)

    def _hero_overlay(self):
        self.body.blit(self._asset("HEROES"), 131, 99,
                       source=bridge_source(self.app.hero), transparent=0)

    def _apply(self, event):
        kind = event[0]
        if kind in ("display_begin", "display_end"):
            return
        if kind == "sound":
            self.app.navigation_sound.start(event[1], "bridge")
        elif kind == "load":
            self._asset(event[1])
        elif kind == "copy":
            _, asset, source, (x, y, _, _) = event
            self.body.blit(self._asset(asset), x, y, source=source)
        elif kind == "pixel":
            _, (x, y), color = event
            palette = self._asset("MAINA5").palette
            at = (y * 320 + x) * 3
            self.body.rgb[at:at + 3] = palette[color * 3:color * 3 + 3]
        elif kind == "hero_overlay":
            self._hero_overlay()
        elif kind == "commander_overlay":
            self._commander_overlay(event[1])
        elif kind == "generic_frame":
            _, asset, frame, source, (x, y, _, _) = event
            picture = self.app.content.bridge_animation(asset, frame)
            self.body.blit(picture, x, y, source=source)
        elif kind == "ambient_step":
            if event[1] == "MAINA5":
                nested = self.ambient.advance_a5()
            else:
                nested = self.ambient.advance_a4(
                    builder_visible=self._commander_visible("builder"))
            for item in nested:
                self._apply(item)
        elif kind == "generic_commander_tick":
            for item in self.ambient.advance_generic(
                    self._rules(), fighter_visible=self._commander_visible("fighter")):
                self._apply(item)
        elif kind == "destination":
            self._commit(DESTINATIONS[event[1]])
        else:
            raise ValueError("Unknown bridge presentation event.")

    def _consume(self):
        while not self.wait and self.events:
            event = self.events.popleft()
            if event[0] == "wait":
                self.wait = event[1]
            else:
                self._apply(event)

    def _commit(self, destination):
        self.events.clear()
        self.wait = 0
        self.target = None
        navigation = getattr(self.app, "navigation_sound", None)
        if (navigation is not None and navigation.owner is self.app.session
                and navigation.destination == "bridge"):
            navigation.destination = destination
        if destination == "fleets":
            self.app.open_fleets()
        else:
            self.app.show_original(destination)

    def schedule(self):
        if (self.timer is None and self.app.screen == "bridge"
                and self.app.startup is None and self.app.original.winfo_ismapped()):
            now = monotonic_ns()
            if self.clock is None:
                self.clock = RetraceClock(now)
            generation = self.generation
            self.timer = self.app.root.after(
                self.clock.delay_ms(now),
                lambda: self.app.guard(lambda: self.tick(generation)))

    def tick(self, generation=None):
        if generation is not None and generation != self.generation:
            return
        self.timer = None
        if self.owner is not self.app.session or self.app.screen != "bridge":
            self.leave()
            return
        if self.app.startup is not None or not self.app.original.winfo_ismapped():
            self.clock = None
            return
        if self.app.pointer.buttons:
            self.clock = RetraceClock(monotonic_ns())
            self.schedule()
            return
        try:
            if self.running:
                if self.wait:
                    self.wait -= 1
                self._consume()
            else:
                for event in self.ambient.advance_pair(
                        builder_visible=self._commander_visible("builder")):
                    self._apply(event)
        except Exception:
            self.cancel()
            raise
        if self.app.screen == "bridge":
            self.app.render_original()
            self.schedule()
