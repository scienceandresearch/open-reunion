"""Original two-bank control slide and its standard-VGA reference waits."""
from ..core import GameError,integer
from .catalog import DATA_FILE_OFFSET
from .video_timing import PIXEL_CLOCK_HZ,HORIZONTAL_TOTAL,VERTICAL_TOTAL,FRAME_DOTS


def read_steps(data):
    steps=list(data[DATA_FILE_OFFSET+0x4874:DATA_FILE_OFFSET+0x4874+21])
    validate_steps(steps);return steps


def validate_steps(steps):
    if not isinstance(steps,(list,tuple)) or len(steps)!=21:
        raise GameError('Invalid control slide table.')
    for step in steps:integer(step,'Control slide distance',minimum=1,maximum=33)
    if sum(steps)!=33 or steps[-1]!=1:raise GameError('Invalid control slide endpoints.')


def slide_rows(steps,page):
    """2F216 copies before adding; 2F2D3 subtracts before copying."""
    validate_steps(steps);integer(page,'Control page',maximum=1)
    rows=[];row=33 if page else 1
    for step in steps:
        if page:row-=step
        rows.append(row)
        if not page:row+=step
    return tuple(rows)


class PageClock:
    """Mode-13 reference: raster origin, 640x400 active dots, retrace at 412.

    See CONTROL-SLIDE.md for register evidence and physical-timing limits.
    No CPU spin or rounded-period accumulation is used by the native UI.
    """
    def __init__(self,origin_ns):
        integer(origin_ns,'Page clock origin',maximum=2**63-1);self.origin_ns=origin_ns

    def dots(self,now_ns):
        integer(now_ns,'Page clock time',minimum=self.origin_ns,maximum=2**63-1)
        return (now_ns-self.origin_ns)*PIXEL_CLOCK_HZ//1_000_000_000

    def stamp(self,dots):
        return self.origin_ns+(dots*1_000_000_000+PIXEL_CLOCK_HZ-1)//PIXEL_CLOCK_HZ

    def display_deadline(self,now_ns):
        # Forty bit-0 low/high cycles. No low interval occurs in vertical
        # inactive lines, so a scanline-only period would be incorrect there.
        dots=self.dots(now_ns);line,x=divmod(dots,HORIZONTAL_TOTAL)
        if line%VERTICAL_TOTAL>=400:line+=(VERTICAL_TOTAL-line%VERTICAL_TOTAL)
        elif x>=640:
            line+=1
            if line%VERTICAL_TOTAL==400:line+=VERTICAL_TOTAL-400
        active=(line//VERTICAL_TOTAL)*400+line%VERTICAL_TOTAL+39
        frame,row=divmod(active,400)
        return self.stamp((frame*VERTICAL_TOTAL+row)*HORIZONTAL_TOTAL+640)

    def retrace_deadline(self,now_ns):
        dots=self.dots(now_ns);frame,phase=divmod(dots,FRAME_DOTS)
        if phase>=412*HORIZONTAL_TOTAL:frame+=1
        return self.stamp(frame*FRAME_DOTS+412*HORIZONTAL_TOTAL)
