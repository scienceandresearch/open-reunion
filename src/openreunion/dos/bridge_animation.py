"""Pure original control-room MAINA1..5 presentation plans and ambient state.

The controller owns scheduling and drawing.  Events are immutable tuples so a
desktop adapter can advance one logical retrace at a time without touching the
campaign clock or campaign RNG.  Recovered from REUNION.PRG 306DC..30CEE; see
local/research/bridge-animation-r1.
"""
from dataclasses import dataclass, field

from ..core import GameError, integer
from .campaign import random_bounded


A1_DESTINATION = (273, 57, 47, 136)
A2_DESTINATION = (172, 49, 18, 89)
A3_DESTINATION = (202, 56, 21, 105)
A4_DESTINATION = (205, 70, 16, 91)
A5_PRIMARY_DESTINATION = (37, 49, 19, 21)
A5_SECONDARY_DESTINATION = (226, 81, 12, 14)

# DS:5526..555C, converted from linear VGA offsets to screen coordinates.
A5_COLOR_PIXELS = ((4, 118), (8, 117), (12, 116), (1, 120), (3, 120),
                   (6, 119), (9, 119), (13, 118), (1, 123), (14, 120), (15, 119))
A5_BLINK_PIXELS = ((224, 51), (232, 59), (235, 55), (126, 51),
                   (134, 52), (136, 51), (138, 52), (142, 51))

GENERIC_COMMANDER_BOUNDARY = (
    "The original MAINA4 helper calls 30320 after each four-call ambient cadence. "
    "generic_commander_tick is the controller boundary where advance_generic must be expanded "
    "before the following pilot overlap restore."
)


def _copy(asset, source, destination):
    return ("copy", asset, source, destination)


def _displayed_copy(events, asset, source, destination, overlay):
    events.append(("display_begin",))
    events.append(_copy(asset, source, destination))
    if overlay is not None:
        events.append(overlay)
    events.append(("display_end",))


def _ambient_retrace(events):
    # MAINA1/2 call 30B75 before 30A45, then wait one retrace.
    events.extend((("ambient_step", "MAINA5"), ("ambient_step", "MAINA4"), ("wait", 1)))


def transition_plan(target, *, a4_direction=0):
    """Return a complete original event plan for one animation-gated bridge exit.

    Targets are the modern names for original hotspots 1B, 1C and 1F.  The
    destination event is deliberately last: the DOS dispatcher commits its
    screen word only after the animation returns.  Ambient markers must be
    expanded through :class:`BridgeAmbient`; they are retained in the plan so
    the small room displays do not silently freeze during MAINA1/2.
    """
    if target not in ("commanders", "production", "fleets"):
        raise GameError("Unknown animated bridge destination.")
    integer(a4_direction, "Bridge MAINA4 direction", maximum=1)
    events = []
    if target == "commanders":
        events.extend((("sound", "DOOR1"), ("load", "MAINA2")))
        _ambient_retrace(events)
        for frame in range(4):
            _displayed_copy(events, "MAINA2", (18 * frame, 0, 18, 89), A2_DESTINATION, None)
            # 30CEF redraws the hero in its own display bracket after MAINA2.
            events.append(("hero_overlay",))
            for _ in range(4):
                _ambient_retrace(events)
        events.append(("destination", 2))
    elif target == "production":
        events.extend((("sound", "DOOR2"), ("load", "MAINA1")))
        _ambient_retrace(events)
        for frame in range(6):
            _displayed_copy(events, "MAINA1", (47 * frame, 0, 47, 136), A1_DESTINATION,
                            ("commander_overlay", "fighter"))
            for _ in range(4):
                _ambient_retrace(events)
        events.append(("destination", 5))
    else:
        events.extend((("sound", "DOOR3"), ("load", "MAINA4"), ("wait", 1)))
        sources = (range(0, 96, 16) if a4_direction == 0 else range(224, 128, -16))
        for source_x in sources:
            _displayed_copy(events, "MAINA4", (source_x, 0, 16, 91), A4_DESTINATION,
                            ("commander_overlay", "builder"))
            events.append(("wait", 4))
        events.extend((("load", "MAINA3"), ("wait", 1)))
        for frame in range(4):
            _displayed_copy(events, "MAINA3", (21 * frame, 0, 21, 105), A3_DESTINATION,
                            ("commander_overlay", "builder"))
            events.append(("wait", 5))
        events.append(("destination", 16))
    return tuple(events)


