"""Original research cells and their static disc-animation endpoints."""

DISC_FRAMES = {1: 10, 2: 19, 3: 30, 4: 39, 5: 0}
RESEARCH_LABELS = ('', 'Can be developed', 'Under development',
                   'Can be analysed', 'Under analysis', 'Done')


def research_targets(state, catalog):
    """223D9..224A5: five columns, seven rows, left-shifted hit rectangles."""
    result = []
    for i, (row, definition) in enumerate(zip(state['products'], catalog['products'])):
        rect = (max(0, i % 5*32-2), 52+i//5*16, 32, 16)
        name = definition['name'] if row['research_state'] else ''
        hidden = i == 13 and not state['campaign']['hyperspace_allowed']
        if hidden:
            name = 'Unknown'
        result.append((rect, name, ('research', i+1) if row['research_state'] and not hidden else None))
    return result


def disc_copies(products):
    """22B5A..22CEB: original 31x14 disc strips from GRAFIKA/CDS."""
    return [((i % 5*32, 53+i//5*16), ((frame % 10)*32, (frame//10)*16, 31, 14))
            for i, row in enumerate(products)
            if (frame := DISC_FRAMES.get(row['research_state'])) is not None]
