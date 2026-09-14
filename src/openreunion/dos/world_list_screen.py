"""Original Main Computer text rows, with native clickable world identities."""
from dataclasses import dataclass

from .world_lists import FILTERS, filtered_worlds, list_category

PREFIXES = {1: {1: 'Colony on ', 2: 'Miner station on '},
            2: {1: 'Accommodable ', 2: 'Mineable   '},
            3: {1: 'Aliens on       ', 2: 'Enemy colony on ', 3: 'Friendly colony on '}}


def list_lines(state, catalog, mode):
    """88AC..8ADF: one line per primary, two lines per qualifying moon.

    Correct the original 'Accomodable' typo. Keep original names, categories,
    indentation and system/primary context; do not expose race identities.
    """
    definitions = {w['id']: w for w in catalog['worlds']}
    rows = []
    for world, _ in filtered_worlds(state, catalog, FILTERS[mode]):
        prefix = PREFIXES[mode][list_category(state['worlds'][world['id']]['raw'], catalog, state['campaign'], mode)]
        system = catalog['system_names'][world['system']-1]
        if world['moon']:
            primary = definitions[f"{world['system']}:{world['planet']}:0"]
            rows.append((world['id'], prefix, system+' system planet '+primary['name']))
            rows.append((world['id'], ' '*len(prefix), 'moon '+world['name']))
        else:
            rows.append((world['id'], prefix, system+' system '+world['name']))
    return rows


@dataclass
class WorldListView:
    mode: int = 1
    offset: int = 0

    def sync(self, rows):
        self.offset = min(max(0, self.offset), max(0, len(rows)-15))

    def scroll(self, rows, amount):
        self.offset += amount
        self.sync(rows)

    def scroll_to(self, rows, y):
        # Original 8BA0..8C06 maps the scrollbar into count-15+3 rows.
        self.offset = (max(55, min(194,y))-55)*(len(rows)-12)//140
        self.sync(rows)

    def scrollbar(self, rows):
        self.sync(rows)
        if len(rows) <= 15:
            return (311,56,3,137)
        return (311,56+self.offset*135//(len(rows)-12),3,max(1,(2100//(len(rows)-12))//5))

    def targets(self, rows):
        self.sync(rows)
        return [((10,57+9*i,297,8), row[2], ('list_world',row[0]))
                for i,row in enumerate(rows[self.offset:self.offset+15])] + [
                    ((308,55,12,140), 'Scroll list', ('world_scroll',))]
