"""Bounded fixed-point product-preview transform, original entry 34150.

This is model arithmetic only. Projection, normal generation, depth-order
corrections and rasterization remain separate.
"""
import math

from ..core import GameError, integer


COSINE = tuple(round(500 * math.cos(math.radians(angle))) for angle in range(360))


def _div500(value):
    return -(abs(value) // 500) if value < 0 else value // 500


def _signed_byte(value):
    value &= 255
    return value - 256 if value >= 128 else value


def rotation_matrix(indices, mode=1):
    """Return three integer rows, retaining original intermediate truncation."""
    if not isinstance(indices, (tuple, list)) or len(indices) != 3:
        raise GameError('Product transform requires three angle indexes.')
    angles = tuple(integer(value, 'Product transform index', maximum=359) for value in indices)
    integer(mode, 'Product transform mode', minimum=1, maximum=2)
    ca, cb, cc = (COSINE[value] for value in angles)
    sa, sb, sc = (COSINE[(value - 90) % 360] for value in angles)
    t = _div500
    rows = ((t(cb * ca), t(cb * sa), sb),
            (t(t(sc * sb) * ca) + t(cc * sa),
             t(t(sc * sb) * sa) + t(-cc * ca), t(-sc * cb)),
            (t(sc * sa) - t(t(cc * sb) * ca),
             t(-sc * ca) - t(t(cc * sb) * sa), t(cc * cb)))
    return (rows[1], rows[0], rows[2]) if mode == 2 else rows


def transform_points(points, indices, scale, mode=1):
    """Transform signed word triples using their low signed bytes.

    The original multiplies each byte by the signed byte scale, accumulates
    matrix dot products in 32 bits, and writes each signed high word. Arithmetic
    right shift deliberately differs from truncation toward zero here.
    """
    if not isinstance(points, (tuple, list)) or not 1 <= len(points) <= 200:
        raise GameError('Product transform requires 1 through 200 points.')
    integer(scale, 'Product transform scale byte', maximum=255)
    factor = _signed_byte(scale)
    matrix = rotation_matrix(indices, mode)
    result = []
    for point in points:
        if not isinstance(point, (tuple, list)) or len(point) != 3:
            raise GameError('Product transform point requires three coordinates.')
        values = tuple(_signed_byte(integer(value, 'Product transform coordinate',
                                           minimum=-32768, maximum=32767)) * factor for value in point)
        transformed = []
        for row in matrix:
            total = sum(value * coefficient for value, coefficient in zip(values, row))
            high = (total >> 16) & 65535
            transformed.append(high - 65536 if high >= 32768 else high)
        result.append(tuple(transformed))
    return tuple(result)
