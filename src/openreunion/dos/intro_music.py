"""Intro-specific module compatibility without relaxing general MOD validation."""
import hashlib

from .module_music import decode_module
from .victory_cinema import module_rows

INTRO2_SOURCE_SHA256 = 'ec38705500e53d583d3e5d6d5d2081f5155ee9791361885141bd4484a8de6879'
INTRO2_MISSING_SAMPLE_BYTES = 202


def decode_intro_module(data):
    """Pad only the known original INTRO2's missing final sample bytes.

    Its last nonempty sample declares 9,678 bytes but supplies 9,476. No
    matching complete sample exists in the supplied MOD assets. Silence is
    an explicit compatibility repair, not a reconstruction of lost audio.
    Original input files are untouched; every other file remains subject to
    the normal strict decoder, including unknown truncations.
    """
    if isinstance(data, bytes) and hashlib.sha256(data).hexdigest() == INTRO2_SOURCE_SHA256:
        data += bytes(INTRO2_MISSING_SAMPLE_BYTES)
    return decode_module(data)


def cue_clock(song):
    """Intro row times matching the audio renderer's MOD compatibility mode.

    Several supplied tracks contain F00 commands. libopenmpt ignores these
    without changing speed; treating them as a stop truncates valid later
    rows in BASE2 and TUNNEL. Keep other callers' strict default unchanged.
    """
    return module_rows(song, pattern_loops=True, ignore_zero_speed=True)
