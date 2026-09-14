"""Ground positioning metrics, class ranges and nearest living target."""
import struct
from ..core import GameError, integer
from .catalog import DATA_FILE_OFFSET


def read_ground_motion(data):
    return {key: list(struct.unpack_from("<5h", data, DATA_FILE_OFFSET+at))
            for key, at in (("x", 0x44), ("y", 0x4E))}


def pixel_position(row, motion):
    direction = row[8];integer(direction, "Ground direction", maximum=4)
    return (64+16*row[4]+motion["x"][direction]*row[10],
            3+16*row[5]+motion["y"][direction]*row[10])


def ground_distances(first, second, motion):
    """0xB0FA..0xB4A2: Manhattan, maximum-axis and squared metrics.

    Native Manhattan distance fixes the original unsigned underflow for
    separations below five pixels. None of these metrics uses square roots.
    """
    ax, ay = pixel_position(first, motion);bx, by = pixel_position(second, motion)
    dx, dy = abs(ax-bx), abs(ay-by)
    return (max(0, (dx+dy-5)//16+1), max(0, (max(dx, dy)-3)//16+1), (dx*dx+dy*dy+255)//256)


def can_attack(first, second, motion):
    """0xB4F3..0xB575: range eligibility only, not cooldown or troop life."""
    manhattan, maximum, squared = ground_distances(first, second, motion)
    kind = first[0]
    return (kind == 1 and maximum <= 1 or kind == 2 and manhattan <= 2
            or kind == 3 and maximum <= 2 or kind == 4 and (maximum <= 1 or 4 <= squared <= 16))


def nearest_ground_target(groups, opponents, selection, motion):
    """0xB9D0..0xBA55: first nearest positive-quantity opponent, or zero."""
    integer(selection, "Ground group", minimum=1, maximum=len(groups))
    best, target = 1000, 0
    for index, row in enumerate(opponents, 1):
        if struct.unpack("<h", bytes(row[1:3]))[0] <= 0:continue
        distance = ground_distances(groups[selection-1], row, motion)[2]
        if distance < best:best, target = distance, index
    return target
