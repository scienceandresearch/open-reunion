"""Nominal standard VGA mode-13 timing and next-retrace scheduling.

The game requests BIOS mode 13h and waits for vertical retrace to go low,
then high. Clock/totals are a standard VGA reference, not measurements of
the user's historical BIOS, monitor or hardware oscillator. See VIDEO-TIMING.md.
"""
from ..core import integer

PIXEL_CLOCK_HZ=25_175_000
HORIZONTAL_TOTAL=800
VERTICAL_TOTAL=449
FRAME_DOTS=HORIZONTAL_TOTAL*VERTICAL_TOTAL
PERIOD_NUMERATOR_NS=FRAME_DOTS*1_000_000_000
RETRACE_HZ=PIXEL_CLOCK_HZ/FRAME_DOTS


def graphics_misc(value):
    """360F9..3610A preserves bits 0..5 and sets sync polarity bits to 01."""
    integer(value,'VGA miscellaneous output',maximum=255)
    return (value&0x3F)|0x40


class RetraceClock:
    def __init__(self,origin_ns):
        integer(origin_ns,'Retrace clock origin',maximum=2**63-1)
        self.origin_ns=origin_ns

    def next_deadline(self,now_ns):
        integer(now_ns,'Retrace clock time',minimum=self.origin_ns,maximum=2**63-1)
        edge=(now_ns-self.origin_ns)*PIXEL_CLOCK_HZ//PERIOD_NUMERATOR_NS+1
        return self.origin_ns+(edge*PERIOD_NUMERATOR_NS+PIXEL_CLOCK_HZ-1)//PIXEL_CLOCK_HZ

    def delay_ms(self,now_ns):
        return (self.next_deadline(now_ns)-now_ns+999_999)//1_000_000
