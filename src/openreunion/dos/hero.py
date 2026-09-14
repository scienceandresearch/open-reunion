"""Original saved hero identity and its differently ordered portrait banks."""
from ..core import integer


def validate_hero(hero):
    integer(hero,'Hero',minimum=1,maximum=2)


def choice_at(x):
    """26CDD..26CF3: left half selects 2, right half selects 1."""
    integer(x,'Hero selection position',maximum=319)
    return 2 if x<160 else 1


def bridge_source(hero):
    validate_hero(hero)
    # DS9278 is 1 for hero 2 and 69 for hero 1 (26CF3..26D08).
    return (1 if hero==2 else 69,1,67,59)


def adviser_source(hero):
    validate_hero(hero)
    return (1 if hero==2 else 101,1,100,109)


def dialog_path(hero):
    validate_hero(hero)
    return f'PICS/SAJAT{hero}.PIC'
