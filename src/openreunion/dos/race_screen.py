"""Planet portrait view and original survey/spy-gated alien intelligence."""
from .race_info import TEXT_NAME, profile, revealed_race
from .worlds import FORCE_PRODUCTS, force_intelligence


class RaceView:
    def __init__(self, session, world_id):
        self.session, self.world_id = session, world_id
        self.owner = revealed_race(session.state['worlds'][world_id]['raw'])
        self.details = False
        self.signature = None

    def current(self, session, world_id):
        return (self.owner is not None and session is self.session and world_id == self.world_id
                and revealed_race(session.state['worlds'][world_id]['raw']) == self.owner)

    def forces(self, state):
        campaign = state['campaign']
        return force_intelligence(state['worlds'][self.world_id]['raw'],
                                  campaign['civilizations'], campaign['bar'])

    def sync(self, state):
        forces = self.forces(state)
        signature = None if forces is None else tuple(forces.items())
        changed = signature != self.signature
        self.signature = signature
        if forces is None:
            self.details = False
        return changed

    def targets(self, state):
        targets = []
        if not self.details and self.forces(state) is not None:
            targets.append(((104, 156, 216, 44), 'Exact military counts', ('race_forces',)))
        targets.append(((0, 49, 320, 151), 'Back to race profile' if self.details else
                        'Back to planet information', ('race_back',)))
        return targets

    def draw(self, renderer, state, caption, buttons, page):
        target = renderer.frame(state, 'ALIENNFO', 8, page, caption, buttons)
        # Original 2B851..2B86E: intermediate width 98; source offset 99,
        # destination offset 0x4382 in the 320-wide framebuffer.
        target.blit(renderer.path_asset(f'ALIEN/ALIEN{self.owner}.PIC'), 2, 54,
                    source=(1, 1, 94, 143))
        lines = renderer.content.text(TEXT_NAME)
        profile(lines, self.owner)  # Validate both original and converted records.
        record = lines[(self.owner-1)*12:self.owner*12]
        renderer.text(target, record[0], 105, 54, columns=35)
        forces = self.forces(state)
        if self.details and forces is not None:
            for index, (product, count) in enumerate(forces.items()):
                renderer.text(target, renderer.content.catalog['products'][product-1]['name'],
                              104, 72+index*9, columns=24)
                renderer.text(target, str(count).rjust(10), 254, 72+index*9, columns=10)
            if not forces:
                renderer.text(target, 'No known weapon types', 104, 72, columns=35)
            renderer.text(target, 'Click to return to profile', 104, 183, columns=35)
            return target
        for index, line in enumerate(record[1:], 2):
            renderer.text(target, line, 105, 54+index*9, columns=35)
        if forces is not None:
            for index, product in enumerate(FORCE_PRODUCTS):
                if product not in forces:
                    continue
                x, colon, number = (104, 170, 176) if index < 4 else (197, 293, 299)
                y = 156+(index % 4)*9
                renderer.text(target, renderer.content.catalog['products'][product-1]['name'],
                              x, y, columns=(colon-x)//6)
                renderer.text(target, ':', colon, y)
                # Original three-character fields silently lost large values.
                # Mark overflow explicitly; a click shows all unsigned digits.
                count = str(forces[product])
                renderer.text(target, count.rjust(3) if len(count) <= 3 else '+++',
                              number, y, columns=3)
        return target
