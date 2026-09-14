"""Original intro animation containers and frame composition rules."""
import struct
from pathlib import Path

from ..core import GameError
from .assets import Picture, read_picture
from .story_cinema import read_main_animation, draw_frame

FRAME_COUNTS = {1: 6, 3: 26, 4: 42, 5: 16, 6: 51, 7: 31, 8: 28,
                10: 5, 11: 13, 12: 102, 13: 187, 14: 91, 15: 120,
                16: 18, 18: 85, 19: 52, 20: 29, 21: 42, 22: 17,
                23: 47, 24: 75}
ALTERNATE_FRAMES = (1, 2, 3, 2, 3, 2, 3, 2, 4, 1, 4, 1, 1, 3, 3,
                    2, 1, 4, 5, 3, 4, 5, 6, 7, 8, 9, 10, 2, 6, 9,
                    2, 4, 3, 9, 10)
PICTURE_PREFIXES = tuple(f'{index}x' for index in range(1, 22)) + ('10_2x',)
CONVERTED_ANIMATION_MAGIC = b'ORIA\1'


def frame_plan(asset):
    """Yield (one-based frame, redraw base first) in original clip order.

    ANIM7 always redraws frame one before its selected delta. ANIM11 draws
    its first frame normally, then follows the executable's repeated frame
    table with base-plus-delta composition. Other clips draw cumulatively.
    Timing, surrounding pictures and palette effects belong to the player.
    """
    if type(asset) is not int or asset not in FRAME_COUNTS:
        raise GameError('Unknown intro animation.')
    if asset == 11:
        return tuple((index, position != 0) for position, index in enumerate(ALTERNATE_FRAMES))
    return tuple((index, asset == 7) for index in range(1, FRAME_COUNTS[asset] + 1))


def read_animation_geometry(executable):
    if len(executable) < 0xF370 + 0x41 + 25 * 7:
        raise GameError('Truncated intro animation tables.')
    rows = {}
    for asset, count in FRAME_COUNTS.items():
        values = struct.unpack_from('<BHBHB', executable, 0xF370 + 0x41 + 7 * asset)
        if values != (count, 320, 200, 0, 0):
            raise GameError('Unsupported intro animation geometry.')
        rows[asset] = dict(zip(('frames', 'width', 'height', 'x', 'y'), values))
    if tuple(executable[0xF370 + 0x23:0xF370 + 0x45]) != ALTERNATE_FRAMES[1:]:
        raise GameError('Unsupported intro alternate frame table.')
    return rows


def animation_frames(data, asset):
    frame_plan(asset)  # Validate the asset before indexing the table.
    return read_main_animation(data, {'frames': FRAME_COUNTS[asset], 'width': 320, 'height': 200})


def clip_frames(data, asset, background):
    """Yield original frame indices and pixels, preserving the supplied screen."""
    frames, _ = animation_frames(data, asset)
    if len(background) != 64000:
        raise GameError('Intro background dimensions disagree.')
    pixels = bytes(background)
    for index, redraw_base in frame_plan(asset):
        if redraw_base:
            pixels = draw_frame(frames, 1, pixels)
        pixels = draw_frame(frames, index, pixels)
        yield index, pixels


def assemble_high_resolution(pictures, prefix):
    if prefix not in PICTURE_PREFIXES or len(pictures) != 5:
        raise GameError('Unknown high-resolution intro picture.')
    pixels = bytearray(640 * 480)
    top = 0
    for index, picture in enumerate(pictures, 1):
        height = 80 if index == 5 else 100
        width = 636 if (prefix, index) == ('19x', 5) else 640
        if (picture.width, picture.height) != (width, height):
            raise GameError('Invalid high-resolution intro picture dimensions.')
        if picture.palette != pictures[0].palette:
            raise GameError('Intro picture palettes disagree.')
        for row in range(height):
            start = (top + row) * 640
            source = picture.pixels[row * width:(row + 1) * width]
            pixels[start:start + width] = bytes(value & 15 for value in source)
        top += height
    return Picture(640, 480, bytes(pixels), pictures[0].palette)


def high_resolution_picture(root, prefix):
    """Assemble five strips into a 640x480 intro picture.

    The original VGA converter retains only the low four bits of each index.
    20X4 contains one index 239, which therefore displays as 15. The supplied
    19X5 black strip is four columns short; fill its missing border with black
    instead of exposing whatever bytes happen to remain in a reused buffer.
    """
    if prefix not in PICTURE_PREFIXES:
        raise GameError('Unknown high-resolution intro picture.')
    pictures = [read_picture(Path(root) / f'{prefix}{index}.PIC') for index in range(1, 6)]
    return assemble_high_resolution(pictures, prefix)


def converted_animation(data, asset):
    """Wrap a validated original container for a self-contained bundle."""
    animation_frames(data, asset)
    return CONVERTED_ANIMATION_MAGIC + bytes([asset]) + data


def decode_converted_animation(data, asset):
    if (not isinstance(data, bytes) or len(data) < len(CONVERTED_ANIMATION_MAGIC) + 1
            or not data.startswith(CONVERTED_ANIMATION_MAGIC)
            or data[len(CONVERTED_ANIMATION_MAGIC)] != asset):
        raise GameError('Invalid converted intro animation.')
    raw = data[len(CONVERTED_ANIMATION_MAGIC) + 1:]
    return animation_frames(raw, asset)[0]
