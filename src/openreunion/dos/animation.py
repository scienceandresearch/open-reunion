"""Bounded SpidyAnim frame containers and base-plus-delta reconstruction."""
import struct
from ..core import GameError, integer


def decode_frame(data, background=None):
    """0x3169C: native palette indices; preserve pixels covered by skip tokens.

    DOS adds 64 to written indices in its shared display palette. Native images
    retain source palette indices; palette remapping belongs to presentation.
    """
    if len(data) < 13 or data[:9] != b"SpidyAnim":raise GameError("Invalid SpidyAnim frame header.")
    width,height = struct.unpack_from("<HH",data,9)
    if not 1 <= width <= 320 or not 1 <= height <= 200:raise GameError("Animation dimensions exceed the display.")
    size = width*height
    if background is not None and len(background) != size:raise GameError("Animation background dimensions disagree.")
    pixels = bytearray(size) if background is None else bytearray(background)
    position = 13;destination = 0
    def take(count):
        nonlocal position
        if position+count > len(data):raise GameError("Truncated animation token.")
        value = data[position:position+count];position += count;return value
    while destination < size:
        token = take(1)[0];count = 1;value = None
        if token < 128:value = token
        elif token in (128,192):
            count = struct.unpack("<H",take(2))[0]
            if token == 192:value = take(1)[0]
        elif token < 192:count = token & 63
        else:count = token & 63;value = take(1)[0]
        if count == 0 or destination+count > size:raise GameError("Animation run exceeds its frame or makes no progress.")
        if value is None and background is None:raise GameError("Animation delta requires a complete base frame.")
        if value is not None:pixels[destination:destination+count] = bytes([value])*count
        destination += count
    if position != len(data):raise GameError("Animation frame has trailing payload.")
    return width,height,bytes(pixels)


def read_animation(data, *, frames, width, height):
    """Container lengths count compressed bytes only, excluding the 13-byte header.

    Zero-length entries reuse the nearest preceding frame. Each actual frame is
    reconstructed over frame one, not cumulatively over the preceding frame.
    """
    integer(frames,"Animation frame count",minimum=1,maximum=140)
    if len(data) > 2*1024*1024:raise GameError("Animation exceeds the input limit.")
    decoded = [];position = 0;base = None
    for index in range(frames):
        if position+2 > len(data):raise GameError("Truncated animation container.")
        length = struct.unpack_from("<H",data,position)[0];position += 2
        if not length:
            if not decoded:raise GameError("The base animation frame is missing.")
            decoded.append(decoded[-1]);continue
        end = position+13+length
        if end > len(data):raise GameError("Truncated compressed animation frame.")
        w,h,pixels = decode_frame(data[position:end],base)
        if (w,h) != (width,height):raise GameError("Animation frame differs from its executable metadata.")
        if base is None:base = pixels
        decoded.append(pixels);position = end
    if position != len(data):raise GameError("Animation frame count does not match the container.")
    return decoded
