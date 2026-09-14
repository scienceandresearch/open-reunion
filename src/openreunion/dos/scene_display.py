"""Original scene display envelope with separate logical and hardware palettes.

The caller redraws after closure: DOS restores only the y=32..48 strip and
logical palette, leaving the hardware palette at the final black fade level.
"""
from dataclasses import dataclass,replace

from ..core import GameError,integer
from .assets import Picture
from .scene_effects import load_scene_palette,dac_rgb,_palette


@dataclass(frozen=True)
class SceneDisplay:
    pixels: bytes
    target: bytes
    palette: bytes
    saved_strip: bytes
    saved_palette: bytes

    def picture(self):
        return Picture(320,200,self.pixels,dac_rgb(self.palette))


def begin_display(picture,pixels,palette,*,hardware=None):
    if not isinstance(pixels,bytes) or len(pixels)!=64000:raise GameError('Invalid prior scene display.')
    _palette(palette)
    if hardware is None:hardware=palette
    _palette(hardware)
    if picture.width!=320 or picture.height<200 or len(picture.pixels)!=picture.width*picture.height:
        raise GameError('Invalid scene picture dimensions.')
    cropped=picture.pixels[:64000]
    if any(index>=192 for index in cropped):raise GameError('Scene picture exceeds its palette range.')
    return SceneDisplay(bytes(index+64 for index in cropped),load_scene_palette(picture.palette,palette),
                        bytes(hardware),pixels[0x2800:0x3D40],bytes(palette))


def fade_display(display,level):
    integer(level,'Scene fade level',maximum=5)
    return replace(display,palette=bytes(value*level//5 for value in display.target))


def draw_display(display,picture,*,x=0,y=0):
    integer(x,'Scene frame x',maximum=319);integer(y,'Scene frame y',maximum=199)
    if picture.width<1 or picture.height<1 or x+picture.width>320 or y+picture.height>200:
        raise GameError('Scene animation exceeds the display.')
    if len(picture.pixels)!=picture.width*picture.height or any(index>=192 for index in picture.pixels):
        raise GameError('Invalid scene animation pixels.')
    pixels=bytearray(display.pixels)
    for row in range(picture.height):
        start=(y+row)*320+x;source=row*picture.width
        pixels[start:start+picture.width]=bytes(index+64 for index in picture.pixels[source:source+picture.width])
    return replace(display,pixels=bytes(pixels))


def finish_display(display):
    pixels=bytearray(display.pixels);pixels[0x2800:0x3D40]=display.saved_strip
    return replace(display,pixels=bytes(pixels),target=display.saved_palette)


def render_scene(source,state,*,pixels,palette,hardware=None):
    """Rebuild a displayed scene from its validated playback snapshot.

    Retained story frames come from ContentSource's cumulative decoder. No
    animation selection, RNG draw, sound replay or gameplay mutation occurs.
    The caller supplies its prior display context for exact exit restoration.
    """
    from .scene_playback import validate_scene
    rules=source.catalog.get('story_cinema')
    validate_scene(state,rules)
    display=begin_display(source.indexed_picture(f"PICS/PIC{state['scene']}.PIC"),pixels,palette,hardware=hardware)
    view=state['view']
    if view['asset'] is not None:
        row=rules[view['asset']-1]
        display=draw_display(display,source.story_animation(view['asset'],view['frame']),x=row['x'],y=row['y'])
    phase=state['phase'];step=state['fade_step']
    if phase=='fade_in':
        if step>=0:display=fade_display(display,step)
    else:
        display=fade_display(display,5 if phase=='body' or step<0 else 5-step)
        if phase=='done':display=finish_display(display)
    return display
