"""Small RGB framebuffer for original artwork, bitmap text and screen chrome.

Composition uses the decoded assets directly. No image toolkit, emulation or
external rendering dependency is required by the game.
"""
import textwrap

from .bridge import COMMANDER_RECTS, COMMANDER_SOURCES, COMMANDER_DRAW_ORDER, available_commanders
from .commanders import ROLES
from .catalog import SUBJECTS
from .control_panel import ControlPictures
from .control_layouts import select_layout
from .research_screen import RESEARCH_LABELS, disc_copies


class ScreenPixels:
    width, height = 320, 200

    def __init__(self):
        self.rgb = bytearray(self.width*self.height*3)

    def blit(self, picture, x, y, *, source=None, transparent=None):
        sx, sy, w, h = source or (0, 0, picture.width, picture.height)
        if not (0 <= sx <= sx+w <= picture.width and 0 <= sy <= sy+h <= picture.height
                and 0 <= x <= x+w <= self.width and 0 <= y <= y+h <= self.height):
            raise ValueError('Screen copy is outside the source or destination')
        colors = [picture.palette[i*3:i*3+3] for i in range(256)]
        for row in range(h):
            for col in range(w):
                value = picture.pixels[(sy+row)*picture.width+sx+col]
                if value != transparent:
                    at = ((y+row)*self.width+x+col)*3
                    self.rgb[at:at+3] = colors[value]

    def text(self, font, characters, text, x, y, *, color=(182, 170, 0), shadow=(129, 117, 0), columns=None,background=(0,0,0)):
        text = str(text)
        if columns is not None:
            text = text[:columns].ljust(columns)
        if not (0 <= x and x+len(text)*6 <= 320 and 0 <= y <= 192):
            raise ValueError('Text exceeds the original display')
        colors = (bytes(background), bytes(color), bytes(shadow))
        for col, char in enumerate(text):
            index = characters.find(char)
            if index < 0:
                index = characters.index('?')
            source = (index//20)*8*320+(index%20)*16
            for row in range(8):
                for px in range(6):
                    at = ((y+row)*320+x+col*6+px)*3
                    self.rgb[at:at+3] = colors[font.pixels[source+row*320+px]]

    def scaled_blit(self, picture, rect, source, *, transparent=0):
        """Nearest-neighbor sprite copy clipped to the map's body viewport."""
        x, y, width, height = rect
        sx, sy, sw, sh = source
        if not (width > 0 and height > 0 and 0 <= sx < sx+sw <= picture.width and 0 <= sy < sy+sh <= picture.height):
            raise ValueError('Invalid scaled sprite rectangle')
        for py in range(max(49, y), min(200, y+height)):
            for px in range(max(0, x), min(320, x+width)):
                value = picture.pixels[(sy+(py-y)*sh//height)*picture.width+sx+(px-x)*sw//width]
                if value != transparent:
                    at = (py*320+px)*3
                    self.rgb[at:at+3] = picture.palette[value*3:value*3+3]

    def ppm(self):
        return b'P6\n320 200\n255\n'+bytes(self.rgb)

    def fill(self, rect, color):
        x, y, width, height = rect
        if not (0 <= x <= x+width <= 320 and 0 <= y <= y+height <= 200):
            raise ValueError('Rectangle exceeds the original display')
        for row in range(y,y+height):
            self.rgb[(row*320+x)*3:(row*320+x+width)*3] = bytes(color)*width


class OriginalScreens:
    def __init__(self, content):
        self.content = content
        self.controls = ControlPictures(content)
        self.assets = {}
        self.characters = content.catalog['character_set']
        self.font = self.asset('CHARSET1')

    def asset(self, name):
        if name not in self.assets:
            self.assets[name] = self.content.indexed_picture('GRAFIKA/'+name+'.PIC')
        return self.assets[name]

    def text(self, target, text, x, y, **kwargs):
        target.text(self.font, self.characters, text, x, y, **kwargs)

    def frame(self, state, background, layout, page, caption, buttons=None):
        target = ScreenPixels()
        slots = buttons if buttons is not None else select_layout(self.content.catalog['control_layouts'], layout)['buttons']
        slots = slots+[0]*(12-len(slots))
        target.blit(self.controls.panel(self.content.catalog['control_buttons'], slots, page), 0, 0)
        target.blit(self.asset('TEXT'), 0, 32)
        if background is not None:
            target.blit(self.path_asset(background) if '/' in background else self.asset(background), 0, 49)
        self.text(target, caption, 12, 35, columns=19)
        # Native formatting is bounded to the original boxes; balances remain
        # exact in the session, including assisted values wider than this box.
        credits = str(state['resources']['credits'])
        self.text(target, credits[-11:].rjust(11), 141, 35, columns=11)
        year, month, day, hour = state['date']
        self.text(target, f'{year:04}/{month:02}/{day:02}/{hour:02}', 221, 35, columns=14)
        return target

    def battle(self,state,body,layout,caption):
        header=b'P6\n320 151\n255\n'
        if not body.startswith(header) or len(body)!=len(header)+320*151*3:
            raise ValueError('Battle viewport must be a 320x151 RGB frame')
        target=self.frame(state,None,layout,0,caption)
        target.rgb[49*320*3:]=body[len(header):]
        return target

    def path_asset(self, name):
        if name not in self.assets:
            self.assets[name] = self.content.indexed_picture(name)
        return self.assets[name]

    def mining(self,state,world_id,caption='RESOURCE-MINE'):
        from .mining_screen import mining_report
        from .production_screen import display_number
        report=mining_report(state,world_id)
        target=self.frame(state,'MINER',4,0,caption)
        digits=self.asset('SZAMOK')
        if report['active']<=9:
            target.blit(digits,34,144,source=(report['active']%5*64,report['active']//5*35,48,35))
        else:
            self.text(target,display_number(report['active'],7),34,158,columns=7)
        for key,x,y,sw,sh,sx,sy in (('stored',112,144,16,35,0,70),('mines',113,113,13,9,163,71)):
            number=report[key]
            if 0<=number<=99:
                for i,digit in enumerate((number//10,number%10)):
                    target.blit(digits,x+sw*i,y,source=(sx+sw*digit,sy,sw,sh))
            else:
                self.text(target,display_number(number,5),x,y+(14 if key=='stored' else 0),columns=5)
        for i,(stock,rate) in enumerate(zip(report['stocks'],report['rates'])):
            self.text(target,(display_number(stock,6) if stock else '-').rjust(6),59,57+8*i,columns=6)
            if rate.isdigit() and int(rate)>99:
                value=int(rate)
                label=str(value) if value<1000 else f'{value/1000:.0f}K'
                self.text(target,label.rjust(3),107,57+8*i,columns=3)
            else:self.text(target,rate.rjust(2),113,57+8*i,columns=2)
        return target

    def equipment(self,state,view,caption='EQUIPMENT',page=0):
        from .equipment_screen import draw
        return draw(self,state,view,caption,page)

    def cargo(self,state,view,caption='TRANSFER'):
        from .cargo_screen import draw
        return draw(self,state,view,caption)

    def cockpit(self,state,view,caption='CONTROL PANEL',page=0):
        from .cockpit_screen import draw
        return draw(self,state,view,caption,page)

    def fleets(self,state,view,caption='SHIP INFO'):
        from .fleet_screen import draw
        return draw(self,state,view,caption)

    def new_fleet(self,state,view,caption='NEW UNIT'):
        from .fleet_screen import draw_new
        return draw_new(self,state,view,caption)

    def surface(self, state, view, caption='PLANET MAIN',*,return_cockpit=False):
        from .surface_screen import VIEWPORT, surface_buttons
        from .surface import occupancy, placement_fits, footprint
        catalog = self.content.catalog
        terrain = view.sync(state,catalog)
        raw = state['worlds'][view.world_id]['raw']
        target = self.frame(state,'DESIGNER',20,0,caption,buttons=surface_buttons(state,view.world_id,return_cockpit=return_cockpit))
        target.fill(VIEWPORT,(0,0,0))
        target.fill((12,64,77,64),(0,0,0))
        target.fill((0,138,89,62),(0,0,0))
        if not view.editable:
            for rect in ((0,50,89,13),(0,64,11,65),(0,129,89,9)):
                target.fill(rect,(0,0,0))
        if not view.revealed:return target
        group = catalog['surface_rules']['groups'][raw[21]-1]
        ground = self.path_asset(f'PLANETS/FELSZ{group}.PIC')
        buildings = self.path_asset(f"PLANETS/EPUL{'T' if raw[0]>1 else ''}{group}.PIC")
        tiles = bytes.fromhex(terrain['tiles_hex'])
        overlays = view.overlays(state,catalog)
        count = ground.width*ground.height//256
        for y in range(min(9,terrain['height'])):
            for x in range(min(14,terrain['width'])):
                identity = (view.x+x+1,view.y+y+1)
                tile = tiles[(identity[1]-1)*terrain['width']+identity[0]-1]
                picture = ground
                if tile >= count:
                    picture = self.path_asset(f'PLANETS/FANIM{group}.PIC')
                    tile = view.animation.tile(group, tile - count)
                if identity in overlays:
                    tile,_ = overlays[identity]
                    picture = buildings
                target.blit(picture,93+16*x,53+16*y,source=((tile%20)*16,(tile//20)*16,16,16))
        definition = next(d for d in catalog['buildings'] if d['id'] == view.selected)
        target.fill((12,64,77,64),(0,0,0))
        sx,sy = 12+(77-definition['width']*16)//2,64+(64-definition['height']*16)//2
        for x,y in footprint(definition,0,0):
            tile = definition['tile_ids'][y*4+x]
            target.blit(buildings,sx+x*16,sy+y*16,source=(tile%20*16,tile//20*16,16,16))
        if view.editable:self.text(target,definition['name'],3,130,columns=14)
        if view.mode in ('build','demolish'):
            target.fill((0 if view.mode == 'build' else 45,62,44,1),(255,70,60))
        # Native minimap samples the original terrain tiles; DOS radar pixel
        # lookup/animation remains a separate presentation fidelity task.
        rx,ry,scale = view.radar(terrain)
        for y in range(terrain['height']):
            for x in range(terrain['width']):
                tile = tiles[y*terrain['width']+x]
                picture = ground
                if tile >= count:
                    picture = self.path_asset(f'PLANETS/FANIM{group}.PIC')
                    tile -= count
                value = picture.pixels[(tile//20*16+8)*320+tile%20*16+8]
                color = picture.palette[value*3:value*3+3]
                if (x+1,y+1) in overlays:color = bytes((210,210,70))
                target.fill((rx+x*scale,ry+y*scale,scale,scale),color)
        def outline(rect,color):
            x,y,w,h = rect
            target.fill((x,y,w,1),color);target.fill((x,y+h-1,w,1),color)
            target.fill((x,y,1,h),color);target.fill((x+w-1,y,1,h),color)
        outline((rx+view.x*scale,ry+view.y*scale,min(14,terrain['width'])*scale,min(9,terrain['height'])*scale),(255,255,255))
        if view.mode == 'build' and view.tile:
            width,height,blocked = occupancy(catalog,raw,state['buildings'],list(map(int,view.world_id.split(':'))))
            fits = placement_fits(definition,*view.tile,width,height,blocked)
            for x,y in footprint(definition,*view.tile):
                if view.x < x <= view.x+14 and view.y < y <= view.y+9:
                    outline((93+(x-view.x-1)*16,53+(y-view.y-1)*16,16,16),(50,230,70) if fits else (255,60,50))
        if view.mode == 'info':
            from .building_information import draw
            draw(self,target,state,view,definition)
        return target

    def world_list(self, state, view, rows, caption='MAIN COMPUTER'):
        target = self.frame(state, 'COLINFO', 37, 0, caption)
        view.sync(rows)
        for i, (_, prefix, name) in enumerate(rows[view.offset:view.offset+15]):
            y = 57+9*i
            self.text(target, prefix, 10, y)
            self.text(target, name, 10+6*len(prefix), y,
                      columns=(307-10-6*len(prefix))//6, color=(198,198,198), shadow=(129,129,129))
        if not rows:
            self.text(target, 'No known planets in this list.', 10, 57)
        target.fill((311,56,3,139), (0,0,0))
        target.fill(view.scrollbar(rows), (84,150,150))
        return target

    def colonize(self,state,view,caption='COLONIZATION'):
        from .colony_screen import OPTION_RECTS,option_available
        from .production_screen import display_number
        target=self.frame(state,'KOLONIZ',28,0,caption)
        catalog=self.content.catalog
        raw=state['worlds'][view.world_id]['raw']
        group=catalog['surface_rules']['groups'][raw[21]-1]
        tiles=self.path_asset(f'PLANETS/EPUL{group}.PIC')
        # 3698E paints palette index 64 on even (screen x+y) pixels.
        shade=self.asset('KOLONIZ').palette[64*3:65*3]
        for kind,x,y,w,h in OPTION_RECTS:
            definition=catalog['buildings'][kind-1]
            for dy in range(definition['height']):
                for dx in range(definition['width']):
                    tile=definition['tile_ids'][dy*4+dx]
                    if tile!=255:target.blit(tiles,x+16*dx,y+16*dy,source=(tile%20*16,tile//20*16,16,16))
            if kind not in view.options:
                for py in range(y,y+h):
                    for px in range(x,x+w):
                        if (px+py)%2==0:
                            at=(py*320+px)*3;target.rgb[at:at+3]=shade
            label=display_number(definition['price'],5) if option_available(state,catalog,view.world_id,kind) else 'Sorry'
            self.text(target,label,x+2,y-11,columns=5)
        self.text(target,'Cost of colony:',180,185,columns=15)
        self.text(target,display_number(view.cost(catalog),6),276,185,columns=6)
        return target

    def planet(self, state, world_id, caption='PLANET INFO', landscape=False,page=0):
        from .world_info import survey_information, owner_label
        from .colony import TAX_LABELS, can_change_tax
        from .production_screen import display_number
        definition = next(w for w in self.content.catalog['worlds'] if w['id'] == world_id)
        raw = state['worlds'][world_id]['raw']
        report = survey_information(raw, self.content.catalog)
        from .planet_actions import planet_buttons
        buttons=planet_buttons(state,self.content.catalog,world_id)
        target = self.frame(state, 'BOLYGO', 8, page, caption, buttons=buttons)
        if landscape and report['terrain']:
            target.blit(self.path_asset(f'PLANETS/NAGY{raw[21]}.PIC'), 0, 49)
            return target
        portrait = report['owner'] if report['owner'] is not None else 0
        target.blit(self.path_asset(f'PLANETS/FAJ{portrait}.PIC'), 0, 49, source=(0, 0, 56, 47))
        terrain = raw[21] if report['terrain'] else 0
        target.blit(self.path_asset(f'PLANETS/PLANET{terrain}.PIC'), 0, 145)
        primaries = [w for w in self.content.catalog['worlds'] if w['system'] == definition['system'] and not w['moon']]
        if definition['moon']:
            index = definition['index']-len(primaries)-1
            source = (66+17*(index%14), 34+17*(index//14), 16, 16)
        else:
            source = (64+32*(definition['planet']-1), 1, 32, 32)
        target.scaled_blit(self.path_asset(f"PLANETS/NAPR{definition['system']}.PIC"), (12, 103, 32, 32), source)
        self.text(target, definition['name']+' - '+owner_label(report, self.content.catalog), 62, 53, columns=42)
        self.text(target, display_number(report['population'], 26) if report['population'] is not None else 'Unknown', 90, 69, columns=37)
        self.text(target, TAX_LABELS[raw[18]] if can_change_tax(raw) else '-', 90, 85, columns=37)
        progress=f'Colony arrives in {raw[7]} days' if 0<raw[7]<128 and raw[0]==1 and not raw[6] else 'Survey '+str(report['survey'])
        self.text(target, progress, 102, 101, columns=35)
        self.text(target, report['terrain'] or 'Unknown', 96, 117, columns=36)
        self.text(target, str(report['diameter_km']) if report['diameter_km'] is not None else '?', 119, 134, columns=5)
        self.text(target, str(report['temperature_k']) if report['temperature_k'] is not None else '?', 271, 134, columns=4)
        for i, key in enumerate(self.content.catalog['ore_names']):
            label = '?' if report['ore_presence'] is None else 'YES' if report['ore_presence'][key] else 'NO'
            self.text(target, label, 155, 149+8*i, columns=3)
        lines = ['Habitable: '+('?' if report['habitable'] is None else 'YES' if report['habitable'] else 'NO'),
                 'Survey: '+str(report['survey']),
                 'Colony: '+('YES' if raw[6] else 'NO') if raw[0] == 1 else '',
                 'Morale: '+str(raw[19]) if raw[0] == 1 else '']
        for i, line in enumerate(lines):
            self.text(target, line, 193, 150+10*i, columns=20)
        return target

    def starmap(self, state, view, caption='GALACTIC MAP', *, entries=(), page=0, selected=None, routing=False):
        from .map_screen import system_choices
        from .orbital_screen import fleet_rect, fleet_sprite, map_buttons
        bodies = view.bodies(state, self.content.catalog)
        target = self.frame(state, 'PLANETS/HATTER2.PIC' if view.planet else 'PLANETS/HATTER1.PIC',
                            7, 0, caption, buttons=map_buttons(state,view.planet,entries,selected,routing=routing))
        sheet = self.path_asset(f'PLANETS/NAPR{view.system}.PIC')
        def body_draw(body):
            target.scaled_blit(sheet, body['rect'], body['source'])
        for body in sorted((b for b in bodies if b['depth'] < 0), key=lambda b:b['depth']):
            body_draw(body)
        if not (view.system == 4 and state['campaign']['flags']['5d90']):
            target.scaled_blit(sheet, (144, 108, 32, 32) if view.planet else (128, 92, 64, 64),
                               (64+32*(view.planet-1), 1, 32, 32) if view.planet else (0, 1, 64, 64))
        for body in sorted((b for b in bodies if b['depth'] >= 0), key=lambda b:b['depth']):
            body_draw(body)
        if not view.planet:
            buttons = self.path_asset('PLANETS/HATTER3.PIC')
            for system in system_choices(state):
                # 2CFCD..2D045: original eight 64x19 selector sprites.
                height = min(19, 200-(49+19*(system-1)))
                target.blit(buttons, 256, 49+19*(system-1),
                            source=((system-1)%4*64, (system-1)//4*19, 64, height), transparent=0)
        elif not routing:
            icons = self.path_asset('PLANETS/HATTER4.PIC')
            for slot, entry in enumerate(entries[page*18:page*18+18]):
                if entry is None:
                    continue
                x, y, _, _ = fleet_rect(slot)
                target.blit(icons, x, y, source=fleet_sprite(entry['icon']), transparent=0)
                if entry['key'] == selected:
                    target.blit(icons, x, y, source=(161, 17, 31, 15), transparent=0)
            entry = next((entry for entry in entries if entry and entry['key'] == selected), None)
            if entry:
                status = {1:'Landed', 2:'Orbit', 3:'Busy'}.get(entry['status'], '') if selected[0] == 'player' else 'Alien fleet'
                self.text(target, entry['label']+' '+status, 8, 168, columns=39)
                if selected[0] == 'player' and entry['status'] in (1, 2):
                    self.text(target, 'LAUNCH' if entry['status'] == 1 else 'LAND', 8, 183, columns=12)
                    if entry['status'] == 2:
                        self.text(target, 'MOVE', 104, 183, columns=12)
            if len(entries) > 18:
                self.text(target, f'PAGE {page+1}/{(len(entries)+17)//18}', 190, 190, columns=10)
        if routing:
            self.text(target, 'Choose destination. Right-click to zoom.', 8, 185, columns=50)
        return target, bodies

    def bridge(self, state, page=0, caption='CONTROL ROOM', hero=2):
        target = self.frame(state, 'MAIN', 1, page, caption)
        # 30CEF: hero sprite at linear VGA offset 7C43, 67 by 59 pixels.
        from .hero import bridge_source
        target.blit(self.asset('HEROES'), 131, 99, source=bridge_source(hero), transparent=0)
        available = available_commanders(state)
        for i in COMMANDER_DRAW_ORDER:
            if i not in available:
                continue
            x, y, width, height = COMMANDER_RECTS[i]
            sx, sy = COMMANDER_SOURCES[i][state['ranks'][ROLES[i]]-1]
            target.blit(self.asset('MAINFACE'), x, y, source=(sx, sy, width, height), transparent=0)
        return target

    def commanders(self, state, role=0, rank=None, caption='COMMANDERS'):
        target = self.frame(state, 'FACES', 2, 0, caption)
        if role:
            target.blit(self.asset('FACES'+str(role+1)), 0, 49)
        if rank is not None:
            row = self.content.catalog['commanders'][3*role+rank-1]
            # The original four fixed candidate text rows fit the lower panel.
            record = self.content.text('SZ_FACE.RAW')[4*(3*role+rank-1):4*(3*role+rank-1)+4]
            for i, line in enumerate(record):
                self.text(target, line, 6, 164+8*i, columns=40)
            if state['ranks'][ROLES[role]] == rank:
                self.text(target, 'HIRED', 278, 164)
        return target

    def disk(self, state, caption='DISK OPERATIONS'):
        return self.frame(state, 'DISK', 12, 0, caption)

    def production(self, state, view, caption='INFO-BUY', angle=0):
        from .production_screen import can_buy, display_number
        from .product_models import decode_model, draw_model
        ids = view.sync(state)
        target = self.frame(state, 'INFO', view.layout, 0, caption)
        if not ids:
            self.text(target, 'No completed projects', 14, 180)
            return target
        pid = view.selected
        definition, row = self.content.catalog['products'][pid-1], state['products'][pid-1]
        if view.selecting:
            target.blit(self.asset('SELECT'), 0, 49, source=(0, 0, 126, 127))
            for i, product in enumerate(ids[view.first:view.first+13]):
                self.text(target, self.content.catalog['products'][product-1]['name'], 16, 55+9*i,
                          columns=16, color=(255, 240, 100) if product == pid else (182, 170, 0))
        else:
            key = ('model', pid)
            if key not in self.assets:
                self.assets[key] = decode_model(self.content.product_model_data(pid))
            draw_model(target, self.assets[key], angle)
        if view.picture:
            key = ('product', pid)
            if key not in self.assets:
                self.assets[key] = self.content.indexed_picture(f'INFO/INFO{pid}.PIC')
            target.blit(self.assets[key], 134, 55, source=(6, 6, 180, 115))
        else:
            lines = self.content.text('SZ_TALAL.RAW')[(pid-1)*7:pid*7]
            self.text(target, lines[0], 136, 59, columns=29)
            if view.quantity is None:
                for i, line in enumerate(lines[1:]):
                    self.text(target, line, 136, 71+i*10, columns=29)
            else:
                self.text(target, 'Ore reserves:', 136, 73, columns=29)
                for i, key in enumerate(definition['ore_costs']):
                    available = state['resources'][key]+row['queued']*definition['ore_costs'][key]
                    self.text(target, self.content.catalog['ore_names'][key][:7]+display_number(available, 6).rjust(6),
                              142+(i%2)*83, 82+(i//2)*9, columns=13)
            self.text(target, 'Ore needs: '+('one piece' if view.quantity is None else 'total order'), 136, 133, columns=29)
            for i, (key, cost) in enumerate(definition['ore_costs'].items()):
                total = cost*(1 if view.quantity is None else view.quantity)
                self.text(target, self.content.catalog['ore_names'][key][:7]+display_number(total, 6).rjust(6),
                          142+(i%2)*83, 142+(i//2)*9, columns=13)
        quantity = row['queued'] if view.quantity is None else view.quantity
        if can_buy(state, definition):
            # Match actual scheduling: excess work is discarded after each item.
            work = row['work_remaining'] or definition['base_work']
            workforce = state['workforce']
            hours = ((max(1, (work+workforce-1)//workforce) +
                     (quantity-1)*max(1, (definition['base_work']+workforce-1)//workforce)) if quantity else 0)
            for label, value, x, y, vx in (
                ('Bought items:', quantity, 14, 180, 100), ('Time to go:', display_number(hours, 7)+'h', 160, 180, 264),
                ('Stores:', row['stock'], 14, 189, 100), ('Total price:', display_number(quantity*definition['price'], 8), 160, 189, 264)):
                self.text(target, label, x, y)
                self.text(target, value, vx, y, columns=8)
        else:
            self.text(target, definition['name'], 14, 180, columns=29)
            self.text(target, 'Technology for colony or fleet use', 14, 189, columns=49)
        return target

    def message_lines(self, state):
        from .mission_messages import append_report_text
        lines = []
        for event in reversed(state['events']):
            year, month, day, hour = event['date']
            lines.append(f'{year:04}/{month:02}/{day:02}/{hour:02}')
            text='' if event['kind']=='report' else self.content.text('MESSAGE.TXT' if event['kind']=='message' else 'KITALAL.TXT')[event['id']-1].replace('|','\n')
            for paragraph in append_report_text(text,event).split('\n'):
                lines.extend(textwrap.wrap(paragraph, width=50) or [''])
            lines.append('')
        return lines or ['No messages.']

    def messages(self, state, first_line=0, caption='MESSAGES'):
        target = self.frame(state, 'UZENET', 11, 0, caption)
        for i, line in enumerate(self.message_lines(state)[first_line:first_line+17]):
            self.text(target, line, 8, 55+8*i, columns=50)
        return target

    def research(self, state, selected=None, caption='RESEARCH-DESIGN'):
        target = self.frame(state, 'RESEARCH', 3, 0, caption)
        for (x, y), source in disc_copies(state['products']):
            target.blit(self.asset('CDS'), x, y, source=source)
        if selected is not None:
            row = state['products'][selected-1]
            definition = self.content.catalog['products'][selected-1]
            self.text(target, 'Project name :', 190, 76, columns=18)
            self.text(target, definition['name'], 200, 88, columns=16)
            self.text(target, RESEARCH_LABELS[row['research_state']], 190, 100, columns=18)
            progress = ('Completed: '+str((10000-row['research_remaining'])//100)+'%'
                        if state['ranks']['developer'] else 'No developer')
            if state['research_paused']:progress='Paused by player'
            self.text(target, progress if row['research_state'] in (2, 4) else '', 190, 112, columns=18)
            if row['research_state'] < 5:
                for label, key, x, y in (('Math:', 'math', 189, 139), ('Physics:', 'physics', 235, 139),
                                          ('Elect:', 'electronics', 189, 149), ('AI:', 'artificial_intelligence', 235, 149)):
                    self.text(target, label, x, y)
                    self.text(target, str(definition['requirements'][key]), 224 if x == 189 else 284, y)
        if state['ranks']['developer']:
            definition = self.content.catalog['commanders'][9+state['ranks']['developer']-1]
            self.text(target, definition['name'], 8, 188, columns=14)
            for key, x in zip(SUBJECTS, (136, 203, 259, 296)):
                self.text(target, str(state['skills'][key]), x, 188, columns=1)
        else:
            self.text(target, 'No developer', 8, 188, columns=14)
            for x in (136, 203, 259, 296):
                self.text(target, '-', x, 188)
        online = (state['ranks']['developer'] and not state['campaign']['research_block_remaining']
                  and state['campaign']['training_role'] != 4)
        # 2288C..229D0 copies the original ON/OFF and indicator sprites.
        target.blit(self.asset('CDS'), 76, 170, source=(0 if online else 18, 79, 11, 5))
        target.blit(self.asset('CDS'), 149, 170, source=(12 if online else 30, 79, 5, 5))
        return target
