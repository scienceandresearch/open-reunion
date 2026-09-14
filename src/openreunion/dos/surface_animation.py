"""Presentation-only FANIM frames recovered from the original surface loops."""
from dataclasses import dataclass

from .video_timing import PERIOD_NUMERATOR_NS, PIXEL_CLOCK_HZ

# Original DS:1826, indexed by terrain group. Each tile occupies 256 bytes.
TILES_PER_FRAME = {1: 80, 5: 20, 10: 80}


@dataclass
class SurfaceAnimation:
    # Original 6085 initializes the one-based frame to three.
    frame: int = 3
    origin_ns: int | None = None
    steps: int = 0

    def pause(self):
        self.origin_ns = None
        self.steps = 0

    def advance(self, now_ns, *, enabled=True):
        """Ten nominal VGA retraces per frame, independent of campaign time.

        The DOS counter was shared with simulation. The port deliberately uses
        a local clock: pause/speed changes cannot change resources or RNG through
        animation. Hidden/held views discard elapsed time instead of catching up.
        """
        if not enabled:
            self.pause()
            return False
        if self.origin_ns is None:
            self.origin_ns = now_ns
            return False
        steps = (now_ns - self.origin_ns) * PIXEL_CLOCK_HZ // (10 * PERIOD_NUMERATOR_NS)
        advanced = steps - self.steps
        self.steps = steps
        if advanced:
            self.frame = (self.frame - 1 + advanced) % 3 + 1
        return bool(advanced)

    def tile(self, group, tile):
        """25B79: add the current frame's atlas offset to an animated tile."""
        return tile + (self.frame - 1) * TILES_PER_FRAME[group]
