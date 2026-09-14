"""Result palette lifetime: logical picture merge and separate device fades.

The caller supplies the prior full logical and hardware palettes. These are
distinct in DOS; neither is inferred from the colors of one cropped picture.
"""
from dataclasses import dataclass,replace
from ..core import GameError,integer
from .assets import Picture
from .scene_effects import _palette,dac_rgb


def load_result_palette(picture_palette,current):
    """35F19: source 0..176 replaces logical 64..240; other colors survive."""
    _palette(current)
    if not isinstance(picture_palette,bytes) or len(picture_palette)!=768:
        raise GameError('Invalid result picture palette.')
    palette=bytearray(current);palette[64*3:241*3]=bytes(v>>2 for v in picture_palette[:177*3])
    return bytes(palette)


def fade_result_palette(target,hardware,step):
    """35159 -> 3518B: 64..254 fade on six retraces, then full upload.

    Step five includes the final untimed 0..255 upload. It can change colors
    outside the fade range when logical and hardware palettes initially differ.
    """
    _palette(target);_palette(hardware);integer(step,'Result fade step',maximum=5)
    if step==5:return bytes(target)
    palette=bytearray(hardware)
    palette[64*3:255*3]=bytes(v*step//5 for v in target[64*3:255*3])
    return bytes(palette)


@dataclass(frozen=True)
class ResultDisplay:
    pixels: bytes
    target: bytes
    hardware: bytes
    step: int=-1

    def picture(self):return Picture(320,151,self.pixels,dac_rgb(self.hardware))


def begin_result_display(picture,logical,hardware):
    """A composed result uses unshifted indices; the DOS display adds 64."""
    _palette(logical);_palette(hardware)
    if (picture.width,picture.height)!=(320,151) or not isinstance(picture.pixels,bytes) or len(picture.pixels)!=320*151:
        raise GameError('Invalid composed result image.')
    return ResultDisplay(bytes((v+64)&255 for v in picture.pixels),bytes(logical),bytes(hardware))


def advance_result_display(display):
    if not isinstance(display,ResultDisplay):raise GameError('Invalid result display.')
    integer(display.step,'Result fade cursor',minimum=-1,maximum=5)
    if display.step==5:return display
    step=display.step+1
    return replace(display,step=step,hardware=fade_result_palette(display.target,display.hardware,step))
