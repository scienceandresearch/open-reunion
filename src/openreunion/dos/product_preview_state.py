"""Pure original Info/Buy product-preview angle state.

The constants are the three bytes copied from DS:5713 + 3*product.  The
initializer and frame routine at 326AA..3285D and 3200A..32212 keep three
angle words, advance each by its product step modulo 1080, and pass each word
divided by three to the transform.  This module has no renderer or timer.
"""
from dataclasses import dataclass

from ..core import GameError, integer


MODULUS = 1080
ANGLE_STEPS = (
    (5, 0, 0), (5, 0, 0), (5, 3, 1), (0, 5, 3), (5, 0, 0),
    (5, 3, 1), (5, 0, 0), (5, 3, 1), (5, 3, 1), (5, 0, 0),
    (5, 3, 1), (5, 0, 0), (5, 0, 0), (2, 3, 5), (3, 4, 2),
    (3, 4, 2), (5, 0, 0), (5, 3, 1), (5, 3, 1), (5, 3, 1),
    (5, 0, 0), (5, 0, 0), (2, 3, 1), (2, 3, 5), (5, 0, 0),
    (5, 3, 1), (2, 3, 4), (5, 0, 0), (5, 0, 0), (5, 0, 0),
    (5, 0, 0), (5, 0, 0), (5, 0, 0), (5, 0, 0), (5, 3, 1),
)


def _product(product):
    return integer(product, 'Product preview id', minimum=1, maximum=len(ANGLE_STEPS))


def _angles(angles):
    if not isinstance(angles, (tuple, list)) or len(angles) != 3:
        raise GameError('Product preview state must contain three angles.')
    return tuple(integer(value, f'Product preview angle {axis}', minimum=0, maximum=MODULUS - 1)
                 for axis, value in zip('xyz', angles))


def initial_angles(product):
    """Return the exact initializer values for a one-based product id."""
    product = _product(product)
    if product == 14:
        return 215, 45, 54
    if product == 24:
        return 0, 21, 32
    return 0, 0, 300


def angle_steps(product):
    """Return the original three unsigned DS:5713 increments for ``product``."""
    return ANGLE_STEPS[_product(product) - 1]


@dataclass(frozen=True)
class ProductPreviewState:
    """One initialized product preview, advanced once for each presentation tick."""
    product: int
    angles: tuple[int, int, int]

    def __post_init__(self):
        _product(self.product)
        object.__setattr__(self, 'angles', _angles(self.angles))

    @classmethod
    def initial(cls, product):
        product = _product(product)
        return cls(product, initial_angles(product))

    @property
    def steps(self):
        return angle_steps(self.product)

    @property
    def transform_indices(self):
        """The integer state/3 values supplied to original transform 34150."""
        return tuple(value // 3 for value in self.angles)

    def advance(self):
        """Return the state after one original preview frame/update call."""
        return ProductPreviewState(self.product, tuple(
            (value + step) % MODULUS for value, step in zip(self.angles, self.steps)))
