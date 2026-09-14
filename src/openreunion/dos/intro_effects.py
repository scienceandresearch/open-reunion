"""Pure pixel operations used by the original intro presentation."""
from ..core import GameError, integer


def fade_levels(steps, kind):
    """Original intro palette positions, including its asymmetric half fade."""
    integer(steps, 'Intro fade steps', minimum=1, maximum=32767)
    if kind in ('in', 'from_white'):
        return tuple(range(steps + 1))
    if kind in ('out', 'to_white'):
        return tuple(range(steps, -1, -1))
    if kind == 'to_half_white':
        return tuple(range(steps, steps // 2 - 1, -1))
    if kind == 'from_half_white':
        return tuple(range(steps // 2, steps + 1))
    raise GameError('Unknown intro fade operation.')


def shake_frame(previous, picture, amplitude, x, y):
    """0x235B: jitter a cropped picture while retaining the screen's border.

    The intro controller supplies two independent random offsets per frame;
    drawing must not consume the campaign's random stream. The original uses
    amplitude 3, leaving an asymmetric one/two-pixel border on the screen.
    """
    integer(amplitude, 'Intro shake amplitude', minimum=1, maximum=199)
    integer(x, 'Intro shake horizontal offset', maximum=amplitude - 1)
    integer(y, 'Intro shake vertical offset', maximum=amplitude - 1)
    if len(previous) != 64000 or len(picture) != 64000:
        raise GameError('Intro shake pictures must be 320 by 200.')
    pixels = bytearray(previous)
    margin = amplitude // 2
    width = 320 - amplitude
    for row in range(200 - amplitude):
        source = (row + y) * 320 + x
        target = (row + margin) * 320 + margin
        pixels[target:target + width] = picture[source:source + width]
    return bytes(pixels)


def shake_plan(seed, repeats, amplitude=3):
    """Return the intro's next private seed and original ordered (x,y) draws.

    The intro executable owns its random state separately from REUNION.PRG.
    The player must retain this returned seed in its intro controller, never
    write it into a campaign or consume campaign randomness for this effect.
    """
    from .campaign import random_bounded
    integer(seed, 'Intro random seed', maximum=2**32 - 1)
    integer(repeats, 'Intro shake repetitions', maximum=32767)
    integer(amplitude, 'Intro shake amplitude', minimum=1, maximum=199)
    offsets = []
    for _ in range(repeats):
        seed, x = random_bounded(seed, amplitude)
        seed, y = random_bounded(seed, amplitude)
        offsets.append((x, y))
    return seed, tuple(offsets)


def white_flash_dac(current, palette, level, divisor=5, first=0, last=255):
    """0x3608: one fixed white blend on a range of six-bit VGA DAC colors.

    Level zero is white and level=divisor restores the loaded palette. There
    is no internal wait: the sequence controls the hold between these flashes.
    Colors outside the selected inclusive range retain the current DAC value.
    """
    integer(divisor, 'Intro flash divisor', minimum=1, maximum=520)
    integer(level, 'Intro flash level', maximum=divisor)
    integer(first, 'Intro flash first color', maximum=255)
    integer(last, 'Intro flash last color', minimum=first, maximum=255)
    if any(len(p) != 768 or any(v > 63 or v < 0 for v in p) for p in (current, palette)):
        raise GameError('Intro flash palettes must contain 256 six-bit RGB colors.')
    result = bytearray(current)
    result[first * 3:(last + 1) * 3] = bytes(
        63 - (63 - value) * level // divisor
        for value in palette[first * 3:(last + 1) * 3])
    return bytes(result)


def scroll_frame(previous, incoming, remaining_rows):
    """0x2927: slide the incoming picture's bottom upward over the old screen.

    The original draws remaining_rows 199 down through zero, one per retrace.
    A value of 200 represents the unchanged starting picture for the player.
    Palette changes occur after the final frame and belong to presentation.
    """
    integer(remaining_rows, 'Intro scroll position', maximum=200)
    if len(previous) != 64000 or len(incoming) != 64000:
        raise GameError('Intro scroll pictures must be 320 by 200.')
    split = remaining_rows * 320
    return bytes(incoming[split:]) + bytes(previous[:split])


def flight_frame(stars, planet, ship, frame):
    """0x2A66: wrap stars and slide transparent planet/ship layers from left.

    Pass ship=None for the original reduced-detail branch. Normal modern
    playback can use both layers, independently of the old speed benchmark.
    Palette ownership and fourteen-tick deadlines belong to the player.
    """
    integer(frame, 'Intro flight frame', maximum=167)
    if any(len(pixels) != 64000 for pixels in (stars, planet)) or (ship is not None and len(ship) != 64000):
        raise GameError('Intro flight layers must be 320 by 200.')
    shift = (frame * 2) % 320 + 1
    planet_width = max(0, (frame * 2 - 80) * 5 // 4)
    ship_width = max(0, (frame * 2 - 176) * 2)
    pixels = bytearray(64000)
    for row in range(200):
        start = row * 320
        background = stars[start:start + 320]
        pixels[start:start + 320] = background[-shift:] + background[:-shift]
        for layer, width in ((planet, planet_width), (ship, ship_width)):
            if layer is None or width == 0:
                continue
            for column, value in enumerate(layer[start + 320 - width:start + 320]):
                if value:
                    pixels[start + column] = value
    return bytes(pixels)
