"""Desktop space combat; session commands own all numerical and campaign state."""
import tkinter as tk
from tkinter import ttk, messagebox
from ..core import GameError
from .space_pixels import SpacePixels
from .battle_samples import SPACE_SAMPLES
from .control_layouts import result_control_enabled


class SpaceWindow:
    def __init__(self, app):
        self.app = app;self.session = app.session;self.running = False;self.timer = None
        self.pixels = None;self.calls = [];self.last_battle = None
        self.combat_ppm=None
        self.photo = self.zoomed = None;self.scale = 2;self.origin = (0, 0)
        self.window = tk.Toplevel(app.root);self.window.title("Space battle")
        self.window.geometry("1040x700");self.window.minsize(780, 580)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        outer = ttk.Frame(self.window, padding=12);outer.pack(fill="both", expand=True)
        self.heading = tk.StringVar();ttk.Label(outer, textvariable=self.heading, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.status = tk.StringVar();ttk.Label(outer, textvariable=self.status, wraplength=730).pack(anchor="w", pady=6)
        from .control_ui import ControlPanelView
        self.control_panel=ControlPanelView(outer,app.content,app.guard);self.control_panel.pack(fill='x',pady=(0,6))
        self.canvas = tk.Canvas(outer, background="#101114", highlightthickness=0, width=640, height=302)
        self.canvas.pack(fill="both", expand=True);self.canvas_image = self.canvas.create_image(0, 0, anchor="nw")
        self.canvas.bind("<Configure>", lambda _:app.guard(self.draw))
        self.forces = tk.StringVar();ttk.Label(outer, textvariable=self.forces, wraplength=730, justify="left").pack(anchor="w", pady=10)
        controls = ttk.Frame(outer);controls.pack(fill="x", pady=6)
        self.run_button = self.button(controls, "Run", self.toggle)
        self.step_button = self.button(controls, "Step", self.step)
        self.retreat_button = self.button(controls, "Retreat", self.retreat)
        self.acknowledge_button = self.button(controls, "Continue", self.acknowledge)
        self.speed = tk.StringVar(value="20");ttk.Label(controls, text="Frames/sec").pack(side="left", padx=(12, 3))
        ttk.Combobox(controls, textvariable=self.speed, values=("5", "10", "20", "40"), width=4, state="readonly").pack(side="left")
        footer = ttk.Frame(outer);footer.pack(fill="x", pady=(10, 0))
        self.button(footer, "Save session", app.save);self.button(footer, "Load session", app.load)
        self.button(footer, "Close battle window", self.close)
        self.window.bind("<Destroy>", self.destroyed, add="+")
        self.window.bind("<space>", self.keyboard_pause)
        from .result_fade import ResultFade
        self.fade=ResultFade(self,'space')
        app.watch_session(self.window, self.refresh)
        try:self.refresh()
        except (GameError, ValueError, OSError, tk.TclError):
            self.window.destroy();raise

    def button(self, parent, text, callback):
        button = ttk.Button(parent, text=text, command=lambda:self.app.guard(callback))
        button.pack(side="left", padx=3);return button

    def encounter(self):return self.app.session.state["space_encounter"]

    def keyboard_pause(self, event):
        if event.widget.winfo_class() not in ("TCombobox", "TEntry", "TButton"):
            self.app.guard(self.toggle);return "break"

    def owns_effect(self):
        return self.session is self.app.session and (self.app.session.effects or {}).get('sample') in SPACE_SAMPLES

    def pause(self,*,audio=True,fade=True):
        self.running = False
        if self.timer is not None:self.window.after_cancel(self.timer);self.timer = None
        self.run_button.configure(text="Run")
        self.status.set(self.status.get().replace("Battle running.", "Battle paused."))
        if audio and self.owns_effect():self.app.effects.pause()
        if fade:self.fade.finish()

    def close(self):self.pause();self.window.destroy()

    def destroyed(self, event):
        if event.widget == self.window:
            self.fade.cancel()
            if self.timer is not None:self.app.root.after_cancel(self.timer);self.timer = None
            self.running = False
            if self.owns_effect():self.app.effects.suspend()
            if self.app.space_window is self:self.app.space_window = None

    def refresh(self):
        if self.session is not self.app.session:
            self.pause();self.session = self.app.session;self.last_battle = None;self.pixels = None
        encounter = self.encounter()
        if encounter is None:self.close();return
        if "space_presentation" not in self.app.catalog:
            raise GameError("Space artwork tables are missing; re-extract the local content bundle.")
        if self.pixels is None:self.pixels = SpacePixels(self.app.content, self.app.catalog["space_presentation"])
        phase = encounter["phase"];battle = encounter["battle"]
        self.control_panel.show(29 if phase=='fighting' else 30,
            {62:self.retreat} if phase=='fighting' else {65:self.acknowledge} if phase=='result' else {})
        self.fade.sync()
        if phase != "fighting":self.pause(audio=False,fade=False)
        if self.last_battle is not battle:
            self.calls = encounter["radar"]
            self.last_battle = battle
        identity = ":".join(map(str, encounter["destination"]))
        name = next(w["name"] for w in self.app.catalog["worlds"] if w["id"] == identity)
        from .battle_identity import space_notice
        self.heading.set(space_notice(self.app.session.state,self.app.catalog,encounter))
        hulls = next(c["hulls"] for f in self.app.catalog["fleet_rules"] if f["id"] == 1
                     for c in f["categories"] if c["bank"] == 1)
        names = [h["name"] for h in hulls]
        rows = []
        for side, label in (("friendly", "Your forces and allies"), ("hostile", "Enemy forces")):
            counts = [sum(unit["raw"][1] == hull for unit in battle[side][:battle[side+"_count"]]) for hull in range(1, 5)]
            rows.append(label+": "+", ".join(f"{names[i]} {count:,}" for i, count in enumerate(counts)))
            if phase != "fighting":rows.append("Losses: "+", ".join(f"{names[i]} {count:,}" for i, count in enumerate(encounter["losses"][side])))
        self.forces.set("\n".join(rows))
        if phase == "fighting":
            self.status.set("Ships fight automatically. "+("Battle running." if self.running else "Battle paused."))
        else:
            result = "Victory." if encounter["player_won"] else "Retreated." if encounter["retreated"] else "Defeat."
            ground = encounter["ground_requested"] and encounter["player_won"] == encounter["player_attacking"]
            self.status.set(result+(" Outcome applied." if phase == "closed" else " Continue to ground deployment." if ground else " Continue to the campaign."))
        for button in (self.run_button, self.step_button, self.retreat_button):button.configure(state="normal" if phase == "fighting" else "disabled")
        self.acknowledge_button.configure(state="normal" if result_control_enabled(self.app.catalog,phase) and not self.fade.active else "disabled")
        pending=len(self.app.session.state["battle_requests"])
        if pending:self.status.set(self.status.get()+f" Other pending attacks: {pending}.")
        self.draw()

    def draw(self):
        encounter = self.encounter()
        if encounter is None or self.pixels is None or not self.canvas.winfo_exists():return
        result = None if encounter["phase"] == "fighting" else encounter["player_won"]
        cinematic=encounter.get("cinema")
        ppm=self.pixels.ppm(self.calls, result=result,
            losses=encounter['losses'] if result is not None else None,
            cinema=cinematic["view"] if cinematic else None,fade_step=self.fade.palette_step())
        if result is None:self.combat_ppm=ppm
        self.photo = tk.PhotoImage(master=self.window, data=self.fade.picture_data(ppm), format="PPM")
        self.scale = max(1, min(4, self.canvas.winfo_width()//320, self.canvas.winfo_height()//151))
        self.zoomed = self.photo.zoom(self.scale)
        self.origin = ((self.canvas.winfo_width()-320*self.scale)//2, (self.canvas.winfo_height()-151*self.scale)//2)
        self.canvas.coords(self.canvas_image, *self.origin);self.canvas.itemconfigure(self.canvas_image, image=self.zoomed)

    def tick(self):
        events = self.app.session.apply("space_tick", render=True)
        self.app.effects.sync()
        for event in events:
            if event["kind"] == "space_frame":self.calls = event["calls"]
        self.last_battle = self.encounter()["battle"];self.refresh()
        if self.encounter()["phase"] == "result":self.app.refresh()

    def step(self):self.pause();self.tick()

    def toggle(self):
        if self.running:self.pause();self.refresh();return
        if (self.encounter() or {}).get("phase") != "fighting":return
        if self.owns_effect():self.app.effects.resume()
        self.running = True;self.run_button.configure(text="Pause");self.refresh();self.schedule()

    def schedule(self):
        if self.running and self.timer is None:
            self.timer = self.window.after(max(1, 1000//int(self.speed.get())), self.frame)

    def frame(self):
        self.timer = None
        if not self.running:return
        if self.control_panel.busy:self.schedule();return
        try:self.tick()
        except (GameError, ValueError, OSError, tk.TclError) as exc:
            self.pause();self.app.status.set(str(exc))
            messagebox.showerror("Space battle paused", str(exc), parent=self.window)
        self.schedule()

    def retreat(self):self.pause();self.app.act("space_retreat")

    def acknowledge(self):
        if self.fade.active:return
        self.pause();self.app.act("space_acknowledge")
        ground = self.app.session.state["ground_encounter"]
        if ground is not None and ground["phase"] == "setup":self.app.show_ground_battle()
