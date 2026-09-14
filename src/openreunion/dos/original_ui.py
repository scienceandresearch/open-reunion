"""Original graphical screen flow over the existing transactional game client.

The remaining development screens are explicit temporary routes while their
original presentations are ported. Simulation, persistence and audio stay shared.
"""
import tkinter as tk
from tkinter import ttk
from time import monotonic_ns

from .ui import RecoveredApp
from .original_screen import OriginalScreens
from .bridge import bridge_targets
from .research_screen import research_targets
from .commanders import ROLES
from .control_panel import pointer_slot
from .control_layouts import select_layout
from .control_input import PanelPress
from .production_screen import ProductionView, can_buy, order_limit, order_limit_reason
from .map_screen import MapView, system_choices
from .world_lists import world_visible
from .orbital_screen import orbital_entries, orbital_targets, map_buttons, map_attack, attack_signature
from .world_list_screen import WorldListView, list_lines
from .editor_context import FleetContext, WorldContext
from .surface_screen import SurfaceView, building_tiles, surface_buttons, local_group
from .surface import surface_revealed, surface_editable
from .mining_screen import mining_available, mining_report
from .colony_screen import ColonyView,settlement_offered
from .equipment_screen import EquipmentView,fleet_name
from .equipment import EquipmentTransferLimit
from .cargo_screen import CargoView
from .cockpit_screen import CockpitView
from .fleet_screen import FleetView,NewFleetView,available_types
from .ground_setup_screen import setup_buttons,setup_targets,setup_signature,draw_setup,ADD_ACTIONS,GroundSetupBar
from .planet_actions import planet_buttons,deployment_buttons,DEPLOY_ACTIONS,action_signature
from .race_info import revealed_race
from .race_screen import RaceView
from ..core import GameError