@dataclass
class BridgeAmbient:
    """Private presentation state for the persistent MAINA4/5 room effects."""

    seed: int = 1994
    a4_direction: int = 0
    a4_idle: int = 1
    a4_cadence: int = 1
    a5_primary_frame: int = 1
    a5_primary_cadence: int = 1
    a5_secondary_frame: int = 1
    a5_secondary_cadence: int = 1
    a5_blinks: list = field(default_factory=lambda: [1] * 8)
    generic_asset: int = 0
    generic_frame: int = 0
    generic_delay: int = 0

    def __post_init__(self):
        integer(self.seed, "Bridge cosmetic seed", maximum=2**32 - 1)
        integer(self.a4_direction, "Bridge MAINA4 direction", maximum=1)
        integer(self.a4_idle, "Bridge MAINA4 idle counter", maximum=0xFFFF)
        integer(self.a4_cadence, "Bridge MAINA4 cadence", maximum=0xFFFF)
        integer(self.a5_primary_frame, "Bridge MAINA5 primary frame", maximum=37)
        integer(self.a5_primary_cadence, "Bridge MAINA5 primary cadence", maximum=0xFFFF)
        integer(self.a5_secondary_frame, "Bridge MAINA5 secondary frame", maximum=9)
        integer(self.a5_secondary_cadence, "Bridge MAINA5 secondary cadence", maximum=0xFFFF)
        integer(self.generic_asset, "Bridge generic animation", maximum=6)
        integer(self.generic_frame, "Bridge generic frame", maximum=140)
        integer(self.generic_delay, "Bridge generic delay", maximum=0xFFFF)
        if not isinstance(self.a5_blinks, list) or len(self.a5_blinks) != 8:
            raise GameError("Bridge MAINA5 requires eight blink counters.")
        for value in self.a5_blinks:
            integer(value, "Bridge MAINA5 blink counter", maximum=255)

    def _random(self, limit):
        self.seed, value = random_bounded(self.seed, limit)
        return value

    def enter_bridge(self):
        """Apply the bridge-entry write at 2F71F without resetting ambient phase."""
        self.a5_primary_frame = 1

    @staticmethod
    def _generic_rules(rules):
        if not isinstance(rules, list) or len(rules) < 6:
            raise GameError("Bridge generic animation rules are missing.")
        for row in rules[:6]:
            if not isinstance(row, dict) or not all(key in row for key in ("frames", "width", "height", "x", "y")):
                raise GameError("Invalid bridge generic animation rules.")
            integer(row["frames"], "Bridge generic frames", minimum=1, maximum=140)
            integer(row["width"], "Bridge generic width", minimum=3, maximum=320)
            integer(row["height"], "Bridge generic height", minimum=3, maximum=200)
            integer(row["x"], "Bridge generic X", maximum=319)
            integer(row["y"], "Bridge generic Y", maximum=199)
            if row["x"] + row["width"] - 2 > 320 or row["y"] + row["height"] - 2 > 200:
                raise GameError("Bridge generic animation exceeds the screen.")
        return rules

    def _select_generic(self, rules):
        self._generic_rules(rules)
        self.generic_asset = 1 + self._random(6)
        self.generic_frame = 1
        self.generic_delay = 100 + self._random(200)

    def initialize_generic(self, rules):
        """Run the original bridge resource-init selection for MAIN1..6."""
        self.generic_asset = self.generic_frame = self.generic_delay = 0
        self._select_generic(rules)

    def advance_generic(self, rules, *, fighter_visible=False):
        """Advance one 30320 generic-idle call after its A4 boundary event."""
        self._generic_rules(rules)
        if type(fighter_visible) is not bool:
            raise GameError("Bridge fighter visibility must be boolean.")
        if self.generic_asset == 0:
            return ()
        if self.generic_delay != 0:
            self.generic_delay = (self.generic_delay - 1) & 0xFFFF
            return ()
        self.generic_frame += 1
        row = rules[self.generic_asset - 1]
        if self.generic_frame > row["frames"]:
            self.generic_asset = 0
            self._select_generic(rules)
            return ()
        source = (1, 1, row["width"] - 2, row["height"] - 2)
        destination = (row["x"], row["y"], row["width"] - 2, row["height"] - 2)
        events = [("display_begin",),
                  ("generic_frame", self.generic_asset, self.generic_frame, source, destination)]
        if fighter_visible and self.generic_asset <= 6:
            events.append(("commander_overlay", "fighter"))
        events.append(("display_end",))
        return tuple(events)

    def advance_a4(self, *, builder_visible=False):
        """Advance one call of original helper 30A45 and return ordered events.

        The generic tick remains an explicit event so the controller can draw
        the MAIN1..6 frame between this helper and the overlapping pilot restore.
        """
        if type(builder_visible) is not bool:
            raise GameError("Bridge commander visibility flags must be booleans.")
        self.a4_cadence -= 1
        if self.a4_cadence > 0:
            return ()
        self.a4_cadence = 4
        self.a4_idle = (self.a4_idle - 1) & 0xFFFF
        if self.a4_idle == 0:
            self.a4_idle = 70 + self._random(250)
            self.a4_direction ^= 1
        frame = self.a4_idle - 1 if self.a4_direction else 16 - self.a4_idle
        events = []
        if 0 <= frame < 16:
            _displayed_copy(events, "MAINA4", (16 * frame, 0, 16, 91), A4_DESTINATION,
                            ("commander_overlay", "builder") if builder_visible else None)
        restore_pilot = self.generic_asset != 0 and self.generic_delay == 0
        events.append(("generic_commander_tick",))
        if restore_pilot:
            events.append(("commander_overlay", "pilot"))
        return tuple(events)

    def advance_a5(self):
        """Advance one call of original helper 30B75 and return ordered events."""
        events = []
        self.a5_primary_cadence -= 1
        if self.a5_primary_cadence <= 0:
            self.a5_primary_cadence = 5
            self.a5_primary_frame = (self.a5_primary_frame + 1) % 38
            frame = self.a5_primary_frame
            source = (19 * (frame % 16), 1 + 22 * (frame // 16), 19, 21)
            events.append(_copy("MAINA5", source, A5_PRIMARY_DESTINATION))
        self.a5_secondary_cadence -= 1
        if self.a5_secondary_cadence <= 0:
            self.a5_secondary_cadence = 7
            self.a5_secondary_frame = (self.a5_secondary_frame + 1) % 10
            source = (115 + 13 * self.a5_secondary_frame, 45, 12, 14)
            events.append(_copy("MAINA5", source, A5_SECONDARY_DESTINATION))
        for destination in A5_COLOR_PIXELS:
            events.append(("pixel", destination, 64 + self._random(176)))
        for index, destination in enumerate(A5_BLINK_PIXELS):
            counter = (self.a5_blinks[index] - 1) & 0xFF
            if counter == 0:
                events.append(("pixel", destination, 0x70))
                counter = 102 + self._random(5)
            elif counter == 100:
                events.append(("pixel", destination, 0x82))
                counter = 5 + self._random(8)
            self.a5_blinks[index] = counter
        return tuple(events)

    def advance_pair(self, *, builder_visible=False):
        """Execute the MAINA1/2 helper order: MAINA5, then MAINA4."""
        return self.advance_a5() + self.advance_a4(builder_visible=builder_visible)
