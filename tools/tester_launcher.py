"""Portable Windows test-build entry point and packaged-runtime verification."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from unittest.mock import patch


def main():
    base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    if not getattr(sys, 'frozen', False):sys.path.insert(0, str(base/'src'))
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--content-dir', type=Path, help='Explicit content location for verification')
    parser.add_argument('--import-from', type=Path, help='Import a supplied original game folder')
    parser.add_argument('--import-only', action='store_true', help='Convert files without launching or playing audio')
    args = parser.parse_args()
    if args.import_only and not args.import_from:
        parser.error('--import-only requires --import-from')
    content_dir = args.content_dir or base/'local/recovered'
    log_path = base/'logs/launch.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    mute_guard = None
    with log_path.open('a', encoding='utf-8') as log:
        if sys.stdout is None:sys.stdout = log
        if sys.stderr is None:sys.stderr = log
        try:
            if args.import_from:
                from openreunion.dos.asset_import import import_assets
                import_assets(args.import_from, content_dir)
                if args.import_only:return
            if not (content_dir/'catalog.json').is_file():
                if args.self_test:
                    raise ValueError('Self-test requires an imported content directory.')
                from openreunion.dos.import_ui import choose_and_import
                if not choose_and_import(content_dir):return
            if args.self_test:
                # Frozen self-tests are child processes, so run_quiet.py cannot
                # mute them. Establish and confirm this process's own session
                # before importing or creating the graphical application.
                from openreunion.testing_audio import mute_current_process
                mute_guard = mute_current_process()
                print(f'Windows self-test audio muted before playback (PID {os.getpid()}); audio engine remains enabled.', flush=True)
            import tkinter as tk
            from openreunion import __version__
            from openreunion.dos.original_ui import OriginalApp
            from openreunion.dos.session import RecoveredSession
            root = tk.Tk()
            if args.self_test:root.withdraw()
            app = OriginalApp(root, content_dir)
            app.save_dir = base/'saves'
            if not args.self_test:
                app.open_startup()
                root.mainloop()
                return
            errors = []
            root.report_callback_exception = lambda *details: errors.append(str(details))
            with tempfile.TemporaryDirectory() as directory:
                app.save_dir = Path(directory)
                root.update()
                fresh = deepcopy(app.session.state)
                assert fresh['date'] == [2927, 8, 13, 23]
                assert fresh['resources']['credits'] == 120000
                assert not (base/'local/recovered/sessions').exists()
                # The frozen candidate must exercise the connected intro
                # controller itself, while the native mute guard is alive.
                # This is deliberately a short live check; full-film playback
                # belongs to the separate graphical smoke.
                intro_before = deepcopy(app.session.state)
                root.deiconify();root.update()
                app.open_startup()
                assert app.screen == 'startup' and app.startup.stage == 'menu'
                app.dispatch(('startup','intro'));root.update()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    root.update()
                    if app.intro_view.music.error:
                        raise AssertionError(app.intro_view.music.error)
                    if app.intro_view.running and app.intro_view.music.playing and app.intro_view.position > 0:
                        break
                    time.sleep(.005)
                else:
                    raise AssertionError('Frozen intro did not start live audio/first transition.')
                first_sample = app.intro_view.music.position()
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and app.intro_view.music.position() <= first_sample:
                    root.update();time.sleep(.005)
                assert app.intro_view.music.position() > first_sample
                app.original.focus_force();root.update()
                assert root.focus_get() is app.original
                app.original.event_generate('<KeyPress-space>');root.update()
                assert not app.intro_view.running
                paused_sample = app.intro_view.music.position()
                deadline = time.monotonic() + .15
                while time.monotonic() < deadline:
                    root.update();time.sleep(.005)
                assert app.intro_view.music.position() == paused_sample
                app.original.event_generate('<KeyPress-space>');root.update()
                assert app.intro_view.running
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and app.intro_view.music.position() <= paused_sample:
                    root.update();time.sleep(.005)
                assert app.intro_view.music.position() > paused_sample
                app.intro_view.pause()
                representative = next((index for index,shot in enumerate(app.intro_view.entries)
                    if shot.high_resolution and shot.level == shot.divisor and not shot.white), None)
                assert representative is not None
                app.intro_view.position = representative;app.intro_view.reset_render();app.render_original()
                payload = app.frame_pixels.split(b'\n',3)[3]
                assert app.frame_pixels.startswith(b'P6\n640 480\n255\n') and any(payload)
                back = next(button for button in app.intro_bar.winfo_children()
                            if button.cget('text').startswith('Back'))
                back.invoke();root.update()
                assert app.screen == 'startup' and not app.intro_view.active
                assert not app.intro_view.music.playing and app.intro_view.timer is None
                assert app.session.state == intro_before
                root.withdraw();root.update()
                app.act('advance', hours=24)
                progressed = deepcopy(app.session.state)
                assert progressed['date'] == [2927, 8, 14, 23]
                path = app.save_dir/'first-day.json'
                app.session.save(path)
                assert RecoveredSession.load(app.catalog, path).state == progressed
                app.new_game()
                root.update()
                assert app.session.state == fresh
                assert RecoveredSession.load(app.catalog, app.save_dir/'recovered-before-new-game.json').state == progressed
                # Frozen startup follows the same menu dispatch as normal launch.
                # Exercise both identities and their saved portrait selection.
                for hero in (1,2):
                    app.open_startup()
                    assert app.screen=='startup' and app.startup.stage=='menu'
                    app.dispatch(('startup','new'))
                    assert app.startup.stage=='choose'
                    app.dispatch(('hero',hero))
                    assert app.startup.stage=='portrait'
                    app.dispatch(('startup','start'));root.update()
                    assert app.screen=='bridge' and app.hero==hero and app.session.state==fresh
                    app.session.save(path)
                    assert RecoveredSession.load(app.catalog,path).hero==hero
                # Exercise converted graphics and the separately replaceable FM DLL.
                picture = app.content.pictures()[0]
                png, width, height = app.content.picture(picture)
                assert png.startswith(b'\x89PNG') and width and height
                from openreunion.dos.fm_audio import OplSynth
                synth = OplSynth()
                synth.close()
                from openreunion.dos.module_audio import ModuleRenderer
                from openreunion.dos.module_music import MODULE_NAMES
                for name in MODULE_NAMES:app.content.module_music(name)
                for name in ('FAILURE','ENDSEQ','STEAL2'):
                    with ModuleRenderer(app.content.module_music(name),repeat=False) as renderer:
                        pcm=renderer.render(48000)
                        assert len(pcm)==192000 and any(pcm)
                for asset,step in ((15,1),(15,8),(16,1),(16,61)):
                    assert len(app.content.defeat_animation(asset,step).pixels)==64000
                for frame in range(1,17):assert len(app.content.victory_animation(frame).pixels)==64000
                credits_state=deepcopy(app.session.state)
                app.dispatch(1);app.dispatch(6);app.credits_view.pause()
                assert app.screen=='credits' and app.credits_view.active
                for picture in ('PRESENTS','HIGHRES','REUNION','PAL10'):
                    app.credits_view.position=next(i for i,shot in enumerate(app.credits_view.frames)
                        if shot.picture==picture and shot.level==shot.divisor)
                    app.render_original()
                    dimensions=b'640 480' if picture=='HIGHRES' else b'320 200'
                    assert app.frame_pixels.startswith(b'P6\n'+dimensions+b'\n255\n')
                app.escape_original()
                assert app.screen=='bridge' and not app.credits_view.active and not app.credits_view.music.playing
                assert app.session.state==credits_state and not app.clock_panel.clock.running
                root.deiconify();root.update()
                app.dispatch(1)
                from openreunion.dos.disk_screen import BUTTONS
                for button in (2,3,4,4,1):
                    x,y,w,h=BUTTONS[button-1];ox,oy=app.origin
                    for event in ('Press','Release'):
                        app.original.event_generate('<Button'+event+'-1>',x=ox+(x+w//2)*app.scale,y=oy+(y+h//2)*app.scale)
                        root.update()
                    if button in (1,2,3):assert app.session.audio['main']=={1:1,2:2,3:0}[button],(button,app.screen,app.session.audio['main'])
                    deadline=time.monotonic()+6
                    while app.disk_cinema.running and time.monotonic()<deadline:
                        root.update();time.sleep(.01)
                    assert not app.disk_cinema.running, 'Disk animation did not finish'
                assert app.session.audio['automatic'] and app.session.effects['enabled']
                assert app.session.state==credits_state and not app.workbench.winfo_ismapped()
                from openreunion.dos.disk_slots import slot_path
                for slot in range(1,13):
                    ox,oy=app.origin
                    for event in ('Press','Release'):
                        app.original.event_generate('<Button'+event+'-1>',x=ox+40*app.scale,y=oy+(68+9*(slot-1))*app.scale)
                        root.update()
                    assert app.disk_slots.selected==slot
                app.dispatch(48)
                saved_slot=slot_path(app.save_dir,12)
                assert app.screen=='bridge' and saved_slot.exists()
                saved_bytes=saved_slot.read_bytes()
                app.dispatch(1)
                with patch('openreunion.dos.disk_slots.messagebox.askyesno',return_value=False) as confirm:
                    app.dispatch(48)
                assert confirm.called and saved_slot.read_bytes()==saved_bytes and app.screen=='disk'
                app.dispatch(24);app.act('advance',hours=1)
                assert app.session.state!=credits_state
                app.dispatch(1);app.dispatch(47);root.update()
                assert app.session.state==credits_state and app.screen=='bridge'
                assert not app.clock_panel.clock.running and not app.disk_cinema.running
                app.dispatch(1)
                named=app.save_dir/'Named disk save.json'
                with patch('openreunion.dos.ui.filedialog.asksaveasfilename',return_value=str(named)):
                    app.clock_bar.save_file.invoke()
                with patch('openreunion.dos.ui.filedialog.askopenfilename',return_value=str(named)):
                    app.clock_bar.load_file.invoke()
                root.update()
                assert app.session.state==credits_state and app.screen=='disk'
                app.dispatch(24)
                root.withdraw();root.update()
                app.dispatch(14)
                app.dispatch(53)
                app.dispatch(('candidate', 1))
                app.dispatch(40)
                assert app.session.state['ranks']['developer'] == 1
                app.dispatch(2)
                app.dispatch(('research', 2))
                assert app.session.state['products'][1]['research_state'] == 4
                assert app.clock_bar.research_pause.cget('text')=='Pause research'
                app.clock_bar.research_pause.invoke()
                remaining=app.session.state['products'][1]['research_remaining']
                app.act('advance',hours=1)
                assert app.session.state['research_paused'] and app.session.state['products'][1]['research_remaining']==remaining
                app.session.save(path);app.load_path(path)
                assert app.clock_bar.research_pause.cget('text')=='Resume research'
                app.clock_bar.research_pause.invoke();app.act('advance',hours=1)
                assert not app.session.state['research_paused'] and app.session.state['products'][1]['research_remaining']<remaining
                assert app.frame_pixels.startswith(b'P6\n320 200\n255\n')
                app.dispatch(23)
                assert app.screen == 'production' and app.production_view.selected == 1
                app.dispatch(('product_picture',))
                assert not app.production_view.picture
                for pid in range(1, 36):
                    app.content.product_model_data(pid)
                app.dispatch(34)
                assert app.screen == 'starmap' and len(app.map_bodies) == 3
                app.dispatch(('map_world', '1:5:0'))
                assert app.screen == 'planet' and app.planet_id == '1:5:0'
                tax = app.session.state['worlds']['1:5:0']['raw'][18]
                app.dispatch(38)
                assert app.session.state['worlds']['1:5:0']['raw'][18] == min(7, tax+1)
                app.dispatch(('planet_orbit',))
                assert app.screen == 'starmap' and app.map_view.planet == 5
                app.dispatch(('map_world', '1:5:1'))
                assert app.screen == 'planet' and app.planet_id == '1:5:1'
                # Assisted fixture tests the packaged orbital route independently
                # of campaign progression; normal New game remains unchanged.
                fixture = deepcopy(fresh)
                fixture['campaign']['capabilities'].update(transport=1, carrier=1)
                fixture['products'][3].update(stock=1, research_state=5, research_remaining=0)
                app.session = RecoveredSession(app.catalog, fixture)
                app.act('create_fleet', fleet_type=4, name='Runtime check')
                app.act('equip_fleet', fleet_index=0, category=4, hull=1)
                app.dispatch(34)
                app.dispatch(('map_world', '1:5:0'), 3)
                assert app.orbital_entries[0]['key'] == ('player',0)
                app.dispatch(('orbital_select',('player',0)))
                app.dispatch(('orbital_toggle',))
                assert app.session.state['fleets']['moving'][0][22] == 2
                app.dispatch(('orbital_route',))
                app.dispatch(('map_world','1:5:1'))
                assert app.session.state['fleets']['moving'][0][19:22] == [1,5,1]
                assert app.route_fleet is None and app.orbital_selected is None
                app.session = RecoveredSession(app.catalog,deepcopy(fresh))
                app.refresh()
                app.dispatch(74)
                assert app.screen == 'world_list'
                assert [r[0] for r in app.world_list_rows] == ['1:5:0']
                app.dispatch(76)
                assert not app.world_list_rows and app.world_list_view.mode == 2
                app.dispatch(77)
                assert not app.world_list_rows and app.world_list_view.mode == 3
                app.dispatch(75)
                app.dispatch(('list_world','1:5:0'))
                assert app.screen == 'planet' and app.planet_id == '1:5:0'
                app.dispatch(41)
                assert app.screen == 'surface'
                app.act('hire',role='builder',rank=1)
                from openreunion.dos.surface import occupancy,placement_fits
                raw=app.session.state['worlds']['1:5:0']['raw']
                width,height,blocked=occupancy(app.catalog,raw,app.session.state['buildings'],[1,5,0])
                definition=app.catalog['buildings'][3]
                x,y=next((x,y) for y in range(1,height) for x in range(1,width)
                         if placement_fits(definition,x,y,width,height,blocked))
                app.surface_view.selected=4
                app.surface_view.x,app.surface_view.y=x-1,y-1
                app.dispatch(('surface_mode','build'))
                app.dispatch(('surface_tile',x,y))
                assert app.session.state['buildings'][-1][:6]==[4,1,5,0,x,y]
                for _ in range(500):
                    app.session.apply('advance',hours=1)
                    if not app.session.state['buildings'][-1][6]:break
                else:raise AssertionError('Packaged mine did not complete')
                app.refresh()
                app.dispatch(('surface_tile',x,y))
                assert app.screen=='mining'
                app.dispatch(25)
                from openreunion.dos.mining_screen import mining_report
                report=mining_report(app.session.state,'1:5:0')
                assert (report['active'],report['stored'],report['mines'])==(3,0,3)
                app.session.save(path)
                assert RecoveredSession.load(app.catalog,path).state==app.session.state
                assert not app.session.state['assisted']
                # Labeled synthetic fixtures check new colony assets, dispatch
                # and deliveries in the frozen runtime; earned replay is separate.
                fixture=deepcopy(fresh)
                fixture['resources']['credits']=500000
                fixture['ranks']['builder']=2;fixture['levels']['builder']=60
                for product in fixture['products']:product.update(research_state=5,research_remaining=0)
                fixture['worlds']['1:5:1']['raw'][12]=30
                app.session=RecoveredSession(app.catalog,fixture);app.refresh()
                app.dispatch(('map_world','1:5:1'));app.dispatch(5)
                assert app.screen=='colonize'
                for kind in app.catalog['settlement_options']:app.dispatch(('colony_option',kind))
                cost=app.colony_view.cost(app.catalog);app.dispatch(59)
                assert app.screen=='planet' and app.session.state['resources']['credits']==500000-cost
                for _ in range(160):app.session.apply('advance',hours=1)
                kinds={r[0] for r in app.session.state['buildings'] if r[1:4]==[1,5,1]}
                assert set(app.catalog['settlement_options'])|{1}<=kinds
                fixture=deepcopy(fresh)
                carrier=[0]*161;carrier[0]=4;carrier[19:23]=[1,5,0,2];carrier[37]=1
                fixture['fleets']['moving']=[carrier]
                app.session=RecoveredSession(app.catalog,fixture);app.refresh()
                app.dispatch(('map_world','1:5:0'));app.dispatch('page')
                assert app.menu_page==1 and app.action(7)[1]==69
                app.dispatch(69)
                assert app.session.state['worlds']['1:5:0']['raw'][11]==1 and app.menu_page==0
                # Explicit equipment fixture: original assets, every fleet
                # category, real transfer commands and inline editor creation.
                from openreunion.dos.equipment import new_fleet
                fixture=deepcopy(fresh)
                for product in fixture['products']:product.update(research_state=5,research_remaining=0,stock=20)
                fixture['fleets']['moving']=[new_fleet(kind,f'Preview {kind}') for kind in range(1,5)]
                app.session=RecoveredSession(app.catalog,fixture);app.refresh()
                for index,rule in enumerate(app.catalog['fleet_rules'][:4]):
                    app.open_equipment('moving',index)
                    for ci,cat in enumerate(rule['categories']):
                        if ci:app.dispatch(('equipment_category',1))
                        app.dispatch(('equipment_transfer',1,0))
                        assert app.session.state['fleets']['moving'][index][29+40*(cat['bank']-1)]==1
                        assert app.screen=='equipment' and app.frame_pixels.startswith(b'P6\n320 200\n')
                app.dispatch(('equipment_transfer',1,1))
                assert app.session.state['fleets']['moving'][3][31]==1
                before_limit=deepcopy(app.session.state)
                app.original.focus_force();root.update();focus_before=root.focus_get()
                with patch('openreunion.dos.ui.messagebox.showerror') as transfer_popup:
                    for event in ('Press','Release'):
                        ox,oy=app.origin
                        app.original.event_generate('<Button'+event+'-1>',x=ox+159*app.scale,y=oy+112*app.scale)
                        root.update()
                    assert not transfer_popup.called
                assert app.equipment_view.notice=='Equipment bay full'
                assert app.session.state==before_limit and root.focus_get() is focus_before
                assert root.grab_current() is None
                # Native maximum/wheel events in the frozen executable.
                def bulk_click(x,shift=False,button=2):
                    for event in ('Press','Release'):
                        ox,oy=app.origin
                        app.original.event_generate('<Button'+event+'-'+str(button)+'>',
                            x=ox+x*app.scale,y=oy+112*app.scale,state=1 if shift else 0)
                        root.update()
                bulk_click(116)
                assert app.session.state['fleets']['moving'][3][29]==20
                bulk_click(159)
                assert app.session.state['fleets']['moving'][3][31]==20
                ox,oy=app.origin
                app.original.event_generate('<MouseWheel>',x=ox+159*app.scale,y=oy+112*app.scale,delta=-120,state=1)
                root.update()
                assert app.session.state['fleets']['moving'][3][31]==10
                bulk_click(159,True)
                assert app.session.state['fleets']['moving'][3][31]==0
                bulk_click(159,button=1,shift=True)
                assert app.session.state['fleets']['moving'][3][31]==20
                bulk_click(159,button=3,shift=True)
                assert app.session.state['fleets']['moving'][3][31]==0
                app.dispatch(('equipment_rename',))
                assert app.equipment_view.notice==''
                assert app.equipment_editor is not None and 'fleet name' in app.clock_edit_reason()
                app.cancel_equipment_name()
                app.session.state['campaign']['capabilities'].update(transport=1,hunter=1,transfer=1,pirate=1,carrier=1)
                app.open_fleets('moving',3)
                assert app.screen=='fleets' and app.fleet_view.selected['moving']==3
                app.dispatch(15)
                assert app.screen=='new_fleet' and not app.clock_panel.clock.running
                def fleet_click(x,y):
                    ox,oy=app.origin
                    for event in ('Press','Release'):
                        app.original.event_generate('<Button'+event+'-1>',x=ox+x*app.scale,y=oy+y*app.scale)
                        root.update()
                fleet_click(160,97)
                entry=app.equipment_editor;assert entry is not None
                entry.delete(0,'end');entry.insert(0,'Preview trade')
                fleet_click(165,120)
                assert app.equipment_editor is None and app.new_fleet_view.kind==2
                assert app.new_fleet_view.name=='Preview trade'
                app.dispatch(60)
                assert app.screen=='fleets' and app.fleet_view.selected['moving']==4
                assert app.session.state['fleets']['moving'][4][0]==2
                app.dispatch(49)
                assert app.screen=='equipment' and app.equipment_view.index==4
                assert app.equipment_view.buttons(app.session.state)==[24,13,16,3,46,41,37]
                app.dispatch('page');assert app.menu_page==1 and app.action(7)[1]==37
                app.dispatch(37)
                assert app.screen=='fleets' and len(app.session.state['fleets']['moving'])==4
                # Explicit cargo fixture, through the connected original screen.
                # Let normal hourly allocation populate New Earth's storage.
                app.act('advance',hours=1)
                app.session.state['resources']['detoxin']=351
                app.open_fleets('moving',1);app.dispatch(3)
                assert app.screen=='cargo' and app.cargo_view.index==1
                assert len(app.cargo_view.report(app.session.state,app.catalog)['lines'])==16
                app.dispatch(('cargo_transfer','ore','detoxin',True))
                assert app.cargo_view.report(app.session.state,app.catalog)['used']==100
                app.dispatch(('cargo_transfer','ore','detoxin',True),3)
                assert app.cargo_view.report(app.session.state,app.catalog)['used']==351
                app.dispatch(('cargo_transfer','ore','detoxin',False),3)
                assert app.session.state['resources']['detoxin']==351
                app.dispatch(('cargo_transfer','slot',13,True),3)
                assert app.cargo_view.report(app.session.state,app.catalog)['used']==500
                app.dispatch(('cargo_transfer','slot',13,False))
                assert app.cargo_view.report(app.session.state,app.catalog)['used']==0
                app.dispatch(16)
                assert app.screen=='cockpit' and app.cockpit_view.index==1
                app.session.state['ranks']['pilot']=1;app.session.state['levels']['pilot']=10
                app.dispatch(('cockpit_orbit',))
                assert app.cockpit_cinema.running
                transition_state=deepcopy(app.session.state)
                app.dispatch(('cockpit_orbit',));assert app.session.state==transition_state
                deadline=time.monotonic()+6
                while app.cockpit_cinema.running and time.monotonic()<deadline:
                    root.update();time.sleep(.01)
                assert not app.cockpit_cinema.running and app.session.state==transition_state
                assert app.session.state['fleets']['moving'][1][22]==2
                def cockpit_move():
                    before=deepcopy(app.session.state)
                    app.dispatch(('cockpit_move',));assert app.cockpit_cinema.running
                    deadline=time.monotonic()+5
                    while app.cockpit_cinema.running and time.monotonic()<deadline:
                        root.update();time.sleep(.005)
                    assert not app.cockpit_cinema.running and app.session.state==before
                cockpit_move()
                assert app.screen=='starmap' and app.route_return==1
                deadline=time.monotonic()+5
                while app.cockpit_cinema.audio_timer is not None and time.monotonic()<deadline:
                    root.update();time.sleep(.01)
                assert app.cockpit_cinema.audio_timer is None and app.cockpit_cinema.player.completed
                app.dispatch(57);assert app.screen=='cockpit'
                cockpit_move();app.commit_map_route([1,5,1])
                assert app.screen=='cockpit' and app.session.state['fleets']['moving'][1][22]==4
                before_animation=deepcopy(app.session.state)
                for _ in range(12):app.cockpit_view.advance(app.session.state)
                app.render_original();assert app.session.state==before_animation
                cockpit_move();app.dispatch(57)
                assert app.screen=='cockpit' and app.session.state==before_animation
                app.dispatch(49);assert app.screen=='equipment' and app.equipment_view.index==1
                app.session.save(path)
                assert RecoveredSession.load(app.catalog,path).state==app.session.state
                # Prepared alien target: original map entry and main-screen
                # space combat, using the same public command as normal play.
                from openreunion.dos.aliens import store_fleet
                civ=app.session.state['campaign']['civilizations'][0]
                civ[27]=4;civ[38]=1
                alien=[0]*27;alien[0]=2;alien[2]=1;alien[8:11]=[1,5,0];alien[11]=1
                store_fleet(civ,1,alien)
                app.session.state['levels']['fighter']=20;app.session.state['ranks']['fighter']=2
                app.planet_id='1:5:0';app.dispatch(('planet_orbit',))
                app.dispatch(('orbital_select',('alien',2,0)))
                assert 55 in [app.action(i)[1] for i in range(1,7)]
                root.deiconify();root.update()
                app.dispatch(55)
                root.update()
                assert app.screen=='space' and app.space_window is None and not app.space_view.running
                assert app.catalog['alien_names'][0] in app.space_bar.notice.cget('text')
                assert app.space_bar.notice.winfo_ismapped()
                app.session.save(path)
                resumed=RecoveredSession.load(app.catalog,path)
                app.space_view.step();resumed.apply('space_tick',render=True)
                assert app.session.state==resumed.state
                if app.space_view.encounter()['phase']=='fighting':app.dispatch(62)
                assert app.space_view.encounter()['phase']=='result'
                app.space_view.cancel_fade();app.render_original();app.dispatch(65)
                assert app.screen=='bridge' and not app.space_view.active
                # A saved incoming encounter identifies the attacker without
                # an external dialog; hover and load keep its notice visible.
                incoming=deepcopy(fresh);incoming['assisted']=True
                civ=incoming['campaign']['civilizations'][1];civ[27]=2;civ[38]=1
                alien=[0]*27;alien[0]=2;alien[2]=1;alien[8:11]=[1,5,0];alien[11]=20
                store_fleet(civ,1,alien)
                app.session=RecoveredSession(app.catalog,incoming)
                app.session.begin_space_battle([1,5,0],player_attacking=False,conquering_owner=3)
                app.refresh();root.update()
                notice=app.space_bar.notice.cget('text')
                assert app.catalog['alien_names'][1] in notice and 'New Earth' in notice
                assert not app.space_view.running and app.space_bar.notice.winfo_ismapped()
                app.hover('RETREAT');root.update();assert app.space_bar.notice.cget('text')==notice
                app.session.save(path);app.load_path(path);root.update()
                assert app.space_bar.notice.cget('text')==notice and not app.space_view.running
                root.withdraw();root.update()
                # Prepared ground forces check deployment/cancellation and the
                # main combat/result assets in the frozen runtime. Campaign
                # acceptance is separate; no research-tool dependency ships.
                import struct
                fixture=deepcopy(fresh);fixture['assisted']=True
                row=[0]*161;row[0]=1;row[19:23]=[1,5,1,1]
                row[99:109]=struct.pack('<5h',10,0,0,112,0)
                fixture['fleets']['moving']=[row]
                raw=fixture['worlds']['1:5:1']['raw']
                raw[0:2]=[3,1];raw[3]=raw[6]=raw[21]=1
                raw[27:43]=struct.pack('<4I',4,0,0,0)
                raw[43:59]=struct.pack('<4I',30,0,0,0)
                fixture['campaign']['civilizations'][1][27]=2
                app.session=RecoveredSession(app.catalog,fixture)
                app.session.begin_ground_battle([1,5,1],player_attacking=True,conquering_owner=3)
                app.refresh()
                assert app.screen=='ground_setup' and app.ground_window is None
                expected=RecoveredSession(app.catalog,deepcopy(app.session.state))
                expected.apply('ground_edit',operation='decrease',selection=1)
                app.dispatch(('ground_quantity',1),3)
                assert app.session.state==expected.state
                expected.apply('ground_cancel');app.dispatch(42)
                assert app.session.state==expected.state and app.screen=='starmap'
                app.session.begin_ground_battle([1,5,1],player_attacking=True,conquering_owner=3)
                app.refresh();app.dispatch(11)
                assert app.screen=='ground' and app.ground_window is None
                app.session.save(path);resumed=RecoveredSession.load(app.catalog,path)
                app.ground_view.step();resumed.apply('ground_tick')
                assert app.session.state==resumed.state
                app.session=RecoveredSession.load(app.catalog,path);app.refresh()
                assert app.screen=='ground' and not app.ground_view.running
                from openreunion.dos.ground_geometry import pixel_position
                px,py=pixel_position(app.ground_view.encounter()['battle']['friendly_groups'][0],
                                     app.catalog['battle_rules']['ground_motion'])
                app.ground_view.command('click',x=px+8,y=py+57)
                app.dispatch(('ground_order','move'));app.ground_view.command('click',x=160,y=100)
                assert app.ground_view.encounter()['battle']['friendly_groups'][0][15]==2
                app.dispatch(72)
                assert app.ground_view.phase=='result' and not app.ground_view.won
                app.ground_view.cancel_fade();app.ground_view.stop_result();app.render_original()
                assert app.frame_pixels.startswith(b'P6\n320 200\n255\n')
                for frame in (1,2,3):
                    app.ground_view.result_pixels.picture('ground',False,app.ground_view.encounter()['losses'],frame=frame)
                app.session.save(path);resumed=RecoveredSession.load(app.catalog,path)
                assert app.session.result_animation==resumed.result_animation
                resumed.apply('ground_acknowledge');app.dispatch(65)
                assert app.session.state==resumed.state and app.screen=='scene'
                assert app.session.state['presentation_requests']==[{'kind':'message','id':14}]
                assert app.scene_view.notice
                resumed.apply('dismiss_presentation');app.dispatch(65)
                assert app.session.state==resumed.state and app.screen=='bridge'
                assert app.session.state['date']==fresh['date'] and app.ground_window is None
                app.session=RecoveredSession(app.catalog,deepcopy(fresh))
                app.refresh()
                from check_graphical_clock import check_graphical_clock
                graphical_clock=check_graphical_clock(app)
                # Labeled prepared discovery fixtures: normal landing must
                # deliver its story after the full sample, without Run/Load.
                discovery=deepcopy(fresh);discovery['assisted']=True
                discovery['known_systems'][2]=1
                discovery['campaign']['navigation']['planet_visibility'][17]=1
                ship=new_fleet(2,'Discovery preview');ship[19:23]=[3,2,1,2];ship[29]=1
                discovery['fleets']['moving']=[ship]
                app.session=RecoveredSession(app.catalog,deepcopy(discovery));app.refresh();app.open_cockpit(0)
                app.dispatch(('cockpit_orbit',));assert app.cockpit_cinema.running
                assert app.session.state['active_scene'] is None
                deadline=time.monotonic()+8
                while app.screen!='scene' and time.monotonic()<deadline:root.update();time.sleep(.005)
                assert app.screen=='scene' and app.session.state['active_scene']['notice']==36
                assert app.cockpit_cinema.player.completed and not app.cockpit_cinema.player.playing
                assert app.session.state['date']==fresh['date'] and not app.clock_panel.clock.running
                assert all(app.session.state['products'][p-1]['research_state']==3 for p in (22,23))
                discovery_path=app.save_dir/'discovery-notice.json';app.session.save(discovery_path)
                before=deepcopy(app.session.state);app.load_path(discovery_path);root.update()
                assert app.session.state==before and app.screen=='scene' and not app.scene_view.running
                # Back skips transient playback while still showing the queued story.
                app.session=RecoveredSession(app.catalog,deepcopy(discovery));app.refresh();app.open_cockpit(0)
                app.dispatch(('cockpit_orbit',));assert app.cockpit_cinema.running
                app.dispatch(24);assert app.screen=='scene' and app.session.state['active_scene']['notice']==36
                assert not app.cockpit_cinema.running and app.cockpit_cinema.on_complete is None
                # A survey discovering the same wreck uses the immediate path.
                survey=deepcopy(discovery);carrier=new_fleet(4,'Survey preview')
                carrier[19:23]=[3,2,0,2];carrier[29]=carrier[31]=1
                survey['fleets']['moving']=[carrier];survey['products'][2]['stock']=0
                app.session=RecoveredSession(app.catalog,survey);app.refresh()
                app.dispatch(('map_world','3:2:1'));assert app.screen=='planet'
                app.dispatch(20);assert app.screen=='scene' and app.session.state['active_scene']['notice']==36
                assert app.session.state['fleets']['moving'][0][31]==0 and app.session.state['date']==fresh['date']
                # New Game navigation must expose a black surface without
                # granting terrain information. Later support is a labeled
                # fixture, not an earned satellite journey.
                app.session=RecoveredSession(app.catalog,deepcopy(fresh));app.refresh()
                app.open_surface('1:2:0');app.render_original()
                def black_surface():
                    rgb=app.frame_pixels.split(b'\n',3)[3]
                    return all(not any(rgb[(y*320+x)*3:(y*320+x+w)*3])
                        for x,top,w,h in ((93,53,224,144),(0,138,89,62),(12,64,77,64))
                        for y in range(top,top+h))
                assert app.screen=='surface' and black_surface() and app.session.state==fresh
                app.session.state['assisted']=True
                raw=app.session.state['worlds']['1:2:0']['raw']
                raw[0]=2;raw[6]=raw[9]=raw[10]=0;raw[8]=226;raw[21:23]=[1,0]
                app.open_surface('1:2:0');app.render_original();assert black_surface()
                raw=app.session.state['worlds']['1:2:0']['raw']
                raw[8]=2;app.open_surface('1:2:0');app.render_original()
                assert not black_surface() and not app.surface_view.editable
                raw=app.session.state['worlds']['1:2:0']['raw']
                raw[8]=0;app.refresh();assert black_surface()
                raw[9]=1;app.refresh();assert not black_surface()
                for hero in (1,2):
                    defeat_fixture=deepcopy(fresh);defeat_fixture.update(campaign_phase='defeat',assisted=True)
                    app.session=RecoveredSession(app.catalog,defeat_fixture,hero=hero);app.refresh()
                    assert app.screen=='defeat' and not app.defeat_view.running
                    for picture in (f'DEATH{hero}','DEATH'):
                        app.defeat_view.position=next(i for i,shot in enumerate(app.defeat_view.frames) if shot.picture==picture)
                        app.render_original();assert app.frame_pixels.startswith(b'P6\n320 200\n255\n')
                    app.defeat_view.position=len(app.defeat_view.frames);app.render_original()
                    assert app.session.state==defeat_fixture
                victory_fixture=deepcopy(fresh);victory_fixture.update(campaign_phase='victory',assisted=True)
                app.session=RecoveredSession(app.catalog,victory_fixture);app.refresh()
                assert app.screen=='victory' and not app.victory_view.running
                for picture in ('TX1','RETURN','TX5','CR1'):
                    app.victory_view.position=next(i for i,shot in enumerate(app.victory_view.frames) if shot.picture==picture)
                    app.render_original();assert app.frame_pixels.startswith(b'P6\n320 200\n255\n')
                app.victory_view.position=len(app.victory_view.frames);app.render_original()
                assert app.session.state==victory_fixture
                assert not errors, errors
                windows_test_session_muted = bool(mute_guard is not None and mute_guard.is_muted())
                assert windows_test_session_muted
                app.close()
                result = {'passed': True, 'version': __version__, 'frozen': bool(getattr(sys, 'frozen', False)),
                          'windows_test_session_muted': windows_test_session_muted,
                          'fresh_start': True, 'first_day': True, 'save_load': True,
                          'graphical_intro_runtime': True,
                          'reset_and_backup': True, 'converted_graphics': True,
                          'fm_library': True, 'numbered_saves_in_package': False,
                          'module_library_and_15_tracks':True,'defeat_animation_assets':True,
                          'game_credits_assets_high_resolution_and_navigation':True,
                          'graphical_disk_audio_buttons_and_indicators':True,
                          'graphical_disk_tray_playback_and_twelve_save_slots':True,
                          'graphical_disk_overwrite_cancel_and_named_files':True,
                          'graphical_saved_research_pause_resume_and_progress':True,
                          'startup_both_heroes_and_saved_identity':True,
                          'fresh_black_surface_and_prepared_spy_disclosure':True,
                          'both_hero_defeat_terminal_fixtures':True,
                          'victory_animation_and_terminal_fixture':True,
                          'original_graphical_start': True, 'graphical_hire_and_research': True,
                          'graphical_info_buy': True, 'all_35_models': True,
                          'graphical_map_planet_moon': True, 'graphical_tax': True,
                          'graphical_orbital_route_assisted_fixture': True,
                          'graphical_world_lists': True, 'graphical_surface_construction':True,
                          'graphical_earned_mining_assignment':True,
                          'graphical_live_clock':graphical_clock,
                          'graphical_colony_bundle_fixture':True,'graphical_solar_deployment_fixture':True,
                          'graphical_equipment_all_types_fixture':True,
                          'graphical_fleet_overview_creation_fixture':True,
                          'graphical_name_edit_then_type_click':True,
                          'graphical_equipment_limit_inline_no_popup':True,
                          'graphical_bulk_quantity_mouse_shortcuts':True,
                          'graphical_equipment_menu_disband_fixture':True,
                          'graphical_original_cargo_fixture':True,
                          'graphical_original_cockpit_fixture':True,
                          'graphical_cockpit_launch_animation_and_input_guard':True,
                          'graphical_cockpit_route_lever_handoff_and_sound':True,
                          'graphical_discovery_landing_full_sound_story_and_save_fixture':True,
                          'graphical_discovery_back_handoff_fixture':True,
                          'graphical_survey_discovery_story_handoff_fixture':True,
                          'graphical_map_attack_main_space_fixture':True,
                          'graphical_named_attack_notice_saved_and_paused':True,
                          'graphical_ground_deployment_cancel_fixture':True,
                          'graphical_main_ground_orders_results_fixture':True}
                if not args.output:raise ValueError('--self-test requires --output')
                args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        except Exception:
            traceback.print_exc(file=log)
            log.flush()
            if args.self_test or args.import_only:raise SystemExit(1)
            if not args.self_test:
                try:
                    from tkinter import messagebox
                    messagebox.showerror('Open Reunion could not start', f'Details were written to:\n{log_path}')
                except Exception:pass
            raise
        finally:
            if mute_guard is not None:
                mute_guard.close()


if __name__ == '__main__':
    main()