class OriginalApp(RecoveredApp):
    @property
    def hero(self):return self.session.hero

    def __init__(self, root, installation, save=None):
        self.startup=None
        self.original = None
        super().__init__(root, installation, save)
        self.workbench = self.book.master
        self.workbench.pack_forget()
        root.title('Open Reunion')
        root.configure(background='black')
        root.geometry('960x600')
        root.minsize(640, 400)
        self.original = tk.Canvas(root, background='black', highlightthickness=0, takefocus=True)
        self.original.pack(fill='both', expand=True)
        self.screen_item = self.original.create_image(0, 0, anchor='nw')
        self.screen_renderer = OriginalScreens(self.content)
        self.screen = 'bridge'
        self.menu_page = 0
        self.disk_pressed = 0
        from .disk_slots import DiskSlots
        self.disk_slots=DiskSlots(self)
        from .disk_cinema import DiskCinema
        self.disk_cinema=DiskCinema(self)
        from .cockpit_cinema import CockpitCinema
        self.cockpit_cinema=CockpitCinema(self)
        from .navigation_sound import NavigationSound
        self.navigation_sound=NavigationSound(self)
        from .research_cinema import ResearchCinema
        self.research_cinema=ResearchCinema(self)
        root.bind('<Destroy>',lambda event:self.research_cinema.cancel() if event.widget is root else None,add='+')
        from .bridge_cinema import BridgeCinema
        self.bridge_cinema=BridgeCinema(self)
        root.bind('<Destroy>',lambda event:self.bridge_cinema.leave() if event.widget is root else None,add='+')
        root.bind('<Destroy>',lambda event:self.cockpit_cinema.cancel() if event.widget is root else None,add='+')
        root.bind('<Destroy>',lambda event:self.navigation_sound.cancel() if event.widget is root else None,add='+')
        root.bind('<Destroy>',lambda event:self.disk_cinema.cancel() if event.widget is root else None,add='+')
        self.commander_role = 0
        self.commander_rank = None
        self.research_selected = None
        self.production_view = ProductionView()
        self.model_angle = 0
        self.model_timer = None
        self.map_view = MapView()
        self.map_bodies = []
        self.planet_id = '1:5:0'
        self.planet_landscape = False
        self.race_view = None
        self.planet_action_signature = None
        self.colony_view = None
        self.colony_context = None
        self.colony_signature = None
        self.equipment_view = None
        self.equipment_context = None
        self.equipment_signature = None
        self.cargo_view = None
        self.cargo_context = None
        self.cargo_signature = None
        self.cockpit_view = None
        self.cockpit_context = None
        self.cockpit_signature = None
        self.route_return = None
        self.equipment_editor = None
        self.equipment_editor_item = None
        self.name_editor_submit = None
        self.name_editor_position = (24,56)
        self.fleet_view = FleetView()
        self.fleet_context = FleetContext(self.session)
        self.fleet_signature = None
        self.new_fleet_view = None
        self.orbital_selected = None
        self.orbital_page = 0
        self.orbital_entries = []
        self.orbital_attack_signature = None
        self.orbital_context = FleetContext(self.session)
        self.route_fleet = None
        self.world_list_view = WorldListView()
        self.world_list_rows = []
        self.surface_view = SurfaceView()
        self.surface_context = None
        self.surface_return = None
        self.surface_signature = None
        self.surface_drag = False
        self.mining_world = '1:5:0'
        self.mining_context = None
        self.mining_signature = None
        self.message_offset = 0
        self.caption = ''
        self.scale, self.origin = 3, (0, 0)
        self.pointer = PanelPress()
        self.screen_session = self.session
        from .original_clock import OriginalClockBar
        self.clock_bar = OriginalClockBar(self)
        self.clock_bar.pack(side='bottom',fill='x',before=self.original)
        self.clock_bar.update_idletasks()
        self.clock_bar_height = self.clock_bar.winfo_reqheight()
        from .space_screen import SpaceScreen,SpaceBar
        self.space_view=SpaceScreen(self)
        self.space_bar=SpaceBar(self)
        self.ground_setup_bar=GroundSetupBar(self)
        self.ground_setup_signature=None
        from .ground_screen import GroundScreen,GroundBar
        self.ground_view=GroundScreen(self)
        self.ground_bar=GroundBar(self)
        from .scene_screen import SceneScreen,SceneBar
        self.scene_view=SceneScreen(self)
        self.scene_bar=SceneBar(self)
        from .dialog_screen import DialogScreen,DialogBar
        self.dialog_view=DialogScreen(self)
        self.dialog_bar=DialogBar(self)
        from .bar_screen import BarScreen,BarControls
        self.bar_view=BarScreen(self)
        self.bar_controls=BarControls(self)
        from .adviser_screen import AdviserScreen,AdviserBar
        self.adviser_view=AdviserScreen(self)
        self.adviser_bar=AdviserBar(self)
        from .defeat_screen import DefeatScreen,DefeatBar
        self.defeat_view=DefeatScreen(self);self.defeat_bar=DefeatBar(self)
        from .victory_screen import VictoryScreen
        self.victory_view=VictoryScreen(self);self.victory_bar=DefeatBar(self,view=self.victory_view,title='Victory cinematic')
        from .credits_screen import CreditsScreen,CreditsBar
        self.credits_view=CreditsScreen(self);self.credits_bar=CreditsBar(self)
        from .intro_screen import IntroScreen,IntroBar
        self.intro_view=IntroScreen(self);self.intro_bar=IntroBar(self)
        root.bind('<Destroy>',lambda event:self.credits_view.close() if event.widget is root else None,add='+')
        root.bind('<Destroy>',lambda event:self.intro_view.close() if event.widget is root else None,add='+')
        root.bind('<Destroy>',lambda event:(self.defeat_view.close(),self.victory_view.close()) if event.widget is root else None,add='+')
        root.geometry(f'960x{600+self.clock_bar_height}')
        root.minsize(640,400+self.clock_bar_height)
        self.original.bind('<Configure>', lambda _: self.render_original())
        self.original.bind('<Motion>', self.original_motion)
        self.original.bind('<Leave>', lambda _: self.hover(''))
        self.original.bind('<MouseWheel>', lambda e:self.guard(lambda:self.scroll_original(e)))
        for key,dx,dy in (('Left',-1,0),('Right',1,0),('Up',0,-1),('Down',0,1)):
            self.original.bind('<'+key+'>',lambda e,dx=dx,dy=dy:self.surface_pan(dx,dy) if self.screen == 'surface' else None)
        self.original.bind('<Prior>', lambda _: self.scroll_messages(-16))
        self.original.bind('<Next>', lambda _: self.scroll_messages(16))
        self.original.bind('<FocusOut>', self.cancel_original_pointer)
        self.original.bind('<Unmap>', self.cancel_original_pointer)
        for button in (1, 2, 3):
            self.original.bind(f'<ButtonPress-{button}>', lambda e: self.guard(lambda: self.original_press(e)))
            self.original.bind(f'<ButtonRelease-{button}>', lambda e: self.guard(lambda: self.original_release(e)))
        root.bind('<Escape>', lambda _: self.escape_original())
        root.bind('<F11>', lambda _: root.attributes('-fullscreen', not root.attributes('-fullscreen')))
        root.bind('<F10>',lambda _:self.guard(self.open_startup))
        root.bind('<F2>', lambda _: self.show_tools('Admin & log'))
        root.bind('<space>', lambda e: self.guard(self.toggle_time) if e.widget is self.original else None)
        root.bind('<KeyPress>',self.scene_key)
        root.bind('<KeyPress-p>',lambda e:self.guard(self.intro_view.input) if self.screen=='intro' and e.widget is self.original else self.guard(self.scene_view.toggle) if self.screen=='scene' and e.widget is self.original else None)
        for key,command in (('m','move'),('a','attack')):
            self.original.bind('<KeyPress-'+key+'>',lambda e,command=command:self.guard(lambda:self.ground_view.command(command)) if self.screen=='ground' else None)
        ttk.Button(self.workbench, text='Return to control room (Esc)', command=self.show_original).pack(anchor='w', before=self.workbench.winfo_children()[0])
        self.refresh_listeners.append(self.original_refresh)
        self.original.focus_set()
        self.original_refresh()
        if self.session.state['active_dialog'] is not None:self.show_conversation()

    def animate_model(self):
        self.model_timer = None
        if self.screen == 'surface':
            view = self.surface_view
            visible = self.original.winfo_ismapped() and self.startup is None
            changed = view.animation.advance(monotonic_ns(), enabled=bool(
                visible and view.revealed and not self.pointer.buttons and view.mode in ('inspect','build','demolish')))
            if visible:
                if changed:self.render_original()
                if self.model_timer is None:self.model_timer = self.root.after(40, self.animate_model)
            return
        if self.original.winfo_ismapped() and (self.screen in ('starmap','cockpit') or self.screen == 'production' and not self.production_view.selecting):
            if not self.pointer.buttons:
                self.model_angle = (self.model_angle+.045) % 6.283185307179586
                self.map_view.ticks += 1
                if self.screen=='cockpit':self.cockpit_view.advance(self.session.state)
            self.render_original()

    def stop_model_timer(self):
        if getattr(self,'surface_view',None) is not None:self.surface_view.animation.pause()
        if self.model_timer is not None:
            self.root.after_cancel(self.model_timer)
            self.model_timer = None

    def close(self):
        if getattr(self,'bridge_cinema',None) is not None:self.bridge_cinema.leave()
        if getattr(self,'research_cinema',None) is not None:self.research_cinema.cancel()
        if getattr(self,'navigation_sound',None) is not None:self.navigation_sound.cancel()
        if getattr(self,'cockpit_cinema',None) is not None:self.cockpit_cinema.cancel()
        if getattr(self,'disk_cinema',None) is not None:self.disk_cinema.cancel()
        if getattr(self,'credits_view',None) is not None:self.credits_view.close()
        if getattr(self,'intro_view',None) is not None:self.intro_view.close()
        if getattr(self,'victory_view',None) is not None:self.victory_view.pause()
        if getattr(self,'defeat_view',None) is not None:self.defeat_view.pause()
        if getattr(self, 'model_timer', None) is not None:
            self.stop_model_timer()
        super().close()

    def save_path(self,path):
        super().save_path(path)
        if self.screen=='disk':self.disk_slots.refresh();self.render_original()

    def pause_battles(self):
        if getattr(self,'bridge_cinema',None) is not None:self.bridge_cinema.leave()
        if getattr(self,'research_cinema',None) is not None:self.research_cinema.cancel()
        if getattr(self,'navigation_sound',None) is not None:self.navigation_sound.cancel()
        if getattr(self,'cockpit_cinema',None) is not None:self.cockpit_cinema.cancel()
        if getattr(self,'credits_view',None) is not None:self.credits_view.pause()
        if getattr(self,'intro_view',None) is not None:self.intro_view.pause()
        if getattr(self,'victory_view',None) is not None:self.victory_view.pause()
        if getattr(self,'defeat_view',None) is not None:self.defeat_view.pause()
        if getattr(self,'scene_view',None) is not None:self.scene_view.pause()
        if getattr(self,'space_view',None) is not None:self.space_view.pause()
        if getattr(self,'ground_view',None) is not None:self.ground_view.pause()
        super().pause_battles()

    def escape_original(self):
        if self.screen=='intro':self.open_startup();return
        if self.startup is not None:self.startup.back(self);return
        if self.screen=='credits':self.show_original();return
        if self.screen in ('defeat','victory'):
            (self.victory_view if self.screen=='victory' else self.defeat_view).pause();self.render_original();return
        if self.screen=='planet' and self.race_view is not None:
            self.dispatch(('race_back',));return
        if self.screen=='adviser':self.adviser_view.close()
        self.scene_view.pause()
        self.space_view.pause()
        if self.screen=='ground':
            self.ground_view.pause()
            self.ground_view.command('context_cancel')
        self.show_original()

    def show_space_battle(self):
        if not self.space_view.active:raise GameError('There is no space battle to resume.')
        self.space_view.sync()
        self.show_original('space')

    def show_ground_battle(self):
        if (self.session.state['ground_encounter'] or {}).get('phase')=='setup':
            self.show_original('ground_setup')
        elif self.ground_view.active:
            self.ground_view.sync();self.show_original('ground')
        else:raise GameError('There is no ground battle to resume.')

    def show_presentation(self,*,autoplay=True):
        # RecoveredApp can request a loaded presentation before the canvas and
        # its adapters have been initialized; original_refresh resumes it.
        if self.original is None:return
        state=self.session.state
        if state['active_scene'] is None and state['active_dialog'] is None and state['presentation_requests']:
            self.session.apply('start_presentation');self.refresh();state=self.session.state
        if state['active_dialog'] is not None:self.show_conversation();return
        if not self.scene_view.active:
            self.status.set('No story presentation is waiting.');return
        self.scene_view.sync();self.show_original('scene')
        current=state['active_scene']
        if autoplay and current is not None and current['notice'] is None and current['playback']['ticks']==0:self.scene_view.play()

    def show_conversation(self):
        if self.original is None:return
        if not self.dialog_view.active:raise GameError('No conversation is waiting for a response.')
        self.dialog_view.sync();self.show_original('dialog')

    def scene_key(self,event):
        if self.screen=='intro' and event.widget is self.original and event.keysym not in ('Escape','F2','F10','F11','space'):
            self.guard(self.intro_view.input);return
        if self.startup is not None and event.widget is self.original:
            view=self.startup;key=event.keysym
            action=({'n':('startup','new'),'l':('startup','load'),'i':('startup','intro'),'q':('startup','quit')}.get(key.lower()) if view.stage=='menu' else
                    {'Left':('hero',2),'Right':('hero',1)}.get(key) if view.stage=='choose' else
                    ('startup','start') if key=='Return' else None)
            if action:self.guard(lambda:view.dispatch(self,action))
            return
        if self.screen=='scene' and event.widget is self.original and event.keysym not in ('Escape','F2','F11','p','P'):
            if self.scene_view.playable:self.scene_view.key_pending=True

    def original_refresh(self):
        if self.startup is not None:
            if self.startup.owner is self.session:self.render_original();return
            self.startup=None;self.screen='bridge';self.pointer.cancel(reset=True)
        if self.cockpit_context is not None and not self.cockpit_context.current(self.session):
            self.cockpit_view=None
            self.cockpit_context=None
            self.route_return=None
            self.pointer.cancel(reset=True)
            if self.screen=='cockpit':self.screen='bridge'
        if self.cargo_context is not None and not self.cargo_context.current(self.session):
            self.cargo_view = None
            self.cargo_context = None
            self.pointer.cancel(reset=True)
            if self.screen=='cargo':self.screen='bridge'
        if not self.fleet_context.current(self.session):
            self.fleet_context = FleetContext(self.session)
            self.fleet_view = FleetView()
            self.new_fleet_view = None
            self.fleet_signature = None
            self.pointer.cancel(reset=True)
            if self.screen in ('fleets','new_fleet'):
                self.cancel_equipment_name()
                self.screen = 'bridge'
        if self.equipment_context is not None and not self.equipment_context.current(self.session):
            self.cancel_equipment_name()
            self.equipment_view = None
            self.equipment_context = None
            if self.screen == 'equipment':self.screen = 'bridge'
        if not self.orbital_context.current(self.session):
            self.orbital_context = FleetContext(self.session)
            self.orbital_selected = None
            self.orbital_page = 0
            self.route_fleet = None
            self.pointer.cancel(reset=True)
        if self.screen_session is not self.session:
            self.bridge_cinema.leave()
            self.research_cinema.cancel()
            self.navigation_sound.cancel()
            self.cockpit_cinema.cancel()
            self.disk_cinema.cancel()
            if self.screen=='disk':self.disk_slots.refresh()
            self.screen_session = self.session
            self.commander_rank = None
            self.research_selected = None
            self.production_view = ProductionView()
            self.map_view = MapView()
            self.planet_id = '1:5:0'
            self.planet_landscape = False
            self.race_view = None
            self.planet_action_signature = None
            self.colony_view = None
            self.colony_context = None
            self.world_list_view = WorldListView()
            self.world_list_rows = []
            self.surface_context = None
            self.surface_view = SurfaceView()
            self.surface_drag = False
            self.mining_context = None
            self.message_offset = 0
            self.menu_page = 0
            self.disk_pressed = 0
            self.pointer.cancel(reset=True)
        self.space_view.sync()
        self.ground_view.sync()
        self.scene_view.sync()
        self.dialog_view.sync()
        self.bar_view.sync()
        self.adviser_view.sync()
        if getattr(self,'credits_view',None) is not None:self.credits_view.sync()
        if getattr(self,'intro_view',None) is not None:self.intro_view.sync()
        if self.intro_view.active:
            if self.screen!='intro':self.show_original('intro')
            else:self.render_original()
            return
        defeat_autoplay=self.defeat_view.sync()
        victory_autoplay=self.victory_view.sync()
        if self.victory_view.active:
            if self.screen!='victory':self.show_original('victory')
            else:self.render_original()
            if victory_autoplay:self.victory_view.play()
            return
        if self.defeat_view.active:
            if self.screen!='defeat':self.show_original('defeat')
            else:self.render_original()
            if defeat_autoplay:self.defeat_view.play()
            return
        if self.screen in ('defeat','victory'):self.show_original();return
        if self.screen=='credits' and not self.credits_view.active:
            self.show_original();return
        if self.screen=='intro' and not self.intro_view.active:
            self.open_startup();return
        if self.screen=='adviser' and not self.adviser_view.active:
            self.show_original();return
        if self.bar_view.active and self.screen!='bar':
            self.show_original('bar');return
        if self.screen=='bar':
            self.bar_controls.pack_forget();self.clock_bar.pack_forget()
            (self.bar_controls if self.bar_view.active else self.clock_bar).pack(side='bottom',fill='x')
        if self.dialog_view.active and self.screen!='dialog':
            self.show_conversation();return
        if not self.dialog_view.active and self.screen=='dialog':
            self.show_original();return
        if self.scene_view.active and self.screen!='scene':
            self.show_original('scene');return
        if not self.scene_view.active and self.screen=='scene':
            self.show_original();return
        if self.ground_view.active and self.screen!='ground':
            self.show_ground_battle()
            return
        if not self.ground_view.active and self.screen=='ground':
            self.show_original()
            return
        if (self.session.state['ground_encounter'] or {}).get('phase')=='setup' and self.screen!='ground_setup':
            self.show_ground_battle()
            return
        if (self.session.state['ground_encounter'] or {}).get('phase')!='setup' and self.screen=='ground_setup':
            self.show_original()
            return
        if self.space_view.active and self.screen!='space':
            self.show_space_battle()
            return
        if not self.space_view.active and self.screen=='space':
            self.show_original()
            return
        self.render_original()

    def show_original(self, screen='bridge', *, navigation_sound=None):
        if getattr(self,'bridge_cinema',None) is not None:self.bridge_cinema.leave()
        if screen != 'research' and getattr(self,'research_cinema',None) is not None:self.research_cinema.cancel()
        requested_screen=screen
        navigation=getattr(self,'navigation_sound',None)
        retained=navigation is not None and navigation_sound is None and navigation.retain(screen)
        if navigation is not None and not retained:navigation.cancel()
        if not (self.cockpit_cinema.handoff and screen=='starmap'):self.cockpit_cinema.cancel()
        self.disk_pressed=0
        self.disk_cinema.cancel()
        state=self.session.state
        pending_kind=state['presentation_requests'][0]['kind'] if state['presentation_requests'] else None
        if screen!='intro' and self.startup is None and state['presentation_requests'] and state['active_scene'] is None and state['active_dialog'] is None and all(
                (state[key] or {}).get('phase','closed')=='closed' for key in ('space_encounter','ground_encounter')) and (
                pending_kind=='scene' or pending_kind=='dialog' and state['campaign_phase']=='starmap') and not self.bar_view.active:
            # Back may skip a transient landing, but must not strand its story.
            # Notices already render through scene_view without starting a scene.
            # Do not retry deferred conversations from inside refresh.
            self.show_presentation();return
        if screen!='intro' and self.dialog_view.active:screen='dialog'
        elif screen!='intro' and self.scene_view.active:screen='scene'
        elif screen!='intro' and self.space_view.active:screen='space'
        elif screen!='intro' and (self.session.state['ground_encounter'] or {}).get('phase')=='setup':screen='ground_setup'
        elif screen!='intro' and self.ground_view.active:screen='ground'
        elif screen!='intro' and self.bar_view.active:screen='bar'
        elif screen!='intro' and self.adviser_view.active:screen='adviser'
        elif screen!='intro' and self.victory_view.active:screen='victory'
        elif screen!='intro' and self.defeat_view.active:screen='defeat'
        if screen!='credits' and getattr(self,'credits_view',None) is not None:self.credits_view.leave()
        if screen!='intro' and getattr(self,'intro_view',None) is not None:self.intro_view.leave()
        if screen!='victory':self.victory_view.pause()
        if screen!='defeat':self.defeat_view.pause()
        self.race_view = None
        if screen!='space':self.space_view.pause()
        if screen!='ground':self.ground_view.pause()
        if screen!='scene':self.scene_view.pause()
        self.cancel_equipment_name()
        if screen!='new_fleet':self.new_fleet_view=None
        if screen!='colonize':
            self.colony_view=None
            self.colony_context=None
        self.surface_drag = False
        if screen != 'starmap':
            self.route_fleet = None
            self.route_return = None
        self.stop_model_timer()
        self.production_view.quantity = None
        self.pointer.cancel(reset=True)
        self.screen = screen
        if navigation_sound is not None and navigation is not None and screen==requested_screen:
            navigation.start(navigation_sound,screen)
        elif retained and not navigation.retain(screen):navigation.cancel()
        if screen=='disk':self.clock_panel.clock.pause();self.disk_slots.refresh()
        if screen!='surface':self.surface_return=None
        self.menu_page = 0
        self.caption = ''
        self.workbench.pack_forget()
        self.root.minsize(640, 400+self.clock_bar_height)
        if getattr(self,'credits_bar',None) is not None:self.credits_bar.pack_forget()
        if getattr(self,'intro_bar',None) is not None:self.intro_bar.pack_forget()
        for bar in (self.clock_bar,self.space_bar,self.ground_setup_bar,self.ground_bar,self.scene_bar,self.dialog_bar,self.bar_controls,self.adviser_bar,self.defeat_bar,self.victory_bar):bar.pack_forget()
        (self.victory_bar if screen=='victory' else self.defeat_bar if screen=='defeat' else self.adviser_bar if screen=='adviser' else self.bar_controls if screen=='bar' and self.bar_view.active else self.dialog_bar if screen=='dialog' else self.scene_bar if screen=='scene' else self.space_bar if screen=='space' else self.ground_bar if screen=='ground' else self.ground_setup_bar if screen=='ground_setup' else self.clock_bar).pack(side='bottom',fill='x')
        if screen=='credits':self.clock_bar.pack_forget();self.credits_bar.pack(side='bottom',fill='x')
        if screen=='intro':self.clock_bar.pack_forget();self.intro_bar.pack(side='bottom',fill='x')
        self.original.pack(fill='both', expand=True)
        self.original.focus_set()
        self.render_original()

    def show_tools(self, tab):
        self.bridge_cinema.leave()
        self.research_cinema.cancel()
        self.navigation_sound.cancel()
        self.cockpit_cinema.cancel()
        self.disk_cinema.cancel()
        if getattr(self,'credits_view',None) is not None:self.credits_view.leave();self.credits_bar.pack_forget()
        if getattr(self,'intro_view',None) is not None:self.intro_view.leave();self.intro_bar.pack_forget()
        self.startup=None
        self.victory_view.pause();self.victory_bar.pack_forget()
        self.defeat_view.pause();self.defeat_bar.pack_forget()
        self.adviser_bar.pack_forget()
        self.bar_controls.pack_forget()
        self.dialog_bar.pack_forget()
        self.scene_view.pause();self.scene_bar.pack_forget()
        self.space_view.pause()
        self.ground_view.pause()
        self.ground_bar.pack_forget()
        self.space_bar.pack_forget()
        self.ground_setup_bar.pack_forget()
        self.cancel_equipment_name()
        self.route_fleet = None
        self.stop_model_timer()
        self.production_view.quantity = None
        self.pointer.cancel(reset=True)
        self.original.pack_forget()
        self.clock_bar.pack_forget()
        self.root.minsize(980, 720)
        self.workbench.pack(fill='both', expand=True)
        self.book.select(self.tabs[tab])
        self.root.geometry('1180x820')
        self.status.set('This screen still uses development controls. Esc returns to the original control room.')

    def render_original(self):
        if self.original is None or not self.original.winfo_exists():
            return
        self.clock_bar.refresh()
        width, height = self.original.winfo_width(), self.original.winfo_height()
        previous_geometry=(self.scale,self.origin)
        self.scale = max(1, min(width//320, height//200))
        self.origin = ((width-320*self.scale)//2, (height-200*self.scale)//2)
        if previous_geometry!=(self.scale,self.origin):self.cancel_original_pointer()
        if self.startup is not None:
            target=self.startup.draw(self.screen_renderer)
        elif self.screen=='intro':
            self.intro_bar.sync();target=self.intro_view.draw()
        elif self.screen=='credits':
            self.credits_bar.sync();target=self.credits_view.draw()
        elif self.screen=='victory':
            self.victory_bar.sync();target=self.victory_view.draw()
        elif self.screen=='defeat':
            self.defeat_bar.sync();target=self.defeat_view.draw()
        elif self.screen=='adviser':
            self.adviser_bar.sync();target=self.adviser_view.draw()
        elif self.screen=='bar':
            if self.bar_view.active:self.bar_controls.sync()
            target=self.bar_view.draw()
        elif self.screen=='dialog':
            self.dialog_bar.sync();target=self.dialog_view.draw()
        elif self.screen=='scene':
            self.scene_bar.sync();target=self.scene_view.draw()
        elif self.screen=='ground':
            self.ground_bar.sync();target=self.ground_view.draw()
        elif self.screen=='ground_setup':
            signature=setup_signature(self.session.state)
            if signature!=self.ground_setup_signature:self.pointer.cancel(reset=True)
            self.ground_setup_signature=signature
            target=draw_setup(self.screen_renderer,self.session.state,self.caption or 'GROUND DEPLOYMENT')
        elif self.screen == 'space':
            self.space_bar.sync()
            target=self.space_view.draw()
        elif self.screen == 'bridge':
            target = self.bridge_cinema.draw(self.session.state, self.menu_page, self.caption or 'CONTROL ROOM', self.hero)
        elif self.screen == 'commanders':
            target = self.screen_renderer.commanders(self.session.state, self.commander_role, self.commander_rank, self.caption or 'COMMANDERS')
        elif self.screen == 'research':
            target = self.screen_renderer.research(self.session.state, self.research_selected, self.caption or 'RESEARCH-DESIGN')
            self.research_cinema.draw(target)
        elif self.screen == 'messages':
            target = self.screen_renderer.messages(self.session.state, self.message_offset, self.caption or 'MESSAGES')
        elif self.screen == 'production':
            target = self.screen_renderer.production(self.session.state, self.production_view, self.caption or 'INFO-BUY', self.model_angle)
        elif self.screen == 'cockpit':
            if self.cockpit_context is None or not self.cockpit_context.current(self.session):
                self.show_original()
                return
            signature=self.cockpit_view.signature(self.session.state,self.catalog)
            if signature!=self.cockpit_signature:self.pointer.cancel(reset=True)
            self.cockpit_signature=signature
            if len(self.cockpit_view.buttons(self.session.state,self.catalog))<=6:self.menu_page=0
            target=(self.cockpit_cinema.frame() if self.cockpit_cinema.running else
                    self.screen_renderer.cockpit(self.session.state,self.cockpit_view,self.caption or 'CONTROL PANEL',self.menu_page))
        elif self.screen == 'cargo':
            if self.cargo_context is None or not self.cargo_context.current(self.session):
                self.show_original()
                return
            report=self.cargo_view.report(self.session.state,self.catalog)
            if report!=self.cargo_signature:self.pointer.cancel(reset=True)
            self.cargo_signature=report
            target=self.screen_renderer.cargo(self.session.state,self.cargo_view,self.caption or 'TRANSFER')
        elif self.screen == 'equipment':
            if self.equipment_context is None or not self.equipment_context.current(self.session):
                self.show_original()
                return
            report = self.equipment_view.report(self.session.state,self.catalog)
            if report != self.equipment_signature:self.pointer.cancel(reset=True)
            self.equipment_signature = report
            if len(self.equipment_view.buttons(self.session.state))<=6:self.menu_page=0
            target = self.screen_renderer.equipment(self.session.state,self.equipment_view,self.caption or 'EQUIPMENT',self.menu_page)
        elif self.screen in ('fleets','new_fleet'):
            signature=(tuple(tuple(r) for bank in ('moving','local') for r in self.session.state['fleets'][bank]),
                       tuple(available_types(self.session.state)),self.session.state['levels']['pilot'])
            if signature!=self.fleet_signature:self.pointer.cancel(reset=True)
            self.fleet_signature=signature
            if self.screen=='new_fleet':
                if self.new_fleet_view is None or self.new_fleet_view.kind not in available_types(self.session.state):
                    self.show_original('fleets')
                    return
                target=self.screen_renderer.new_fleet(self.session.state,self.new_fleet_view,self.caption or 'NEW UNIT')
            else:target=self.screen_renderer.fleets(self.session.state,self.fleet_view,self.caption or 'SHIP INFO')
        elif self.screen == 'starmap':
            entries = orbital_entries(self.session.state, self.catalog, self.map_view.system, self.map_view.planet)
            if entries != self.orbital_entries:
                self.pointer.cancel(reset=True)
            self.orbital_entries = entries
            self.orbital_page = min(self.orbital_page, max(0, (len(self.orbital_entries)-1)//18))
            if not any(e and e['key'] == self.orbital_selected for e in self.orbital_entries):
                self.orbital_selected = None
            signature = attack_signature(self.session.state,entries,self.orbital_selected,
                map_buttons(self.session.state,self.map_view.planet,entries,self.orbital_selected,routing=self.route_fleet is not None))
            if signature != self.orbital_attack_signature:self.pointer.cancel(reset=True)
            self.orbital_attack_signature = signature
            target, self.map_bodies = self.screen_renderer.starmap(self.session.state, self.map_view,
                self.caption or self.catalog['system_names'][self.map_view.system-1],
                entries=self.orbital_entries, page=self.orbital_page, selected=self.orbital_selected,
                routing=self.route_fleet is not None)
        elif self.screen == 'mining':
            if (self.mining_context is None or not self.mining_context.current(self.session)
                    or not mining_available(self.session.state,self.mining_world)):
                self.mining_context = None
                self.show_original()
                return
            report = mining_report(self.session.state,self.mining_world)
            if report != self.mining_signature:self.pointer.cancel(reset=True)
            self.mining_signature = report
            target = self.screen_renderer.mining(self.session.state,self.mining_world,self.caption or self.mining_context.definition['name'])
        elif self.screen == 'surface':
            if self.surface_context is None or not self.surface_context.current(self.session):
                self.surface_context = None
                self.show_original()
                return
            if self.surface_return is not None:
                context,index=self.surface_return
                if not context.current(self.session) or not 0<=index<len(self.session.state['fleets']['moving']):
                    self.surface_return=None;self.pointer.cancel(reset=True)
            signature = (tuple(tuple(r) for r in self.session.state['buildings']),
                         self.session.state['resources']['credits'],
                         tuple(d['id'] for d in self.surface_view.choices(self.session.state,self.catalog)),
                         surface_revealed(self.session.state['worlds'][self.surface_view.world_id]['raw']),
                         tuple(tuple(row) for row in self.session.state['fleets']['local']))
            if signature != self.surface_signature:
                self.pointer.cancel(reset=True)
                self.surface_drag = False
            self.surface_signature = signature
            target = self.screen_renderer.surface(self.session.state,self.surface_view,self.caption or
                self.surface_context.definition['name'],return_cockpit=self.surface_return is not None)
        elif self.screen == 'world_list':
            rows = list_lines(self.session.state, self.catalog, self.world_list_view.mode)
            if rows != self.world_list_rows:
                self.pointer.cancel(reset=True)
            self.world_list_rows = rows
            target = self.screen_renderer.world_list(self.session.state, self.world_list_view, rows,
                self.caption or self.catalog['control_buttons'][74+self.world_list_view.mode]['label'])
        elif self.screen == 'colonize':
            if (self.colony_context is None or not self.colony_context.current(self.session)
                    or not settlement_offered(self.session.state,self.catalog,self.colony_view.world_id)):
                self.show_original('planet')
                return
            signature=action_signature(self.session.state,self.colony_view.world_id)
            if signature!=self.colony_signature:self.pointer.cancel(reset=True)
            self.colony_signature=signature
            target=self.screen_renderer.colonize(self.session.state,self.colony_view,
                                                 self.caption or self.colony_context.definition['name'])
        elif self.screen == 'planet':
            definition = next(w for w in self.catalog['worlds'] if w['id'] == self.planet_id)
            if not world_visible(self.session.state, definition):
                self.show_original('starmap')
                return
            signature=action_signature(self.session.state,self.planet_id)
            if signature!=self.planet_action_signature:
                self.pointer.cancel(reset=True)
                self.planet_action_signature=signature
            if len(planet_buttons(self.session.state,self.catalog,self.planet_id))<=6:self.menu_page=0
            if self.race_view is not None:
                if not self.race_view.current(self.session,self.planet_id):
                    self.race_view=None;self.pointer.cancel(reset=True)
                elif self.race_view.sync(self.session.state):self.pointer.cancel(reset=True)
            target = (self.race_view.draw(self.screen_renderer,self.session.state,
                self.caption or definition['name'],planet_buttons(self.session.state,self.catalog,self.planet_id),self.menu_page)
                if self.race_view is not None else self.screen_renderer.planet(self.session.state, self.planet_id,
                self.caption or definition['name'], self.planet_landscape,self.menu_page))
        else:
            from .disk_screen import draw
            target = draw(self.screen_renderer,self.session.state,self.session.audio,self.session.effects,
                          self.caption or 'DISK OPERATIONS',self.disk_pressed)
            self.disk_slots.draw(self.screen_renderer,target)
            self.disk_cinema.draw(self.screen_renderer,target,self.session.audio['main'])
        self.frame_pixels = target.ppm()
        photo=tk.PhotoImage(master=self.original,data=self.frame_pixels,format='PPM')
        if self.screen in ('credits','intro') and self.startup is None and (target.width,target.height)==(640,480):
            # Preserve the real 640x480 interlude. Integer reduction at small
            # window sizes keeps the whole image visible without distorting it.
            self.scale=max(1,min(width//target.width,height//target.height))
            reduction=max(1,(target.width+max(1,width)-1)//max(1,width),
                          (target.height+max(1,height)-1)//max(1,height))
            self.screen_image=photo.subsample(reduction) if reduction>1 else photo.zoom(self.scale)
            self.origin=((width-self.screen_image.width())//2,(height-self.screen_image.height())//2)
        else:self.screen_image=photo.zoom(self.scale)
        self.original.itemconfigure(self.screen_item, image=self.screen_image)
        self.original.coords(self.screen_item, *self.origin)
        if self.equipment_editor is not None:
            x,y=self.name_editor_position
            self.original.coords(self.equipment_editor_item,self.origin[0]+x*self.scale,self.origin[1]+y*self.scale)
            self.original.itemconfigure(self.equipment_editor_item,width=102*self.scale,height=9*self.scale)
            self.equipment_editor.configure(font=('Courier New',-8*self.scale))
        if not self.cockpit_cinema.running and (self.screen in ('starmap','cockpit','surface') or self.screen == 'production' and not self.production_view.selecting) and self.original.winfo_ismapped() and self.model_timer is None:
            self.model_timer = self.root.after(40 if self.screen == 'surface' else 80, self.animate_model)

    def original_slot(self, event):
        x = (event.x-self.origin[0])//self.scale
        y = (event.y-self.origin[1])//self.scale
        if not (0 <= x < 320 and 0 <= y < 200):
            return 0
        targets = self.targets()
        if self.startup is not None:
            return next((i+21 for i,(rect,_,__) in enumerate(targets)
                         if rect[0]<=x<rect[0]+rect[2] and rect[1]<=y<rect[1]+rect[3]),0)
        slot = pointer_slot(x, y, [r[0] for r in targets])
        return slot+6*self.menu_page if 1 <= slot <= 6 else slot

    def targets(self):
        if self.startup is not None:return self.startup.targets()
        if self.screen in ('defeat','victory','credits','intro'):return []
        if self.screen=='disk':
            from .disk_screen import targets
            from .disk_slots import SLOT_RECT
            return targets()+[(SLOT_RECT,'Select save slot',('disk_slot',))]
        if self.screen=='adviser':return self.adviser_view.targets()
        if self.screen=='bar':return self.bar_view.targets()
        if self.screen=='dialog':return self.dialog_view.targets()
        if self.screen=='scene':return []
        if self.screen=='ground':return self.ground_view.targets()
        if self.screen=='ground_setup':return setup_targets(self.session.state)
        if self.screen=='space':return []
        if self.screen=='fleets':return self.fleet_view.targets(self.session.state)
        if self.screen=='new_fleet':return self.new_fleet_view.targets()
        if self.screen=='equipment':return self.equipment_view.targets(self.session.state,self.catalog)
        if self.screen=='cargo':return self.cargo_view.targets(self.session.state,self.catalog)
        if self.screen=='cockpit':return self.cockpit_view.targets(self.session.state)
        if self.screen=='colonize':return self.colony_view.targets(self.catalog)
        if self.screen == 'mining':
            return [((0,49,320,151),'Return to surface',41)]
        if self.screen == 'surface':
            return self.surface_view.targets()
        if self.screen == 'world_list':
            return self.world_list_view.targets(self.world_list_rows)
        if self.screen == 'bridge':
            return bridge_targets(self.session.state, self.catalog)
        if self.screen == 'research':
            return research_targets(self.session.state, self.catalog)
        if self.screen == 'production':
            return self.production_view.targets(self.session.state)
        if self.screen == 'starmap':
            targets = self.map_view.targets(self.session.state, self.catalog, self.map_bodies)
            if self.route_fleet is not None:
                if not self.map_view.planet:
                    targets.append(((128,92,64,64), 'System destination', ('route_system',)))
                return targets
            controls = orbital_targets(self.orbital_entries, self.orbital_page)
            if self.orbital_selected and self.orbital_selected[0] == 'player':
                row = self.session.state['fleets']['moving'][self.orbital_selected[1]]
                if row[22] in (1,2):
                    controls.append(((8,183,72,8), 'Launch' if row[22] == 1 else 'Land', ('orbital_toggle',)))
                    if row[22] == 2:
                        controls.append(((104,183,72,8), 'Move fleet', ('orbital_route',)))
            return controls+targets
        if self.screen == 'planet':
            if self.race_view is not None:return self.race_view.targets(self.session.state)
            return [((0, 49, 320, 151), 'Back to information', ('planet_landscape',))] if self.planet_landscape else [
                *([((0,49,57,47),'Race information',('planet_race',))]
                  if revealed_race(self.session.state['worlds'][self.planet_id]['raw']) is not None else []),
                ((0, 97, 57, 47), 'Orbit and moons', ('planet_orbit',)),
                ((0, 145, 96, 55), 'See surface', ('planet_landscape',))]
        if self.screen == 'commanders':
            return [((i*107, 49, 106 if i < 2 else 106, 111),
                     self.catalog['commanders'][self.commander_role*3+i]['name'], ('candidate', i+1))
                    for i in range(3)]
        return []

    def action(self, slot):
        if self.screen in ('defeat','victory','credits'):return '',None
        if self.startup is not None:
            targets=self.startup.targets()
            return targets[slot-21][1:] if 21<=slot<21+len(targets) else ('',None)
        if self.screen=='adviser':
            if slot==1:return 'Back to control room',24
            targets=self.adviser_view.targets()
            return targets[slot-21][1:] if 21<=slot<21+len(targets) else ('',None)
        if self.screen=='bar':
            if slot==1 and not self.bar_view.active:return 'Back to control room',24
            if slot>=21:
                targets=self.bar_view.targets()
                if slot<21+len(targets):return targets[slot-21][1:]
            return ('TIME','time') if slot==14 and not self.bar_view.active else ('',None)
        if self.screen=='dialog':
            targets=self.dialog_view.targets()
            return targets[slot-21][1:] if 21<=slot<21+len(targets) else ('',None)
        if self.screen=='scene':
            return ('Continue',65) if slot==1 and self.scene_view.notice else ('',None)
        if self.equipment_editor is not None:return '',None
        if 1 <= slot <= 12:
            if self.screen=='ground':
                layout=32 if self.ground_view.encounter()['phase']=='fighting' else 30
                buttons=select_layout(self.catalog['control_layouts'],layout)['buttons']
                action=(buttons+[0]*12)[slot-1]
                return self.catalog['control_buttons'][action]['label'] if action else '',action if self.ground_view.enabled(action) else None
            elif self.screen=='ground_setup':buttons=setup_buttons(self.session.state)
            elif self.screen=='space':
                layout=29 if self.space_view.encounter()['phase']=='fighting' else 30
                buttons=select_layout(self.catalog['control_layouts'],layout)['buttons']
                action=(buttons+[0]*12)[slot-1]
                return self.catalog['control_buttons'][action]['label'] if action else '',action if self.space_view.enabled(action) else None
            elif self.screen == 'starmap':
                buttons = map_buttons(self.session.state,self.map_view.planet,self.orbital_entries,
                                      self.orbital_selected,routing=self.route_fleet is not None)
            elif self.screen == 'planet':
                buttons=planet_buttons(self.session.state,self.catalog,self.planet_id)
            elif self.screen=='colonize':buttons=[59,58]
            elif self.screen=='fleets':buttons=self.fleet_view.buttons(self.session.state)
            elif self.screen=='equipment':buttons=self.equipment_view.buttons(self.session.state)
            elif self.screen=='new_fleet':buttons=[60,58]
            elif self.screen=='cargo':buttons=[24,13,16,49]
            elif self.screen=='surface':buttons=surface_buttons(self.session.state,self.surface_view.world_id,return_cockpit=self.surface_return is not None)
            elif self.screen=='cockpit':buttons=self.cockpit_view.buttons(self.session.state,self.catalog)
            else:
                layout = self.production_view.layout if self.screen == 'production' else {'bridge': 1, 'commanders': 2, 'research': 3, 'disk': 12, 'messages': 11, 'world_list':37,'surface':20,'mining':4,'equipment':22}[self.screen]
                buttons = select_layout(self.catalog['control_layouts'], layout)['buttons']
            action = (buttons+[0]*12)[slot-1]
            return self.catalog['control_buttons'][action]['label'] if action else '', action
        if slot >= 21 and slot-21 < len(self.targets()):
            _, label, action = self.targets()[slot-21]
            return label, action
        if slot == 13 and (self.screen == 'bridge' or self.screen=='planet' and
                          len(planet_buttons(self.session.state,self.catalog,self.planet_id))>6 or
                          self.screen=='equipment' and len(self.equipment_view.buttons(self.session.state))>6 or
                          self.screen=='cockpit' and len(self.cockpit_view.buttons(self.session.state,self.catalog))>6):
            return 'MORE ICONS', 'page'
        if slot == 14:
            return 'TIME', 'time'
        return '', None

    def hover(self, caption):
        if caption != self.caption:
            self.caption = caption
            self.render_original()

    def original_motion(self, event):
        if self.screen=='adviser':
            action=self.action(self.original_slot(event))[1]
            hovered=action[1] if isinstance(action,tuple) and action[0]=='adviser_choice' else None
            if hovered!=self.adviser_view.hovered:self.adviser_view.hovered=hovered;self.render_original()
        if self.screen=='bar' and self.bar_view.active:
            action=self.action(self.original_slot(event))[1]
            hovered=action[1] if isinstance(action,tuple) and action[0]=='bar_choice' else None
            if hovered!=self.bar_view.hovered:self.bar_view.hovered=hovered;self.render_original()
        if self.screen=='dialog':
            action=self.action(self.original_slot(event))[1]
            self.dialog_view.hovered=action[1] if isinstance(action,tuple) and action[0]=='dialog_choice' else None
            self.render_original()
        if self.screen == 'surface':
            if self.surface_drag:
                if event.state & 0x100:
                    self.surface_radar(event)
                    return
                self.cancel_original_pointer()
            action = self.action(self.original_slot(event))[1]
            tile = action[1:] if isinstance(action,tuple) and action[0] == 'surface_tile' else None
            if self.surface_view.tile != tile:
                self.surface_view.tile = tile
                if self.surface_view.mode == 'build':self.render_original()
        caption, action = self.action(self.original_slot(event))
        self.original.configure(cursor='hand2' if action else '')
        self.hover(caption)

    def original_press(self, event):
        # Finish an inline name before resolving the clicked control. Moving
        # focus first left the editor open while action() disabled every icon.
        if self.equipment_editor is not None:
            self.name_editor_submit()
        self.original.focus_set()
        if event.num==2:
            slot=self.original_slot(event)
            self.pointer.cancel(reset=True)
            self.pointer.press(2,slot,self.quantity_target(self.action(slot)[1]))
            return
        if self.screen=='intro':self.guard(self.intro_view.input);return
        if self.screen=='scene' and not self.scene_view.notice:
            x=(event.x-self.origin[0])//self.scale;y=(event.y-self.origin[1])//self.scale
            self.scene_view.mouse=event.num==1 and 0<=x<320 and 0<=y<200
            return
        slot = self.original_slot(event)
        self.pointer.press(event.num, slot, bool(self.action(slot)[1]))
        if self.screen=='disk' and 21<=slot<=24:
            self.disk_pressed=slot-20;self.render_original()
        if self.screen == 'surface' and self.action(slot)[1] == ('surface_radar',):
            self.surface_drag = event.num == 1
            self.surface_radar(event)

    def cancel_original_pointer(self, event=None):
        # Destroying the inline Entry can queue a FocusOut after focus has
        # already returned to this canvas. It must not cancel the new click.
        if event is not None and event.type==tk.EventType.FocusOut and self.original.focus_get() is self.original:
            return
        if self.screen=='disk' and self.disk_pressed:
            self.disk_pressed=0;self.render_original()
        self.scene_view.clear_input()
        self.surface_drag = False
        self.pointer.cancel(reset=True)

    def original_release(self, event):
        if event.num==2:
            slot=self.pointer.release(2,self.original_slot(event),True)
            if slot:self.adjust_quantity(self.action(slot)[1],maximum=True,reverse=bool(event.state & 1))
            return
        if self.screen=='scene' and not self.scene_view.notice:
            self.scene_view.mouse=False;return
        if self.surface_drag:
            self.surface_drag = False
            self.pointer.cancel(reset=True)
            return
        slot = self.pointer.release(event.num, self.original_slot(event), True)
        if self.screen=='disk' and self.disk_pressed:
            self.disk_pressed=0;self.render_original()
        if slot:
            action = self.action(slot)[1]
            if event.state & 1 and self.quantity_target(action):
                self.adjust_quantity(action,maximum=True,reverse=event.num==3)
                return
            if self.screen=='bridge' and slot in (27,28,31):
                if slot==27:self.commander_rank=None
                self.bridge_cinema.start({27:'commanders',28:'production',31:'fleets'}[slot])
            elif action==('ground_board',):
                if event.num==3:self.ground_view.command('context_cancel')
                else:self.ground_view.command('click',x=(event.x-self.origin[0])//self.scale,y=(event.y-self.origin[1])//self.scale)
            elif action == ('world_scroll',):
                self.world_list_view.scroll_to(self.world_list_rows, (event.y-self.origin[1])//self.scale)
                self.render_original()
            elif action == ('disk_slot',):
                self.disk_slots.select((event.y-self.origin[1])//self.scale)
            else:
                self.dispatch(action, event.num)

    def clock_edit_reason(self):
        if getattr(self,'bridge_cinema',None) is not None and self.bridge_cinema.running:return 'Control Room door animation'
        if getattr(self,'research_cinema',None) is not None and self.research_cinema.running:return 'Research disc animation'
        if self.cockpit_cinema.running and self.cockpit_cinema.mode=='route':return 'Opening navigation'
        if self.cockpit_cinema.running:return 'Landing' if self.session.state['fleets']['moving'][self.cockpit_cinema.index][22]==1 else 'Launching'
        if self.startup is not None:return self.startup.hint()
        if self.screen=='credits':return 'Game Credits playback'
        if self.screen=='disk':return 'Disk operations'
        if self.screen=='adviser':return 'Finish the commander consultation'
        if self.screen=='new_fleet':return 'Create or abort the new group'
        if self.equipment_editor is not None:return 'Finish or cancel the fleet name'
        if self.screen=='colonize':return 'Confirm or abort the colony purchase'
        if self.screen == 'surface' and self.surface_view.mode in ('build','demolish'):
            return 'Finish placement or right-click to cancel'
        if self.route_fleet is not None:
            return 'Choose destination or Abort Move'
        if self.screen == 'production' and self.production_view.quantity is not None:
            view=self.production_view
            if view.limited and view.selected is not None:
                definition=self.catalog['products'][view.selected-1]
                row=self.session.state['products'][view.selected-1]
                if view.quantity>=order_limit(self.session.state,definition,row):
                    return 'Production order: '+order_limit_reason(self.session.state,definition,row)
            return 'Confirm or cancel production order'

    def toggle_time(self, fast=False):
        if self.startup is not None:return
        if self.screen=='intro':self.intro_view.toggle();return
        if self.screen=='defeat':self.defeat_view.toggle();return
        if self.screen=='victory':self.victory_view.toggle();return
        if self.screen=='credits':self.credits_view.toggle();return
        if self.screen in ('dialog','adviser'):return
        if self.screen=='scene':
            if self.scene_view.playable:self.scene_view.key_pending=True
            return
        if self.screen=='ground':
            self.ground_view.toggle()
            return
        if self.screen=='space':
            self.space_view.toggle()
            return
        clock = self.clock_panel.clock
        if clock.running:
            clock.pause()
        else:
            if fast:clock.set_interval(83)
            clock.start()

    def scroll_messages(self, lines):
        if self.screen=='adviser':self.adviser_view.scroll(lines);return
        if self.screen=='bar':self.bar_view.scroll(lines);return
        if self.screen=='dialog':self.dialog_view.scroll(lines);return
        if self.screen=='scene':self.scene_view.scroll(lines);return
        if self.screen=='fleets':
            self.fleet_view.scroll(self.session.state,1 if lines>0 else -1)
            self.pointer.cancel(reset=True)
            self.render_original()
            return
        if self.screen == 'world_list':
            self.world_list_view.scroll(self.world_list_rows, lines)
            self.pointer.cancel(reset=True)
            self.render_original()
            return
        if self.screen == 'starmap' and self.map_view.planet and self.route_fleet is None:
            self.orbital_page = max(0, min(max(0, (len(self.orbital_entries)-1)//18), self.orbital_page+(1 if lines > 0 else -1)))
            self.pointer.cancel(reset=True)
            self.render_original()
            return
        if self.screen == 'messages':
            count = len(self.screen_renderer.message_lines(self.session.state))
            self.message_offset = min(max(0, count-17), max(0, self.message_offset+lines))
            self.render_original()

    def quantity_target(self,action):
        return isinstance(action,tuple) and (self.screen,action[0]) in (
            ('equipment','equipment_transfer'),('cargo','cargo_transfer'),('ground_setup','ground_quantity'))

    def adjust_quantity(self,action,*,maximum=False,reverse=False,direction=None,steps=1):
        if not self.quantity_target(action):return
        self.pointer.cancel(reset=True)
        if self.screen=='equipment':
            loading=direction>0 if direction is not None else not reverse
            self.equipment_action(action,1 if loading else 3,maximum=maximum,steps=steps,bounded=True)
        elif self.screen=='cargo':
            self.cargo_context.require(self.session)
            loading=direction>0 if direction is not None else bool(action[3]) != reverse
            args=self.cargo_view.transfer(self.session.state,self.catalog,*action[1:3],loading,1,
                                          maximum=maximum,steps=steps)
            if args:self.act('transfer_cargo',**args)
            self.render_original()
        else:
            loading=direction>0 if direction is not None else not reverse
            self.act('ground_edit',operation='increase' if loading else 'decrease',selection=action[1],
                     amount=32767 if maximum else steps)

    def scroll_original(self, event):
        if event.delta and self.screen in ('equipment','cargo','ground_setup'):
            action=self.action(self.original_slot(event))[1]
            steps=min(100,max(1,abs(event.delta)//120)*(10 if event.state & 1 else 1))
            self.adjust_quantity(action,direction=1 if event.delta>0 else -1,steps=steps)
            return 'break'
        if event.delta:
            if self.screen == 'surface':
                self.dispatch(('surface_step',-1 if event.delta > 0 else 1))
            elif self.screen == 'production':
                self.production_view.step(self.session.state, -1 if event.delta > 0 else 1)
                self.render_original()
            else:
                self.scroll_messages(-3 if event.delta > 0 else 3)

    def dispatch(self, action, mouse=1):
        if getattr(self,'bridge_cinema',None) is not None and self.bridge_cinema.running and action != 24:return
        if getattr(self,'research_cinema',None) is not None and self.research_cinema.running and action != 24:return
        if self.cockpit_cinema.running and action!=24:return
        if self.screen=='disk' and isinstance(action,tuple) and action[0]=='disk_audio':
            if self.disk_cinema.running:return
            from .disk_screen import select_audio
            audio=self.session.audio;effects=2 if self.session.effects is None or self.session.effects['enabled'] else 1
            main,mode=select_audio(action[1]+20,audio['main'],effects)
            if action[1] in (1,2,3):
                if main!=audio['main'] or not audio['automatic'] or audio['paused']:
                    old_main=audio['main']
                    self.music_panel.select_main(main,follow_game=True)
                    if old_main!=main:self.disk_cinema.start(old_main,main)
            elif mode!=effects:self.effects.set_enabled(mode==2);self.sound.set(mode==2)
            self.render_original();return
        if self.startup is not None:
            if isinstance(action,tuple):self.startup.dispatch(self,action)
            return
        if self.screen=='adviser':self.adviser_view.dispatch(action);return
        if self.screen=='bar' and action!='time':self.bar_view.dispatch(action);return
        if self.screen=='dialog':self.dialog_view.dispatch(action);return
        if self.screen=='scene':
            if action==65:self.scene_view.acknowledge()
            return
        if self.screen=='ground':
            if isinstance(action,tuple) and action[0]=='ground_order':
                self.ground_view.command('context_cancel' if mouse==3 else action[1]);return
            if action in (72,65):self.ground_view.dispatch(action);return
        if self.screen=='ground_setup':
            if isinstance(action,tuple) and action[0] in ('ground_quantity','ground_remove'):
                operation='remove' if action[0]=='ground_remove' else 'increase' if mouse==1 else 'decrease'
                self.act('ground_edit',operation=operation,selection=action[1])
                return
            if action in ADD_ACTIONS:
                self.act('ground_edit',operation='add',selection=ADD_ACTIONS[action])
                return
            if action==11:
                self.act('ground_start');self.show_ground_battle()
                return
            if action==42:
                destination=self.session.state['ground_encounter']['destination'][:]
                self.act('ground_cancel')
                if not self.space_view.active and not self.session.state['ground_encounter'] and not (
                        self.session.state['presentation_requests'] or self.session.state['active_dialog'] or self.session.state['active_scene']):
                    self.map_view=MapView(system=destination[0],planet=destination[1])
                    self.show_original('starmap')
                return
        if self.screen=='space' and action in (62,65):
            self.space_view.dispatch(action)
            return
        if action == 'page':
            self.menu_page = 1-self.menu_page
            self.caption = ''
            self.render_original()
        elif action == 'time':
            self.toggle_time(mouse == 3)
        elif isinstance(action, tuple):
            if action[0].startswith('fleet_') and self.screen in ('fleets','new_fleet'):
                self.fleet_action(action,mouse)
            elif action[0].startswith('equipment_') and self.screen=='equipment':
                self.equipment_action(action,mouse)
            elif action[0]=='cargo_transfer' and self.screen=='cargo':
                self.cargo_context.require(self.session)
                args=self.cargo_view.transfer(self.session.state,self.catalog,*action[1:],mouse)
                if args:self.act('transfer_cargo',**args)
                self.pointer.cancel(reset=True)
                self.render_original()
            elif action[0].startswith('cockpit_') and self.screen=='cockpit':
                self.cockpit_action(action[0])
            elif action[0]=='colony_option' and self.screen=='colonize':
                self.colony_context.require(self.session)
                self.colony_view.toggle(self.session.state,self.catalog,action[1])
                self.pointer.cancel(reset=True)
                self.render_original()
            elif action[0].startswith('surface_'):
                self.surface_action(action,mouse)
            elif action[0] == 'list_world':
                if any(row[0] == action[1] for row in self.world_list_rows):
                    self.planet_id = action[1]
                    self.planet_landscape = False
                    if mouse == 3:
                        self.dispatch(('planet_orbit',))
                    else:
                        self.show_original('planet')
            elif action[0] == 'orbital_select':
                self.orbital_context.require(self.session)
                if any(e and e['key'] == action[1] for e in self.orbital_entries):
                    self.orbital_selected = action[1]
                    self.render_original()
            elif action[0] == 'orbital_toggle':
                self.act('orbit', fleet_index=self.selected_orbital_fleet())
            elif action[0] == 'orbital_route':
                self.begin_map_route()
            elif action[0] == 'route_system':
                self.commit_map_route([self.map_view.system,0,0])
            elif action[0] == 'map_system':
                if action[1] in system_choices(self.session.state):
                    self.map_view = MapView(system=action[1])
                    self.render_original()
            elif action[0] == 'map_world':
                definition = next(w for w in self.catalog['worlds'] if w['id'] == action[1])
                if world_visible(self.session.state, definition):
                    if self.route_fleet is not None and mouse != 3:
                        self.commit_map_route([definition[k] for k in ('system','planet','moon')])
                        return
                    if self.route_fleet is not None and definition['moon']:
                        return  # Right-click only zooms primary planets during routing.
                    self.planet_id = action[1]
                    self.planet_landscape = False
                    if mouse == 3 and not definition['moon']:
                        self.map_view.planet = definition['planet']
                        self.map_view.ticks = 0
                        self.show_original('starmap')
                    else:
                        self.show_original('planet')
            elif action[0] == 'planet_orbit':
                definition = next(w for w in self.catalog['worlds'] if w['id'] == self.planet_id)
                self.map_view = MapView(system=definition['system'], planet=definition['planet'])
                self.show_original('starmap')
            elif action[0] == 'planet_landscape':
                if self.session.state['worlds'][self.planet_id]['raw'][12] > 5:
                    self.planet_landscape = not self.planet_landscape
                    self.render_original()
            elif action[0] == 'planet_race' and self.screen=='planet':
                definition=next(w for w in self.catalog['worlds'] if w['id']==self.planet_id)
                if world_visible(self.session.state,definition) and revealed_race(self.session.state['worlds'][self.planet_id]['raw']) is not None:
                    self.race_view=RaceView(self.session,self.planet_id)
                    self.pointer.cancel(reset=True);self.caption='';self.render_original()
            elif action[0] in ('race_back','race_forces') and self.screen=='planet' and self.race_view is not None:
                if self.race_view.current(self.session,self.planet_id):
                    if action[0]=='race_forces':
                        self.race_view.details=self.race_view.forces(self.session.state) is not None
                    elif self.race_view.details:self.race_view.details=False
                    else:self.race_view=None
                else:self.race_view=None
                self.pointer.cancel(reset=True);self.caption='';self.render_original()
            elif action[0] == 'product_picture':
                self.production_view.picture = not self.production_view.picture
                self.render_original()
            elif action[0] == 'product_step':
                self.production_view.step(self.session.state, action[1])
                self.render_original()
            elif action[0] == 'product_select':
                self.production_view.selected = action[1]
                self.model_angle = 0
                self.render_original()
            elif action[0] == 'candidate':
                self.commander_rank = action[1]
                self.render_original()
            elif action[0] == 'consult':
                self.adviser_view.open(action[1])
            elif action[0] == 'research':
                self.research_cinema.select(action[1])
        elif action == 24:
            self.show_original()
        elif action == 14:
            self.commander_rank = None
            self.show_original('commanders')
        elif action in (50, 51, 52, 53):
            self.commander_role = action-50
            self.commander_rank = None
            self.caption = ''
            self.render_original()
        elif action == 40:
            if self.commander_rank is not None:
                self.act('hire', role=ROLES[self.commander_role], rank=self.commander_rank)
        elif action == 1:
            self.show_original('disk')
        elif action == 47:
            self.disk_slots.load() if self.screen=='disk' else self.load()
        elif action == 48:
            self.disk_slots.save() if self.screen=='disk' else self.save()
        elif action == 73:
            self.close()
        elif action == 2:
            self.show_original('research')
        elif action == 23:
            self.production_view.selected = self.research_selected if self.screen == 'research' else self.production_view.selected
            self.show_original('production')
        elif self.screen == 'production' and action in (18, 21, 22, 26, 27, 28, 29, 30, 31, 32, 35):
            self.production_action(action)
        elif action == 34:
            self.map_view.planet = 0
            self.show_original('starmap')
        elif action == 33 and self.screen == 'starmap':
            self.map_view.planet = 0
            self.show_original('starmap')
        elif action == 46 and self.screen == 'planet':
            definition = next(w for w in self.catalog['worlds'] if w['id'] == self.planet_id)
            self.map_view = MapView(system=definition['system'], planet=definition['planet'])
            self.show_original('starmap')
        elif action in (38, 39) and self.screen == 'planet':
            raw = self.session.state['worlds'][self.planet_id]['raw']
            self.act('set_tax', world_id=self.planet_id, level=max(0, min(7, raw[18]+(1 if action == 38 else -1))))
        elif action == 74:
            self.world_list_view = WorldListView()
            self.show_original('world_list')
        elif action in (75,76,77) and self.screen == 'world_list':
            self.world_list_view = WorldListView(mode=action-74)
            self.pointer.cancel(reset=True)
            self.caption = ''
            self.render_original()
        elif action in DEPLOY_ACTIONS and self.screen in ('planet','cockpit'):
            wid=self.cockpit_view.world_id(self.session.state) if self.screen=='cockpit' else self.planet_id
            if self.screen=='cockpit':self.selected_cockpit_fleet()
            if action not in deployment_buttons(self.session.state,self.catalog,wid):
                raise GameError('This deployment is no longer available. Reopen planet information.')
            args={'fleet_index':self.cockpit_view.index} if self.screen=='cockpit' and action!=70 else {}
            self.act(DEPLOY_ACTIONS[action],world_id=wid,**args)
        elif action==5 and self.screen in ('planet','cockpit'):
            if self.screen=='cockpit':self.selected_cockpit_fleet();self.planet_id=self.cockpit_view.world_id(self.session.state)
            self.open_colony(self.planet_id)
        elif action==58 and self.screen=='colonize':
            self.show_original('planet')
        elif action==59 and self.screen=='colonize':
            self.colony_context.require(self.session)
            self.act('colonize',world_id=self.colony_view.world_id,options=sorted(self.colony_view.options))
            self.show_original('planet')
        elif action == 41:
            selected = (':'.join(map(str,self.selected_cockpit_fleet()[19:22])) if self.screen=='cockpit' else
                        ':'.join(map(str,self.selected_equipment_fleet()[19:22])) if self.screen=='equipment' else
                        ':'.join(map(str,self.selected_overview_fleet()[19:22])) if self.screen=='fleets' else
                        self.mining_world if self.screen == 'mining' else self.planet_id if self.screen == 'planet' else '1:5:0')
            self.open_surface(selected)
        elif action == 8 and self.screen == 'planet':
            self.open_mining(self.planet_id)
        elif action == 25 and self.screen == 'mining':
            self.mining_context.require(self.session)
            self.act('assign_droid',world_id=self.mining_world)
        elif action == 9 and self.screen == 'surface':
            self.planet_id = self.surface_view.world_id
            self.planet_landscape = False
            self.show_original('planet')
        elif action == 46 and self.screen == 'surface':
            self.planet_id = self.surface_view.world_id
            self.dispatch(('planet_orbit',))
        elif action == 43 and self.screen == 'surface':
            self.surface_context.require(self.session)
            self.open_fleets()
        elif action == 16 and self.screen == 'surface':
            self.surface_context.require(self.session)
            if self.surface_return is not None:
                context,index=self.surface_return
                if context.current(self.session) and 0<=index<len(self.session.state['fleets']['moving']):
                    self.open_cockpit(index)
        elif action == 66 and self.screen == 'surface':
            self.surface_context.require(self.session)
            wid=self.surface_view.world_id
            if 66 not in surface_buttons(self.session.state,wid):return
            self.open_equipment('local',local_group(self.session.state,wid),world_id=wid)
        elif action==46 and self.screen in ('equipment','cockpit'):
            row=self.selected_cockpit_fleet() if self.screen=='cockpit' else self.selected_equipment_fleet()
            if self.screen=='cockpit':
                self.orbital_context=FleetContext(self.session)
                self.orbital_selected=('player',self.cockpit_view.index)
                entries=orbital_entries(self.session.state,self.catalog,row[19],row[20])
                self.orbital_page=next((i//18 for i,e in enumerate(entries) if e and e['key']==self.orbital_selected),0)
            self.planet_id=':'.join(map(str,row[19:22]))
            self.dispatch(('planet_orbit',))
        elif action==37 and self.screen=='equipment':
            self.selected_equipment_fleet()
            bank,index=self.equipment_view.bank,self.equipment_view.index
            self.act('disband_fleet',bank=bank,fleet_index=index)
            self.open_fleets(bank)
        elif action == 13:
            self.route_fleet = None
            if self.screen == 'starmap':self.open_fleets('moving',self.selected_orbital_fleet())
            elif self.screen=='equipment':self.open_fleets(self.equipment_view.bank,self.equipment_view.index)
            elif self.screen=='cargo':
                self.selected_cargo_fleet();self.open_fleets('moving',self.cargo_view.index)
            elif self.screen=='cockpit':
                self.selected_cockpit_fleet();self.open_fleets('moving',self.cockpit_view.index)
            else:self.open_fleets()
        elif action==49 and self.screen in ('fleets','cargo','cockpit'):
            if self.screen=='cockpit':
                self.selected_cockpit_fleet();self.open_equipment('moving',self.cockpit_view.index)
            elif self.screen=='cargo':
                self.selected_cargo_fleet();self.open_equipment('moving',self.cargo_view.index)
            else:
                self.selected_overview_fleet()
                self.open_equipment(self.fleet_view.bank,self.fleet_view.selected[self.fleet_view.bank])
        elif action==15 and self.screen=='fleets':
            kinds=available_types(self.session.state)
            if not kinds:raise GameError('Research and story progression must unlock a fleet type, with room for a new group.')
            self.clock_panel.clock.pause()
            self.new_fleet_view=NewFleetView(kinds[0],self.catalog['fleet_rules'][kinds[0]-1]['default_name'])
            self.show_original('new_fleet')
        elif action==58 and self.screen=='new_fleet':self.show_original('fleets')
        elif action==60 and self.screen=='new_fleet':
            self.fleet_context.require(self.session)
            draft=self.new_fleet_view
            index=len(self.session.state['fleets']['moving'])
            self.act('create_fleet',fleet_type=draft.kind,name=draft.name)
            self.open_fleets('moving',index)
        elif action==3 and self.screen in ('fleets','equipment','cockpit'):
            if self.screen=='cockpit':
                self.selected_cockpit_fleet();index=self.cockpit_view.index
            elif self.screen=='equipment':
                self.selected_equipment_fleet();index=self.equipment_view.index
            else:self.selected_overview_fleet();index=self.fleet_view.selected[self.fleet_view.bank]
            self.open_cargo(index)
        elif action==16 and self.screen in ('fleets','equipment','cargo'):
            source=self.screen
            if self.screen=='cargo':
                row=self.selected_cargo_fleet();bank='moving';index=self.cargo_view.index
            elif self.screen=='equipment':
                row=self.selected_equipment_fleet();bank=self.equipment_view.bank;index=self.equipment_view.index
            else:
                row=self.selected_overview_fleet();bank=self.fleet_view.bank;index=self.fleet_view.selected[bank]
            if bank!='moving':raise GameError('Local forces do not have a cockpit.')
            self.open_cockpit(index,navigation_sound='CPANEL' if source in ('fleets','equipment') else None)
        elif action == 56 and self.screen == 'starmap':
            self.begin_map_route()
        elif action == 57 and self.screen == 'starmap':
            returning=self.route_return
            self.route_fleet = None
            self.route_return=None
            if returning is not None:self.open_cockpit(returning)
            else:self.render_original()
        elif action == 7 and self.screen == 'starmap':
            self.open_cargo(self.selected_orbital_fleet())
        elif action in (55,71) and self.screen == 'starmap':
            self.begin_map_attack(action)
        elif action == 45:
            if self.session.state['campaign']['bar'] is None:raise GameError('This save lacks bar records.')
            self.show_original('bar')
        elif action == 4:
            self.message_offset = 0
            self.show_original('messages')
        elif action == 6:
            self.credits_view.open()

    def open_fleets(self,bank=None,index=None,*,navigation_sound=None):
        self.fleet_context.require(self.session)
        if bank is not None:self.fleet_view.bank=bank
        if index is not None:self.fleet_view.select(self.session.state,index)
        if navigation_sound is not None:self.navigation_sound.start(navigation_sound,'fleets')
        self.show_original('fleets')

    def selected_overview_fleet(self):
        self.fleet_context.require(self.session)
        row=self.fleet_view.row(self.session.state)
        if row is None:raise GameError('Select a group first.')
        return row

    def fleet_action(self,action,mouse):
        self.fleet_context.require(self.session)
        if action[0]=='fleet_bank':
            self.fleet_view.bank='local' if self.fleet_view.bank=='moving' else 'moving'
        elif action[0]=='fleet_select':
            self.fleet_view.select(self.session.state,action[1])
            if mouse==3:
                self.open_equipment(self.fleet_view.bank,action[1])
                return
        elif action[0]=='fleet_type':self.new_fleet_view.cycle(self.session.state,self.catalog,-1 if mouse==3 else 1)
        elif action[0]=='fleet_name':
            draft=self.new_fleet_view;context=self.fleet_context
            def commit(value):
                context.require(self.session)
                if not value:raise GameError('Enter a fleet name.')
                draft.name=value
            self.begin_name_entry(draft.name,commit,135,94)
        self.pointer.cancel(reset=True)
        self.render_original()

    def open_cargo(self,index):
        view=CargoView(index);view.row(self.session.state)
        self.cargo_view=view
        self.cargo_context=FleetContext(self.session)
        self.cargo_signature=None
        self.show_original('cargo')

    def open_cockpit(self,index,*,navigation_sound=None):
        view=CockpitView(index);view.row(self.session.state)
        self.cockpit_view=view
        self.cockpit_context=FleetContext(self.session)
        self.cockpit_signature=None
        self.show_original('cockpit',navigation_sound=navigation_sound)

    def selected_cockpit_fleet(self):
        self.cockpit_context.require(self.session)
        return self.cockpit_view.row(self.session.state)

    def cockpit_action(self,action):
        row=self.selected_cockpit_fleet();index=self.cockpit_view.index
        if action=='cockpit_surface' and row[22] in (1,2):self.open_surface(self.cockpit_view.world_id(self.session.state))
        elif action=='cockpit_orbit' and row[22] in (1,2):
            landing=row[22]==2;prepared=self.cockpit_cinema.prepare(landing)
            self.act('orbit',fleet_index=index,defer_presentation=True)
            callback=self.show_presentation if self.session.state['presentation_requests'] else None
            self.cockpit_cinema.start(index,landing,prepared,callback)
        elif action=='cockpit_cargo':self.open_cargo(index)
        elif action=='cockpit_fleets':self.open_fleets('moving',index,navigation_sound='BASEEFF')
        elif action=='cockpit_equipment':self.open_equipment('moving',index,navigation_sound='GROUP')
        elif action=='cockpit_move' and row[22] in (2,4,5,6):
            from .navigation import ship_count
            if not ship_count(row,self.catalog):raise GameError('Equip the fleet with ships first.')
            if not self.session.state['levels']['pilot'] and row[0]!=4:raise GameError('Hire a pilot before traveling.')
            context=FleetContext(self.session)
            def opened():
                context.require(self.session)
                current=self.selected_cockpit_fleet()
                if self.cockpit_view.index!=index or current[22] not in (2,4,5,6):
                    raise GameError('The selected fleet changed. Reopen navigation.')
                self.orbital_context=FleetContext(self.session)
                self.map_view=MapView(system=current[19],planet=current[20])
                self.route_fleet=index;self.route_return=index
                self.show_original('starmap')
            self.cockpit_cinema.start_route(index,opened)

    def selected_cargo_fleet(self):
        self.cargo_context.require(self.session)
        return self.cargo_view.row(self.session.state)

    def open_equipment(self,bank,index,*,world_id=None,navigation_sound=None):
        view=EquipmentView(bank,index,world_id=world_id)
        view.row(self.session.state)
        self.equipment_view=view
        self.equipment_context=FleetContext(self.session)
        self.equipment_signature=None
        if navigation_sound is not None:self.navigation_sound.start(navigation_sound,'equipment')
        self.show_original('equipment')

    def selected_equipment_fleet(self):
        self.equipment_context.require(self.session)
        return self.equipment_view.row(self.session.state)

    def equipment_action(self,action,mouse,*,maximum=False,steps=1,bounded=False):
        self.equipment_context.require(self.session)
        view=self.equipment_view
        view.row(self.session.state)
        view.notice=''
        if action[0]=='equipment_transfer':
            try:
                self.act('equip_fleet',bank=view.bank,fleet_index=view.index,
                         category=view.category_rule(self.session.state,self.catalog)['id'],
                         hull=action[1],component=action[2],quantity=-steps if mouse==3 else steps,
                         **({"maximum":True} if maximum else {"bounded":True} if bounded else {}))
            except EquipmentTransferLimit as exc:
                view.notice=exc.notice
                self.status.set(str(exc))
        elif action[0]=='equipment_step':view.step(self.session.state,action[1])
        elif action[0]=='equipment_category':
            view.category=max(0,min(len(view.rule(self.session.state,self.catalog)['categories'])-1,view.category+action[1]))
        elif action[0]=='equipment_rename':
            self.begin_equipment_name()
        self.pointer.cancel(reset=True)
        self.render_original()

    def cancel_equipment_name(self):
        self.name_editor_submit=None
        if self.equipment_editor is not None:
            self.original.delete(self.equipment_editor_item)
            self.equipment_editor.destroy()
            self.equipment_editor=None
            self.equipment_editor_item=None

    def begin_equipment_name(self):
        context=self.equipment_context
        view=self.equipment_view
        bank,index=view.bank,view.index
        def commit(value):
            context.require(self.session)
            self.act('rename_fleet',bank=bank,fleet_index=index,name=value)
        self.begin_name_entry(fleet_name(view.row(self.session.state)),commit,24,56)

    def begin_name_entry(self,value,commit,x,y):
        self.cancel_equipment_name()
        self.clock_panel.clock.pause()
        self.name_editor_position=(x,y)
        entry=tk.Entry(self.original,background='black',foreground='#c6c6c6',insertbackground='white',
                       borderwidth=0,highlightthickness=0,exportselection=False)
        self.equipment_editor=entry
        self.equipment_editor_item=self.original.create_window(0,0,anchor='nw',window=entry)
        entry.insert(0,value)
        entry.selection_range(0,'end')
        entry.configure(validate='key',validatecommand=(entry.register(
            lambda value:len(value)<=17 and all(32<=ord(c)<127 for c in value)),'%P'))
        def submit():
            commit(entry.get())
            self.cancel_equipment_name()
            self.original.focus_set()
            self.render_original()
        self.name_editor_submit=submit
        def key(event):
            if event.keysym=='Return':self.guard(submit)
            else:
                self.cancel_equipment_name()
                self.original.focus_set()
                self.render_original()
            return 'break'
        entry.bind('<Return>',key)
        entry.bind('<Escape>',key)
        entry.focus_set()

    def open_colony(self,world_id):
        definition=next(w for w in self.catalog['worlds'] if w['id']==world_id)
        if not world_visible(self.session.state,definition) or not settlement_offered(self.session.state,self.catalog,world_id):
            raise GameError('Colonization needs Control Centre research and a suitable surveyed world.')
        rank=self.session.state['ranks']['builder']
        if not (rank==3 or rank==2 and definition['system']<=2):
            raise GameError('Hire a rank 2 builder for systems 1 and 2, or rank 3 elsewhere.')
        self.clock_panel.clock.pause()
        self.planet_id=world_id
        self.planet_landscape=False
        self.colony_view=ColonyView(world_id)
        self.colony_context=WorldContext(self.session,definition)
        self.colony_signature=None
        self.show_original('colonize')

    def open_mining(self,world_id):
        definition=next(w for w in self.catalog['worlds'] if w['id']==world_id)
        if not world_visible(self.session.state,definition) or not mining_available(self.session.state,world_id):
            raise GameError('Select an owned colony or mining outpost.')
        self.mining_world=world_id
        self.mining_context=WorldContext(self.session,definition)
        self.mining_signature=None
        self.show_original('mining')

    def open_surface(self, world_id):
        returning=(FleetContext(self.session),self.cockpit_view.index) if self.screen=='cockpit' else None
        definition = next(w for w in self.catalog['worlds'] if w['id'] == world_id)
        if not world_visible(self.session.state,definition):
            raise GameError('This world has not been discovered.')
        self.act('prepare_surface',world_id=world_id)
        self.surface_return=returning
        self.surface_context = WorldContext(self.session,definition)
        self.surface_view = SurfaceView(world_id=world_id)
        terrain = self.surface_view.sync(self.session.state,self.catalog)
        centre = next((r for r in self.session.state['buildings'] if r[0] == 1 and r[1:4] == list(map(int,world_id.split(':')))),None)
        self.surface_view.x = centre[4]-6 if centre else (terrain['width']-14)//2
        self.surface_view.y = centre[5]-3 if centre else (terrain['height']-9)//2
        self.surface_signature = None
        self.show_original('surface')

    def surface_pan(self, dx, dy):
        self.surface_view.x += dx
        self.surface_view.y += dy
        self.surface_view.tile = None
        self.pointer.cancel(reset=True)
        self.render_original()

    def surface_radar(self,event):
        if self.surface_context is None:return
        terrain = self.surface_view.sync(self.session.state,self.catalog)
        rx,ry,scale = self.surface_view.radar(terrain)
        x = (event.x-self.origin[0])//self.scale
        y = (event.y-self.origin[1])//self.scale
        self.surface_view.x = (x-rx)//scale-7
        self.surface_view.y = (y-ry)//scale-4
        self.render_original()

    def surface_action(self,action,mouse):
        if self.surface_context is None:raise GameError('Reopen the colony surface.')
        self.surface_context.require(self.session)
        view = self.surface_view
        raw=self.session.state['worlds'][view.world_id]['raw']
        if not surface_revealed(raw):return
        if action[0] in ('surface_step','surface_mode','surface_info') and not surface_editable(self.catalog,raw):return
        if action[0]=='surface_tile' and raw[0]!=1:return
        if action[0] == 'surface_step':
            view.step(self.session.state,self.catalog,action[1])
        elif action[0] == 'surface_close_info':
            view.mode,view.inspected,view.inspected_identity='inspect',None,None
        elif action[0] == 'surface_mode':
            if action[1] == 'build' and view.selected in (1,25):
                raise GameError('Command centres and Miner stations use their deployment process.')
            view.mode,view.inspected = action[1],None
            self.clock_panel.clock.pause()
        elif action[0] == 'surface_pan':
            self.surface_pan(*action[1:]);return
        elif action[0] == 'surface_info':
            view.mode,view.inspected = 'info',None
        elif action[0] == 'surface_tile':
            if mouse == 3 or view.mode == 'info':
                view.mode,view.inspected = 'inspect',None
            elif view.mode == 'build':
                self.act('build',world_id=view.world_id,building_id=view.selected,x=action[1],y=action[2])
                view.mode = 'inspect'
            else:
                tile = building_tiles(self.session.state,self.catalog,view.world_id).get(action[1:])
                if tile is not None:
                    index = tile[1]
                    if view.mode == 'demolish':
                        self.act('demolish',world_id=view.world_id,building_index=index)
                        view.mode = 'inspect'
                    else:
                        row=self.session.state['buildings'][index]
                        if row[0] in (4,5,25) and not row[6]:
                            self.open_mining(view.world_id)
                            return
                        view.inspected = index
                        view.inspected_identity=tuple(row[:6])
                        view.selected = self.session.state['buildings'][index][0]
                        view.mode = 'info'
        self.pointer.cancel(reset=True)
        self.caption = ''
        self.render_original()

    def selected_orbital_fleet(self):
        self.orbital_context.require(self.session)
        if not self.orbital_selected or self.orbital_selected[0] != 'player':
            raise GameError('Select one of your fleets first.')
        if not any(e and e['key'] == self.orbital_selected for e in self.orbital_entries):
            raise GameError('This fleet is no longer at the selected planet.')
        return self.orbital_selected[1]

    def begin_map_attack(self, action):
        self.orbital_context.require(self.session)
        if self.route_fleet is not None:raise GameError('Finish choosing the route before attacking.')
        entries = orbital_entries(self.session.state,self.catalog,self.map_view.system,self.map_view.planet)
        arguments = map_attack(self.session.state,self.map_view.planet,entries,self.orbital_selected,action)
        self.act('attack',**arguments)
        self.pointer.cancel(reset=True)
        self.show_space_battle()

    def begin_map_route(self):
        index = self.selected_orbital_fleet()
        if self.session.state['fleets']['moving'][index][22] != 2:
            raise GameError('Launch the fleet into orbit before choosing a route.')
        self.clock_panel.clock.pause()
        self.route_fleet = index
        self.route_return = None
        self.caption = ''
        self.render_original()

    def commit_map_route(self, destination):
        self.orbital_context.require(self.session)
        if self.route_fleet is None:
            raise GameError('Select Move before choosing a destination.')
        returning=self.route_return
        self.act('travel', fleet_index=self.route_fleet, destination=destination)
        self.route_fleet = None
        self.route_return = None
        if returning is not None:
            self.open_cockpit(returning)
            return
        self.orbital_selected = None
        self.map_view = MapView(system=destination[0], planet=destination[1])
        self.caption = ''
        self.render_original()

    def production_action(self, action):
        view, state = self.production_view, self.session.state
        view.limited=False
        view.sync(state)
        if action in (31, 35):
            view.selecting = action == 31
        elif action in (21, 22):
            view.step(state, 1 if action == 21 else -1)
            self.model_angle = 0
        elif action == 32:
            view.quantity = None
        elif view.selected is not None:
            definition, row = self.catalog['products'][view.selected-1], state['products'][view.selected-1]
            if action == 18:
                if not can_buy(state, definition):
                    raise GameError('This technology is used through colony or fleet controls.')
                self.clock_panel.clock.pause()
                view.quantity = row['queued']
            elif action == 30 and view.quantity is not None:
                self.act('order', product_id=view.selected, quantity=view.quantity)
                view.quantity = None
            elif action in (26, 27, 28, 29) and view.quantity is not None:
                proposed = view.quantity+{26:1, 27:-1, 28:10, 29:-10}[action]
                limit=order_limit(state,definition,row)
                view.limited=action in (26,28) and proposed>limit
                view.quantity = min(limit, max(0, proposed))
        self.caption = ''
        self.render_original()


    def open_startup(self):
        self.navigation_sound.cancel()
        self.cockpit_cinema.cancel()
        self.disk_cinema.cancel()
        from .startup_screen import StartupView
        if getattr(self,'credits_view',None) is not None:self.credits_view.leave();self.credits_bar.pack_forget()
        if getattr(self,'intro_view',None) is not None:self.intro_view.leave();self.intro_bar.pack_forget()
        self.pause_battles();self.stop_model_timer();self.cancel_equipment_name()
        self.pointer.cancel(reset=True);self.surface_drag=False
        self.startup=StartupView(self.session);self.screen='startup';self.menu_page=0
        self.workbench.pack_forget()
        for bar in (self.space_bar,self.ground_setup_bar,self.ground_bar,self.scene_bar,self.dialog_bar,self.bar_controls,self.adviser_bar,self.defeat_bar,self.victory_bar):bar.pack_forget()
        self.clock_bar.pack(side='bottom',fill='x');self.original.pack(fill='both',expand=True)
        self.original.focus_set();self.render_original()


def play(installation, save=None):
    root = tk.Tk()
    app=OriginalApp(root, installation, save)
    if save is None:app.open_startup()
    root.mainloop()
