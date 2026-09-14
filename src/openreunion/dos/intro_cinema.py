"""Original INTRO.PRG film script and deterministic presentation timeline."""
from dataclasses import dataclass, replace
from fractions import Fraction

from .intro_assets import frame_plan
from .intro_effects import fade_levels, shake_plan
from .intro_music import cue_clock
from .video_timing import FRAME_DOTS, PIXEL_CLOCK_HZ


TRACKS = ('INTRO1', 'INTRO2', 'INTRO3', 'INTRO4', 'REBEL', 'BASE1',
          'BASE2', 'TUNNEL', 'INTRO5', 'INTRO6', 'INTRO7')
LOW_PICTURES = ('ATTACK', 'BASE', 'BASE0', 'FOLYOSO', 'GABOR', 'LEADER',
                'MON1', 'MON2', 'MON3', 'MUSZER', 'PAL1', 'PAL3', 'PAL4',
                'PAL5', 'PAL6', 'PAL7', 'PAL8', 'PAL10', 'PAL11', 'PAL11X',
                'PAL12', 'PAL13', 'PAL14', 'PAL15', 'PAL16', 'PAL20', 'PAL21',
                'PAL22', 'PLANET', 'PLANET2', 'SHIP', 'STARS', 'TRACE')


def script():
    """Semantic transcription of all presentation calls in one original pass.

    Cue coordinates are the original one-based order and row counters.  The
    final input operation returns to the top-level repeat jump; the player owns
    that repeat/abort policy rather than hiding it in this pure script.
    """
    return (
        ('music', 'INTRO1'), ('picture', 'PAL20', 1, 1, 5, 70),
        ('animation', 20, 1, 15, 84, 0), ('animation', 21, 2, 3, 84, 0),
        ('wait_fade', 2, 16, 30),
        ('highres', '1x', 1, 1, 10, 2, 30, 100),
        ('highres', '2x', 3, 8, 70, 3, 54, 100),
        ('highres', '3x', 4, 25, 70, 4, 36, 100),
        ('highres', '4x', 6, 2, 140, 6, 56, 100), ('cue', 7, 48),
        ('music', 'INTRO2'),
        ('highres', '5x', 0, 1, 30, 2, 1, 100),
        ('highres', '6x', 3, 15, 70, 3, 32, 100), ('cue', 5, 32),
        ('music', 'INTRO3'),
        ('highres', '7x', 0, 1, 30, 1, 18, 300),
        ('highres', '8x', 2, 40, 70, 3, 1, 5),
        ('highres', '9x', 3, 50, 70, 4, 1, 5),
        ('highres', '10x', 4, 50, 70, 5, 1, 5),
        ('highres', '10_2x', 5, 20, 70, 5, 32, 100),
        ('highres', '11x', 5, 45, 70, 5, 58, 100), ('cue', 7, 14),
        ('music', 'INTRO4'),
        ('highres', '12x', 0, 1, 30, 2, 1, 20),
        ('highres', '13x', 3, 16, 70, 4, 1, 100),
        ('highres', '14x', 5, 40, 70, 6, 1, 100),
        ('highres', '15x', 7, 12, 70, 8, 1, -1),
        ('wait_fade', 8, 40, 70), ('cue', 8, 60),
        ('music', 'REBEL'), ('picture', 'STARS', 1, 1, 5, 5),
        ('flight', 1, 6), ('picture', 'PAL12', 2, 64, 5, 5),
        ('animation', 12, 3, 16, 155, 0), ('animation', 13, 4, 56, 41, 0),
        ('picture', 'BASE', 6, 24, 5, 5), ('picture', 'PAL15', 6, 46, 99, 40),
        ('animation', 15, 8, 8, 42, 0), ('animation', 14, 9, 5, 50, 0),
        ('cue', 10, 6), ('fade', 'out', 180),
        ('music', 'BASE1'), ('picture', 'BASE0', 1, 10, 5, 255),
        ('scroll', 'BASE', 1, 32), ('picture', 'PAL1', 2, 1, 5, 5),
        ('picture', 'BASE', 3, 1, 5, 5), ('picture', 'PAL11X', 3, 10, 5, 5),
        ('picture', 'PAL1', 4, 1, 5, 5),
        ('animation', 1, 4, 55, 42, 0), ('animation', 1, 4, 63, 42, 0),
        ('load_wait', 'PAL1', 5, 1), ('shake', 15, 1, 3),
        ('picture', 'BASE', 5, 12, 5, 5), ('cue', 5, 20),
        ('fade', 'to_white', 2), ('fade', 'from_half_white', 2), ('cue', 5, 24),
        ('fade', 'to_white', 2), ('fade', 'from_half_white', 2),
        ('picture', 'FOLYOSO', 5, 40, 5, 5), ('cue', 5, 41),
        ('shake', 20, 1, 3), ('picture', 'BASE', 6, 1, 5, 5),
        ('animation', 3, 7, 1, 84, 1), ('picture', 'MUSZER', 7, 32, 5, 5),
        ('picture', 'BASE', 8, 1, 5, 5), ('picture', 'TRACE', 9, 1, 5, 5),
        ('animation', 4, 9, 10, 70, 1), ('picture', 'PAL5', 10, 10, 5, 5),
        ('animation', 5, 10, 30, 64, 0), ('picture', 'BASE', 11, 1, 5, 5),
        ('animation', 6, 12, 5, 70, 1), ('animation', 7, 13, 1, 74, 1),
        ('animation', 8, 13, 36, 70, 1), ('fade', 'to_half_white', 10),
        ('fade', 'from_white', 70), ('cue', 14, 38),
        ('music', 'BASE2'), ('picture', 'PAL11', 2, 32, 5, 5),
        ('cue', 2, 54), ('shake', 15, 1, 3), ('cue', 3, 22),
        ('shake', 15, 1, 3), ('picture', 'PAL10', 4, 1, 5, 5),
        ('animation', 10, 4, 39, 42, 0), ('picture', 'PAL11', 5, 1, 5, 5),
        ('cue', 5, 22), ('shake', 15, 1, 3),
        ('animation', 11, 6, 28, 120, 0),
        ('picture', 'MON1', 0, 0, 0, 0), ('wait', 40),
        ('picture', 'MON2', 0, 0, 0, 0), ('wait', 40),
        ('picture', 'MON3', 0, 0, 0, 0), ('cue', 7, 6),
        ('music', 'TUNNEL'), ('picture', 'PAL16', 1, 1, 5, 70),
        ('animation', 16, 3, 1, 42, 0), ('animation', 23, 4, 4, 42, 0),
        ('animation', 24, 4, 4, 42, 0), ('animation', 18, 5, 2, 42, 0),
        ('animation', 19, 5, 45, 42, 0),
        ('flash', 2), ('flash', 1), ('flash', 0), ('show_loaded', 'ATTACK'),
        ('cue', 6, 20), ('fade', 'from_white', 100), ('cue', 6, 64),
        ('fade', 'out', 100),
        ('music', 'INTRO5'),
        ('highres', '16x', 0, 0, 0, 1, 32, 100),
        ('highres', '17x', 5, 34, 70, 6, 1, -1),
        ('highres', '18x', 7, 32, 70, 8, 1, 70),
        ('wait_fade', 8, 40, 70), ('cue', 8, 63),
        ('music', 'INTRO6'),
        ('highres', '19x', 0, 0, 0, 2, 1, 10),
        ('highres', '20x', 2, 24, 20, 2, 32, 20),
        ('highres', '21x', 3, 10, 70, 3, 40, 70),
        ('wait_fade', 4, 16, 70), ('cue', 4, 24),
        ('music', 'INTRO7'), ('picture', 'PAL22', 1, 1, 5, 70),
        ('animation', 22, 1, 63, 70, 0), ('wait_fade', 3, 1, 70),
        ('picture', 'LEADER', 3, 18, 5, 140),
        ('picture', 'GABOR', 7, 1, 5, 70), ('wait_fade', 7, 63, 70),
        ('input',),
    )


