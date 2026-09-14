"""Info/Buy presentation state; orders remain transactional session commands."""
from dataclasses import dataclass


def display_number(value, columns):
    """Mark oversized display values as approximate instead of losing digits."""
    if len(str(value)) <= columns:
        return str(value)
    for scale, suffix in ((1000, 'K'), (1000000, 'M'), (1000000000, 'B'), (1000000000000, 'T')):
        text = f'{value/scale:.1f}{suffix}'
        if len(text) <= columns:
            return text
    return 'LARGE'[:columns]


def completed_products(state):
    # Original 28270..282C5: completed research only, in product-table order.
    return [i for i, row in enumerate(state['products'], 1) if row['research_state'] == 5]


def can_buy(state, definition):
    return bool(definition['manufacturable'] or
                definition['special_ship'] and state['products'][23]['research_state'] == 5)


def order_limit(state, definition, row):
    limits = [32767]
    for key, cost in {'credits': definition['price'], **definition['ore_costs']}.items():
        if cost:
            limits.append(row['queued'] + state['resources'][key] // cost)
    if definition['special_ship']:
        limits.append(max(row['queued'], state['products'][23]['stock']))
    return min(limits)


def order_limit_reason(state, definition, row):
    """Explain a clamped increase using the same current purchase constraints."""
    limit=order_limit(state,definition,row)
    if definition['special_ship'] and max(row['queued'],state['products'][23]['stock'])==limit:
        return 'Build a Space station first' if not state['products'][23]['stock'] else 'Space station capacity reached'
    for key,cost in {'credits':definition['price'],**definition['ore_costs']}.items():
        if cost and row['queued']+state['resources'][key]//cost==limit:
            return 'More '+key.capitalize()+' needed'
    return 'Maximum queue size reached'


@dataclass
class ProductionView:
    selected: int | None = None
    first: int = 0
    selecting: bool = False
    picture: bool = True
    quantity: int | None = None
    limited: bool = False

    @property
    def layout(self):
        return 15 if self.quantity is not None else 14 if self.selecting else 5

    def sync(self, state):
        ids = completed_products(state)
        if self.selected not in ids:
            self.selected = ids[0] if ids else None
            self.quantity = None
        if self.selected:
            index = ids.index(self.selected)
            self.first = min(max(0, len(ids)-13), max(min(self.first, index), index-12))
        return ids

    def step(self, state, delta):
        ids = self.sync(state)
        if ids and self.quantity is None:
            self.selected = ids[min(len(ids)-1, max(0, ids.index(self.selected)+delta))]
            self.sync(state)

    def targets(self, state):
        self.sync(state)
        targets = [((129, 49, 190, 127), 'See info' if self.picture else 'See picture', ('product_picture',))]
        if self.quantity is not None:
            return targets
        if not self.selecting:
            return targets + [((0, 49, 128, 127), 'Select', 31)]
        # Original scroll rails (292C3..293FF); native rows get direct clicks.
        targets.extend((rect, label, ('product_step', step)) for rect, label, step in (
            ((0, 49, 11, 18), 'Scroll up', -1), ((114, 49, 12, 18), 'Scroll up', -1),
            ((0, 158, 11, 18), 'Scroll down', 1), ((114, 158, 12, 18), 'Scroll down', 1)))
        for i, pid in enumerate(completed_products(state)[self.first:self.first+13]):
            targets.append(((12, 55+9*i, 102, 9), '', ('product_select', pid)))
        return targets
