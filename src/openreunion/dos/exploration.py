"""Daily hidden-planet discovery after each world's survey and colony updates."""
from .campaign import random_bounded


def discover_planet(visibility,known,system,moon,observatories,mental_radar,fleets,seed,discovered_today):
    """1213A..123EA: one discovery per daily world pass, with ordered RNG draws.

    Visibility 254 permits observatory or passing-fleet discovery; 253 needs
    an observatory; 252 needs completed Mental radar. Other values are retained.
    A day's earlier discovery suppresses writes, but does not suppress rolls.
    """
    method=None
    if observatories>0 and moon==0 and visibility in (254,253) and known==1:
        seed,roll=random_bounded(seed,50)
        if roll==1 and not discovered_today:
            visibility=0;discovered_today=True;method='observatory'
    if moon==0 and visibility==254 and known==1:
        seed,roll=random_bounded(seed,5)
        if roll==1 and not discovered_today:
            for row in fleets:
                if row[19]==system and row[22]>2:
                    method='satellite carrier' if row[0]==4 else 'fleet'
            if method is not None:visibility=0;discovered_today=True
    if mental_radar==5 and moon==0 and visibility==252 and known==1:
        seed,roll=random_bounded(seed,10)
        if roll==1 and not discovered_today:
            visibility=0;discovered_today=True;method='mental radar'
    return visibility,seed,discovered_today,method