@dataclass(frozen=True)
class Shot:
    operation: tuple = ()
    level: int = 1
    divisor: int = 1
    white: bool = False
    flash: int = -1
    high_resolution: bool = False


@dataclass(frozen=True)
class Film:
    entries: tuple
    duration: int
    music: tuple
    next_seed: int


def timeline(songs, *, seed=1994, reduced_detail=False):
    """Compile the complete pass without touching campaign clocks or RNG."""
    low_period = Fraction(FRAME_DOTS, PIXEL_CLOCK_HZ)
    high_period = Fraction(800 * 525, PIXEL_CLOCK_HZ)
    now = Fraction(0); track_start = Fraction(0); rows = {}; shot = Shot()
    entries = []; music = []; call = 0

    def emit(duration=Fraction(0), *, force=False):
        nonlocal now, shot
        if duration > 0 or force:
            entries.append((int(now * 1_000_000_000), shot))
            now += duration
            shot = replace(shot, operation=())

    def cue(order, row):
        if order == 0 and row == 0:return
        coordinate = (order - 1, row - 1)
        # The DOS gate is >=, so a pattern jump across the requested row also
        # releases it. Several original high-resolution cues rely on this.
        target = track_start + min(time for position, time in rows.items()
                                   if position >= coordinate)
        emit(max(Fraction(0), target - now))

    def fade(kind, steps):
        nonlocal shot
        white = kind not in ('in', 'out')
        for level in fade_levels(steps, kind):
            shot = replace(shot, level=level, divisor=steps, white=white, flash=-1)
            emit(high_period if shot.high_resolution else low_period)

    def visual(operation):
        nonlocal shot
        shot = replace(shot, operation=operation, flash=-1)
        emit(force=True)

    def timed_frames(operations, milliseconds, period=low_period):
        nonlocal now
        origin = now
        for index, operation in enumerate(operations):
            visual(operation)
            if index + 1 < len(operations):
                due = origin + Fraction((index + 1) * milliseconds, 1000)
                edge = due // period + 1
                emit(max(period, edge * period - now))

    for operation in script():
        kind, *args = operation
        if kind == 'music':
            name = args[0]; rows, _ = cue_clock(songs[name]); track_start = now
            music.append((int(now * 1_000_000_000), name)); continue
        if kind == 'cue':cue(*args);continue
        if kind == 'picture':
            name, order, row, outward, inward = args; cue(order, row)
            if outward:fade('out', outward)
            shot = replace(shot, high_resolution=False)
            visual(('picture', name))
            if inward:fade('in', inward)
        elif kind == 'load_wait':
            name, order, row = args; cue(order, row); visual(('load', name))
        elif kind == 'show_loaded':
            shot = replace(shot, high_resolution=False);visual(('show_loaded', args[0]))
        elif kind == 'highres':
            name, order, row, outward, end_order, end_row, inward = args; cue(order, row)
            if outward:fade('out', outward)
            shot = replace(shot, high_resolution=True)
            visual(('highres', name)); cue(end_order, end_row)
            if inward > 0:fade('in', inward)
            elif inward == -1:
                fade('in', 5); fade('to_half_white', 5); fade('from_white', 10)
        elif kind == 'wait_fade':cue(args[0], args[1]);fade('out', args[2])
        elif kind == 'fade':fade(*args)
        elif kind == 'animation':
            asset, order, row, delay, palette = args; cue(order, row); call += 1
            plan = frame_plan(asset); origin = now
            for position, (frame, redraw) in enumerate(plan):
                visual(('animation', call, asset, frame, redraw, bool(palette)))
                if asset == 16 and 2 <= frame < 5:
                    seed, offsets = shake_plan(seed, 1, 3)
                    x, y = offsets[0]; visual(('shake', call * 1000 + frame, 3, x, y))
                if asset == 19 and frame in (51, 52):
                    shot = replace(shot, flash={51: 4, 52: 3}[frame]);emit(force=True)
                if position + 1 < len(plan):
                    due = origin + Fraction((position + 1) * delay, 1000)
                    edge = due // low_period + 1
                    emit(max(low_period, edge * low_period - now))
        elif kind == 'shake':
            repeats, wait, amplitude = args; call += 1
            seed, offsets = shake_plan(seed, repeats, amplitude)
            timed_frames([('shake', call, amplitude, x, y) for x, y in offsets], wait)
        elif kind == 'scroll':
            name, order, row = args; cue(order, row); call += 1
            for remaining in range(199, -1, -1):
                visual(('scroll', call, name, remaining)); emit(low_period)
        elif kind == 'flight':
            cue(*args); call += 1
            timed_frames([('flight', call, frame, bool(reduced_detail)) for frame in range(168)], 14)
        elif kind == 'flash':
            shot = replace(shot, flash=args[0]); emit(low_period)
        elif kind == 'wait':emit(Fraction(args[0], 1000))
        elif kind == 'input':pass
        else:raise AssertionError('Unknown intro operation: ' + kind)
    return Film(tuple(entries), int(now * 1_000_000_000), tuple(music), seed)
