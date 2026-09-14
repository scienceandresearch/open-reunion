"""Game Credits animation containers, including the original skipped opening."""
from pathlib import Path
import struct

from ..core import GameError
from .assets import Picture,read_picture
from .story_cinema import read_main_animation,draw_frame

ASSETS=(3,4,*range(10,28))
FRAME_COUNTS={asset:165 if asset==3 else 41 if asset==4 else 30 for asset in ASSETS}


def animation_frames(data,asset):
    """The original decoder uses embedded 320x200 geometry, not table height.

    ANIM4's table says 160 high, but all its headers and actual decoder use 200.
    The first two containers have unused tails; the DOS loader stops at the
    declared frame count. ANIM28 is not referenced by the credits program.
    """
    if type(asset) is not int or asset not in FRAME_COUNTS:raise GameError('Unknown Game Credits animation.')
    return read_main_animation(data,{'frames':FRAME_COUNTS[asset],'width':320,'height':200})


def displayed_frames(asset):
    if type(asset) is not int or asset not in FRAME_COUNTS:raise GameError('Unknown Game Credits animation.')
    return range(31 if asset==3 else 1,FRAME_COUNTS[asset]+1)


def read_animation_geometry(executable):
    if len(executable)<0xD850+0x1B+28*7:raise GameError('Truncated Game Credits animation table.')
    rows={}
    for asset in ASSETS:
        values=struct.unpack_from('<BHBHB',executable,0xD850+0x1B+7*asset)
        expected=(FRAME_COUNTS[asset],320,160 if asset==4 else 200,0,0)
        if values!=expected:raise GameError('Unsupported Game Credits animation geometry.')
        rows[asset]=dict(zip(('frames','width','height','x','y'),values))
    return rows


def raw_palette(data):
    if len(data)!=768:raise GameError('Invalid Game Credits palette.')
    # These palette-only files store eight-bit channels, like SpidyGfx.
    # DAC quantization and fades belong to presentation, not asset decoding.
    return bytes(data)


def original_frames(root):
    """Yield (asset, original frame index, picture) in actual playback order.

    Frames 1..30 of ANIM3 are intentionally never drawn. ANIM4 starts on the
    original cleared screen. ANIM10..27 draw cumulatively over PAL10 and then
    over the preceding clip's final frame; resetting each clip loses pixels.
    """
    root=Path(root);background=bytes(64000);palette=bytes(768)
    for asset in ASSETS:
        if asset in (3,4):
            background=bytes(64000);palette=raw_palette((root/f'PAL{asset}.PIC').read_bytes())
        elif asset==10:
            picture=read_picture(root/'PAL10.PIC')
            if (picture.width,picture.height)!=(320,200):raise GameError('Invalid credits background size.')
            background,palette=picture.pixels,picture.palette
        frames,_=animation_frames((root/f'ANIM{asset}.ANI').read_bytes(),asset)
        for index in displayed_frames(asset):
            background=draw_frame(frames,index,background)
            yield asset,index,Picture(320,200,background,palette)


def high_resolution_picture(root):
    """The five A pictures form one original 640x480, sixteen-color screen."""
    pictures=[read_picture(Path(root)/f'A{index}.PIC') for index in range(1,6)]
    if any((p.width,p.height)!=(640,80 if i==5 else 100) or max(p.pixels)>15
           for i,p in enumerate(pictures,1)):
        raise GameError('Invalid high-resolution Game Credits picture.')
    if any(p.palette!=pictures[0].palette for p in pictures):raise GameError('Credits picture palettes disagree.')
    return Picture(640,480,b''.join(p.pixels for p in pictures),pictures[0].palette)
