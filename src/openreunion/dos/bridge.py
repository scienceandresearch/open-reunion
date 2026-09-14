"""Original control-room targets and transparent commander sprite placement.

Coordinates are in the original 320x200 display, including its 49-row header.
Recovered from 2FF90..30250 and 30D6C..30E41; see ORIGINAL-INTERFACE.md.
"""
from .commanders import ROLES

# Four dynamic commander records precede these eight fixed records in DOS.
ROOM_TARGETS = (
    ((42, 71, 38, 60), 'RESEARCH-DESIGN', 2),
    ((0, 71, 42, 79), 'MESSAGE', 4),
    ((163, 49, 30, 54), 'COMMANDERS', 14),
    ((255, 49, 65, 88), 'INFO-BUY', 23),
    ((0, 49, 80, 22), 'STARMAP', 34),
    ((81, 49, 48, 49), 'SPACE LOCAL', 45),
    ((194, 49, 53, 82), 'SHIP INFO', 13),
    ((73, 157, 190, 43), 'PLANET MAIN', 41),
)
COMMANDER_RECTS = ((245, 103, 50, 97), (200, 100, 46, 65),
                   (77, 87, 57, 84), (43, 105, 49, 95))
COMMANDER_SOURCES = (((152, 1), (203, 1), (254, 1)),
                     ((175, 100), (222, 100), (269, 100)),
                     ((1, 100), (59, 100), (117, 100)),
                     ((1, 1), (51, 1), (101, 1)))
# Original overlapping sprites draw fighter, builder, developer, pilot.
COMMANDER_DRAW_ORDER = (2, 1, 3, 0)


def available_commanders(state):
    campaign = state['campaign']
    return [i for i, role in enumerate(ROLES)
            if state['ranks'][role] and campaign['training_role'] != i+1
            and not (i == 3 and campaign['research_block_remaining'])]


def bridge_targets(state, catalog):
    targets = []
    for i in available_commanders(state):
        rank = state['ranks'][ROLES[i]]
        name = catalog['commanders'][3*i+rank-1]['name']
        targets.append((COMMANDER_RECTS[i], name, ('consult', ROLES[i])))
    # Keep all four record positions: original inactive records have no area.
    targets.extend([((0, 0, 0, 0), '', None)]*(4-len(targets)))
    targets.extend(ROOM_TARGETS)
    return targets
