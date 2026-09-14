"""Desktop controls for saved ground encounters; gameplay stays in the session."""
import struct
import tkinter as tk
from tkinter import ttk, messagebox
from ..core import GameError
from .ground_battle import ground_group
from .ground_pixels import GroundPixels
from .ground_presentation import ground_render_plan
from .battle_samples import GROUND_SAMPLES
from .control_layouts import result_control_enabled


class GroundWindow:
    def __init__(self, app):
        self.app = app;self.session = app.session;self.timer = None;self.running = False
        self.pixels = None;self.terrain = None;self.scale = 2;self.origin = (0, 0)
        self.photo = None;self.zoomed = None;self.last_phase = None
        self.result_pixels=None;self.result_photo=None;self.result_zoomed=None
        self.combat_ppm=None
        self.window = tk.Toplevel(app.root);self.window.title("Ground battle")
        self.window.geometry("1040x760");self.window.minsize(780, 620)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        outer = ttk.Frame(self.window, padding=12);outer.pack(fill="both", expand=True)
        self.heading = tk.StringVar();ttk.Label(outer, textvariable=self.heading, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.status = tk.StringVar();ttk.Label(outer, textvariable=self.status, wraplength=740).pack(anchor="w", pady=6)
        from .control_ui import ControlPanelView
        self.control_panel=ControlPanelView(outer,app.content,app.guard);self.control_panel.pack(fill='x',pady=(0,6))
        self.setup = ttk.Frame(outer)
        banks = ttk.Frame(self.setup);banks.pack(fill="both", expand=True)
        self.groups = {}
        for side, label in (("friendly", "Your deployed groups"), ("hostile", "Enemy groups")):
            holder = ttk.LabelFrame(banks, text=label, padding=6);holder.pack(side="left", fill="both", expand=True, padx=4)
            self.groups[side] = app.tree(holder, ("Group", "Type", "Troops"), (55, 140, 70), height=13)
        self.reserves = tk.StringVar();ttk.Label(self.setup, textvariable=self.reserves, wraplength=740).pack(anchor="w", pady=8)
        controls = ttk.Frame(self.setup);controls.pack(fill="x", pady=6)
        self.troop = tk.StringVar();self.type_choice = ttk.Combobox(controls, textvariable=self.troop, state="readonly", width=13)
        self.type_choice.pack(side="left", padx=3)
        self.button(controls, "Add group", self.add_group)
        for title, operation in (("+1 troop", "increase"), ("-1 troop", "decrease"), ("Remove group", "remove")):
            self.button(controls, title, lambda op=operation:self.edit(op))
        self.button(controls, "Start battle", self.start)
        self.cancel_button=self.button(controls,'Cancel assault',lambda:app.act('ground_cancel'))
        self.combat = ttk.Frame(outer)
        self.canvas = tk.Canvas(self.combat, background="#101114", highlightthickness=0, width=640, height=302)
        self.canvas.pack(fill="both", expand=True)
        self.canvas_image = self.canvas.create_image(0, 0, anchor="nw")
        self.canvas.bind("<Configure>", lambda _:self.draw())
        self.canvas.bind("<Button-1>", lambda event:app.guard(lambda:self.click(event)))
        self.canvas.bind("<Button-3>", lambda _:app.guard(lambda:self.command("context_cancel")))
        self.selection = tk.StringVar();ttk.Label(self.combat, textvariable=self.selection, wraplength=740).pack(anchor="w", pady=6)
        bar = ttk.Frame(self.combat);bar.pack(fill="x")
        self.order_buttons = {}
        for title, command in (("Move (M)", "move"), ("Attack (A)", "attack"), ("Cancel order", "cancel"), ("Retreat", "retreat")):
            self.order_buttons[command] = self.button(bar, title, lambda action=command:self.command(action))
        self.run_button = self.button(bar, "Run", self.toggle)
        self.step_button = self.button(bar, "Step", self.step)
        self.speed = tk.StringVar(value="20")
        ttk.Label(bar, text="Frames/sec").pack(side="left", padx=(12, 3))
        ttk.Combobox(bar, textvariable=self.speed, values=("5", "10", "20", "40"), width=4, state="readonly").pack(side="left")
        self.result = ttk.Frame(outer)
        self.result_canvas=tk.Canvas(self.result,background='#101114',highlightthickness=0,width=640,height=302)
        self.result_canvas.pack(fill='both',expand=True);self.result_image=self.result_canvas.create_image(0,0,anchor='nw')
        self.result_canvas.bind('<Configure>',lambda _:app.guard(self.draw_result))
        self.losses = tk.StringVar();ttk.Label(self.result, textvariable=self.losses, wraplength=740, justify="left").pack(anchor="w", pady=6)
        result_controls=ttk.Frame(self.result);result_controls.pack(fill='x')
        self.acknowledge_button = self.button(result_controls, "Continue campaign", self.acknowledge)
        self.result_play_button=self.button(result_controls,'Play animation',lambda:self.result_playback.toggle())
        from .result_playback import ResultPlayback
        self.result_playback=ResultPlayback(self)
        from .result_fade import ResultFade
        self.fade=ResultFade(self,'ground')
        footer = ttk.Frame(outer);footer.pack(side="bottom", fill="x", pady=(10, 0))
        self.button(footer, "Save session", app.save);self.button(footer, "Load session", app.load)
        self.button(footer, "Close battle window", self.close)
        self.window.bind("<KeyPress-m>", lambda _:app.guard(lambda:self.command("move")))
        self.window.bind("<KeyPress-a>", lambda _:app.guard(lambda:self.command("attack")))
        self.window.bind("<Escape>", lambda _:app.guard(lambda:self.command("context_cancel")))
        self.window.bind("<Destroy>", self.destroyed, add="+")
        app.watch_session(self.window, self.refresh)
        try:self.refresh()
        except (GameError, ValueError, OSError, tk.TclError):
            self.window.destroy();raise

    def button(self, parent, text, callback):
        button = ttk.Button(parent, text=text, command=lambda:self.app.guard(callback))
        button.pack(side="left", padx=3);return button

    def encounter(self):
        return self.app.session.state["ground_encounter"]

    def owns_effect(self):
        return self.session is self.app.session and (self.app.session.effects or {}).get('sample') in GROUND_SAMPLES

    def pause(self,*,audio=True,result=True,fade=True):
        self.running = False
        if self.timer is not None:
            self.window.after_cancel(self.timer);self.timer = None
        self.run_button.configure(text="Run")
        self.status.set(self.status.get().replace(" Battle running.", " Battle paused."))
        if audio and self.owns_effect():self.app.effects.pause()
        if result:self.result_playback.pause()
        if fade:self.fade.finish()

    def close(self):
        self.pause();self.window.destroy()

    def destroyed(self, event):
        if event.widget==self.window:
            self.fade.cancel()
            self.result_playback.pause()
            if self.timer is not None:
                self.app.root.after_cancel(self.timer);self.timer = None
            self.running = False
            if self.owns_effect():self.app.effects.suspend()
            if self.app.ground_window is self:self.app.ground_window = None

    def refresh(self):
        if self.session is not self.app.session:
            self.pause();self.session = self.app.session;self.pixels = None
        encounter = self.encounter()
        if encounter is None:
            self.close();return
        phase = encounter["phase"]
        self.cancel_button.configure(state='normal' if phase=='setup' and encounter['player_attacking'] else 'disabled')
        self.control_panel.show(19 if phase=='setup' else 32 if phase=='fighting' else 30,
            {11:self.start} if phase=='setup' else {72:lambda:self.command('retreat')} if phase=='fighting'
            else {65:self.acknowledge} if phase=='result' else {})
        self.fade.sync()
        if phase!="fighting":self.pause(audio=False,result=False,fade=False)
        world_id = ":".join(map(str, encounter["destination"]))
        name = next(w["name"] for w in self.app.catalog["worlds"] if w["id"]==world_id)
        self.heading.set(f"{'Attacking' if encounter['player_attacking'] else 'Defending'} {name}")
        if "ground_presentation" not in self.app.catalog:
            raise GameError("Ground artwork tables are missing; re-extract the local content bundle.")
        self.names = self.app.catalog["ground_presentation"]["names"]
        self.type_choice.configure(values=self.names[:4])
        if self.troop.get() not in self.names[:4]:self.troop.set(self.names[0])
        if phase!=self.last_phase:
            self.setup.pack_forget();self.combat.pack_forget();self.result.pack_forget()
            {"setup": self.setup, "fighting": self.combat, "result": self.result, "closed": self.result}[phase].pack(fill="both", expand=True)
        battle = encounter["battle"]
        if phase=="setup":
            self.status.set("Arrange your troops, then start the battle. Troops in reserve remain outside the battle.")
            for side in ("friendly", "hostile"):
                tree = self.groups[side];selection = tree.selection();tree.delete(*tree.get_children())
                for index, row in enumerate(battle[side+"_groups"], 1):
                    tree.insert("", "end", iid=str(index), values=(index, self.names[row[0]-1], struct.unpack("<h", bytes(row[1:3]))[0]))
                if selection and tree.exists(selection[0]):tree.selection_set(selection[0])
            self.reserves.set("Your reserve: "+", ".join(f"{self.names[i]} {qty:,}" for i, qty in enumerate(battle["friendly_reserve"]))
                +"\nEnemy reserve: "+", ".join(f"{self.names[i]} {qty:,}" for i, qty in enumerate(battle["hostile_reserve"])))
        elif phase=="fighting":
            self.status.set({1:"Select a group to move or attack. Right-click cancels targeting.",
                2:"Battle paused. Cancel order resumes selection.", 3:"Click a destination for the selected group.",
                4:"Click an enemy target."}[battle["control_mode"]]+(" Battle running." if self.running else " Battle paused."))
            side = "friendly" if battle["selected_friendly"] else "hostile"
            selected = ground_group(battle, side, battle["selected_group"])
            can_order = selected is not None and side=="friendly" and selected[0]<5 and struct.unpack("<h", bytes(selected[1:3]))[0]>0
            for command in ("move", "attack"):self.order_buttons[command].configure(state="normal" if can_order else "disabled")
            if selected is None:self.selection.set("No group selected.")
            elif selected[0]==5:
                label = "Colony" if encounter["player_attacking"]!=(side=="friendly") else self.names[4]
                self.selection.set(f"{'Your' if side=='friendly' else 'Enemy'} {label}: {'intact' if selected[1] else 'destroyed'}. This structure has no active ground weapon.")
            else:
                kind = selected[0]-1;quantity = struct.unpack("<h", bytes(selected[1:3]))[0]
                total = battle[side+"_totals"][kind]
                primary = quantity*battle[side+"_primary"][kind]//total if total else 0
                text = f"{'Your' if side=='friendly' else 'Enemy'} group {battle['selected_group']}: {self.names[kind]}, {quantity} troops. Primary power {primary}."
                if kind==3:
                    secondary = quantity*battle[side+"_secondary"][kind]//total if total else 0
                    text += f" Missile power {secondary}."
                self.selection.set(text)
            self.draw()
        else:
            self.status.set("Victory" if battle["player_won"] else "Retreated" if battle["retreated"] else "Defeat")
            rows = ["Troop losses:"]
            for side, label in (("friendly", "Your forces"), ("hostile", "Enemy forces")):
                rows.append(label+": "+", ".join(f"{self.names[i]} {qty:,}" for i, qty in enumerate(encounter["losses"][side])))
            if phase=="closed":rows.append("Campaign outcome applied.")
            self.losses.set("\n\n".join(rows))
            self.acknowledge_button.configure(state="normal" if result_control_enabled(self.app.catalog,phase) and not self.fade.active else "disabled")
            self.draw_result()
        self.last_phase = phase
        self.result_playback.sync()

    def draw_result(self):
        encounter=self.encounter()
        if encounter is None or encounter['phase'] not in ('result','closed') or not self.result_canvas.winfo_exists():return
        if self.result_pixels is None:
            from .battle_results import BattleResultPictures
            self.result_pixels=BattleResultPictures(self.app.content)
        value=self.app.session.result_animation
        picture=self.result_pixels.picture('ground',encounter['battle']['player_won'],encounter['losses'],frame=value['shown'] if value else 1,fade_step=self.fade.palette_step())
        self.result_photo=tk.PhotoImage(master=self.window,data=self.fade.picture_data(picture.ppm()),format='PPM')
        scale=max(1,min(4,self.result_canvas.winfo_width()//320,self.result_canvas.winfo_height()//151))
        self.result_zoomed=self.result_photo.zoom(scale)
        self.result_canvas.coords(self.result_image,(self.result_canvas.winfo_width()-320*scale)//2,(self.result_canvas.winfo_height()-151*scale)//2)
        self.result_canvas.itemconfigure(self.result_image,image=self.result_zoomed)

    def draw(self):
        encounter = self.encounter()
        if encounter is None or encounter["phase"]!="fighting" or not self.canvas.winfo_exists():return
        world = self.app.session.state["worlds"][":".join(map(str, encounter["destination"]))]["raw"]
        if self.pixels is None or self.terrain!=world[21]:
            self.pixels = GroundPixels(self.app.content, world[21]);self.terrain = world[21]
        rules = self.app.catalog["battle_rules"]
        calls = ground_render_plan(encounter["battle"], rules["ground_motion"], self.app.catalog["ground_presentation"], rules["ground_controls"])
        self.combat_ppm=self.pixels.ppm(calls)
        self.photo = tk.PhotoImage(master=self.window, data=self.combat_ppm, format="PPM")
        self.scale = max(1, min(4, self.canvas.winfo_width()//320, self.canvas.winfo_height()//151))
        self.zoomed = self.photo.zoom(self.scale)
        self.origin = ((self.canvas.winfo_width()-320*self.scale)//2, (self.canvas.winfo_height()-151*self.scale)//2)
        self.canvas.coords(self.canvas_image, *self.origin);self.canvas.itemconfigure(self.canvas_image, image=self.zoomed)

    def add_group(self):
        self.app.act("ground_edit", operation="add", selection=self.names.index(self.troop.get())+1)

    def edit(self, operation):
        self.app.act("ground_edit", operation=operation, selection=self.app.selected_id(self.groups["friendly"]))

    def start(self):
        self.app.act("ground_start")

    def click(self, event):
        x = (event.x-self.origin[0])//self.scale;y = (event.y-self.origin[1])//self.scale
        if 64<=x<320 and 0<=y<151:self.command("click", x=x, y=y+49)
        elif 0<=x<64 and 0<=y<151:
            self.command("move" if 119<=y<135 else "attack" if y>=135 else "cancel")

    def command(self, command, **args):
        if (self.encounter() or {}).get("phase")!="fighting":return
        if command in ("move", "attack") and self.order_buttons[command].instate(["disabled"]):return
        self.app.act("ground_command", command=command, **args)

    def step(self):
        self.pause();self.app.act("ground_tick")

    def toggle(self):
        if self.running:self.pause();self.refresh();return
        if (self.encounter() or {}).get("phase")!="fighting":return
        self.running = True;self.run_button.configure(text="Pause");self.refresh();self.schedule()
        if self.owns_effect():self.app.effects.resume()

    def schedule(self):
        if self.running and self.timer is None:self.timer = self.window.after(max(1, 1000//int(self.speed.get())), self.frame)

    def frame(self):
        self.timer = None
        if not self.running:return
        if self.control_panel.busy:self.schedule();return
        try:
            self.app.session.apply("ground_tick");self.app.effects.sync();self.refresh()
            if (self.encounter() or {}).get("phase")=="result":self.app.refresh()
        except (GameError, ValueError, OSError, tk.TclError) as exc:
            self.pause();self.app.status.set(str(exc))
            messagebox.showerror("Ground battle paused", str(exc), parent=self.window)
        self.schedule()

    def acknowledge(self):
        if self.fade.active:return
        self.pause();self.app.act("ground_acknowledge")
