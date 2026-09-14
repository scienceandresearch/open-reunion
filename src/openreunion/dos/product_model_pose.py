"""Pure original product-model centroid and post-centroid pivot arithmetic.

The centroid follows 33122..332D8: every signed model coordinate is scaled
with truncation toward zero by ten, then each axis mean is rounded half away
from zero.  ``adjusted_pivot`` implements only 332DC..338E4.  It deliberately
does not load models, rotate parts, calculate normals, or render pixels.
"""

from ..core import GameError, integer


def _s16(value):
    """Return the low signed 16-bit word, matching AX/word destination writes."""
    value &= 0xffff
    return value - 0x10000 if value >= 0x8000 else value


def _coordinate(value, label):
    return integer(value, label, minimum=-0x8000, maximum=0x7fff)


def _centroid_input(points):
    if not isinstance(points, (tuple, list)) or not points:
        raise GameError('Product model points must be a nonempty sequence.')
    result = []
    for index, point in enumerate(points, 1):
        if not isinstance(point, (tuple, list)) or len(point) != 3:
            raise GameError(f'Product model point {index} must have three coordinates.')
        result.append(tuple(_coordinate(value, f'Product model point {index} coordinate {axis}')
                            for axis, value in zip('xyz', point)))
    return result


def _trunc_zero(value, divisor):
    return -(abs(value) // divisor) if value < 0 else value // divisor


def _round_half_away(total, count):
    sign = -1 if total < 0 else 1
    whole, remainder = divmod(abs(total), count)
    return sign * (whole + (remainder * 2 >= count))


def model_centroid(points):
    """Return the original scaled, half-away centroid for one model part."""
    points = _centroid_input(points)
    scaled = [tuple(_trunc_zero(value, 10) for value in point) for point in points]
    return tuple(_round_half_away(sum(point[axis] for point in scaled), len(scaled))
                 for axis in range(3))


def _abs_word(value):
    """3312C-style signed word absolute value, including -32768 overflow."""
    sign = -1 if value < 0 else 0
    return _s16((value ^ sign) - sign)


def _divide_by_own_abs(value):
    """Signed IDIV of a word by its original overflow-preserving absolute word."""
    divisor = _abs_word(value)
    if divisor == 0:
        raise GameError('Product 24 parts 1 through 8 require a nonzero x centroid.')
    quotient = abs(value) // abs(divisor)
    if (value < 0) != (divisor < 0):
        quotient = -quotient
    return _s16(quotient)


def adjusted_pivot(product, part, centroid):
    """Apply the original product-specific pivot adjustments.

    ``product`` is the one-based product id and ``part`` the one-based model
    part.  Inputs and all word arithmetic are signed 16-bit.  Product 24,
    parts 1--8 cannot represent a zero X centroid in the original because it
    executes ``IDIV 0``; this safe implementation rejects it explicitly.
    """
    integer(product, 'Product id', minimum=1, maximum=35)
    integer(part, 'Product model part', minimum=1, maximum=17)
    if not isinstance(centroid, (tuple, list)) or len(centroid) != 3:
        raise GameError('Product model centroid must have three signed coordinates.')
    x, y, z = tuple(_coordinate(value, f'Product model centroid {axis}')
                    for axis, value in zip('xyz', centroid))

    if product == 6:
        if part == 2:
            z = 14
        elif part == 3:
            x = -4
        elif part == 4:
            x = 4
        y = 0
        x, z = _s16(x * 3), _s16(z * 3)
    elif product == 9:
        if part == 2:
            y = 1
        elif part == 3:
            y = -120
        elif part in (4, 5):
            y, z = 120, 0
    elif product == 11 and part == 2:
        y = _s16(y + 11)
    elif product == 12 and part == 7:
        z = _s16(z + 10)
    elif product == 14:
        z = 0
        if part == 1:
            x, y = 0, 0
        elif part == 2:
            x, y = -4, -100
        elif part == 3:
            x, y = 4, -100
        elif 4 <= part <= 6:
            x = -4
        elif 7 <= part <= 11:
            x = 0
        elif 12 <= part <= 14:
            x = 4
        if part in (4, 7, 8, 12):
            z = 20
        elif part in (6, 10, 11, 14):
            z = -20
        if part in (4, 8, 12):
            y = 0
        elif part in (5, 9, 13):
            y = 40
        elif part in (6, 10, 14):
            y = 0
        elif part in (7, 11):
            y = -5
    elif product == 15:
        z = 0
        if part == 1:
            y = 100
        elif part > 1:
            y = -100
        if part == 3:
            x = -8
        elif part == 4:
            x = 8
    elif product == 16:
        y, z = 0, 0
    elif product == 19:
        if part <= 5:
            x = 0
        z = -50 if 2 <= part <= 5 else 0
        if part == 1:
            y = 0
        elif part in (6, 7):
            y = 3
        elif part == 2:
            y = 2
        elif part == 3:
            y = -10
        elif part == 4:
            y = -20
        elif part == 5:
            y = -30
    elif product == 21:
        if part > 2:
            x = 0
        y = 0 if part != 6 else -10
        z = 0
        if part == 5:
            y = -5
    elif product == 23:
        z = 0
        if part == 2:
            z = -7
        elif part == 7:
            z = 120
        x = {2: -5, 3: -110, 4: -108, 5: 108, 6: 110}.get(part, 0)
        y = {2: -9, 4: 5, 5: 5}.get(part, 0)
    elif product == 24:
        if part <= 8:
            if _abs_word(x) == 33:
                x = _s16(_divide_by_own_abs(x) * 5)
            if _abs_word(y) == 33:
                y = _s16(_divide_by_own_abs(y) * 5)
            if _abs_word(x) == 67:
                x = _s16(_divide_by_own_abs(x) * 20)
            if _abs_word(y) == 67:
                y = _s16(_divide_by_own_abs(y) * 20)
            x = _s16(_s16(_divide_by_own_abs(x) * 100) + x)
        if part == 10:
            x = -120
        elif part == 11:
            x = 120
    elif product == 25:
        z = 0
    elif product == 26:
        y, z = 0, 0
    elif product == 32:
        if part <= 4:
            y = 0
        if part > 4:
            x = 0
        z = 0
        if part == 1:
            x = -5
        elif part == 2:
            x = 5
        elif part in (3, 5, 6, 7):
            z = -25
        if part in (3, 4):
            x = 0
    return _s16(x), _s16(y), _s16(z)
