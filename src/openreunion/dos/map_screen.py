"""Original map identities, discovery gates and native orbital presentation.

Orbital radii/speeds come from original world-name records. Deterministic
presentation phases replace the DOS UI's random phase initialization, leaving
the campaign RNG untouched. Projection follows 2D2A0's elliptical layout with
native trigonometry; exact fixed-point timing remains a fidelity task.
"""
import math
from dataclasses import dataclass

from .world_lists import world_visible


def system_choices(state):
    # 2BB93..2BC05: completed Hyperspace drive OR Trade ship enables switches.
    if not any(state['products'][i]['research_state'] == 5 for i in (13, 14)):
        return []
    return [i for i, status in enumerate(state['known_systems'], 1) if status < 128]


@dataclass
class MapView:
    system: int = 1
    planet: int = 0
    ticks: int = 0

    def sync(self, state):
        if not 1 <= self.system <= 8 or state['known_systems'][self.system-1] >= 128:
            self.system, self.planet = 1, 0
        if self.planet and (state['known_systems'][self.system-1] != 1 or
                state['campaign']['navigation']['planet_visibility'][8*(self.system-1)+self.planet-1] >= 128):
            self.planet = 0

    def bodies(self, state, catalog):
        self.sync(state)
        # Original hides the Antares system during its story concealment state.
        if self.system == 4 and state['campaign']['flags']['5d90']:
            return []
        primaries = [w for w in catalog['worlds'] if w['system'] == self.system and not w['moon']]
        rows = [w for w in catalog['worlds'] if w['system'] == self.system and
                (w['planet'] == self.planet and w['moon'] if self.planet else not w['moon'])]
        result = []
        for index, world in enumerate(rows):
            if not world_visible(state, world):
                continue
            # A visible primary with visibility 0 has not revealed its moons.
            if self.planet and state['campaign']['navigation']['planet_visibility'][8*(self.system-1)+self.planet-1] < 1:
                continue
            speed, rx, ry = world['orbital_display_bytes']
            angle = ((index*617+world['system']*193+self.ticks*(speed//(4 if self.planet else 2))) % 3600)/10
            radians = math.radians(angle)
            depth = math.sin(radians)
            x, y = 160+int(rx*math.cos(radians)), 124+int(ry*depth)
            size = (8+int(67+67*depth)//16) if self.planet else (16+int(67+67*depth)//8)
            if self.planet:
                moon_index = world['index']-len(primaries)-1
                source = (66+17*(moon_index%14), 34+17*(moon_index//14), 16, 16)
            else:
                source = (64+32*(world['planet']-1), 1, 32, 32)
            result.append({'world':world, 'rect':(x-size//2, y-size//2, size, size),
                           'source':source, 'depth':depth})
        return result

    def targets(self, state, catalog, bodies):
        targets = []
        if not self.planet:
            targets.extend(((256, 49+19*(system-1), 64, min(19, 200-(49+19*(system-1)))),
                            catalog['system_names'][system-1], ('map_system', system))
                           for system in system_choices(state))
        else:
            if self.system == 4 and state['campaign']['flags']['5d90']:
                return []
            world = next(w for w in catalog['worlds'] if (w['system'], w['planet'], w['moon']) == (self.system, self.planet, 0))
            targets.append(((144, 108, 32, 32), world['name'], ('map_world', world['id'])))
        # Hit the frontmost sprite when bodies overlap; use drawn bounds.
        targets.extend((body['rect'], body['world']['name'], ('map_world', body['world']['id']))
                       for body in sorted(bodies, key=lambda b:b['depth'], reverse=True))
        return targets
