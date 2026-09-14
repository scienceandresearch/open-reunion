"""Replaceable Tk desktop client. All gameplay mutations go through Engine."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from .core import GameError, ORES, RULES, new_game
from .engine import ADMIN_HELP, Engine
from .legacy import LegacySave, TerrainMap, RESOURCE_OFFSETS, export_legacy
from .persistence import default_save_directory, load_game, save_game
from .systems import power

BG, PANEL, INK, MUTED, ACCENT = "#101b2c", "#18283d", "#e3edf7", "#99aec3", "#67dfb5"


class App:
    def __init__(self, root, engine=None):
        self.root, self.engine = root, engine or Engine()
        self.root.title("Open Reunion | Reconstruction prototype")
        self.root.geometry("1200x860")
        self.root.minsize(1050, 780)
        self.root.configure(bg=BG)
        self.paused = tk.BooleanVar(value=True)
        self.speed = tk.StringVar(value="1")
        self.world = tk.StringVar(value="new_earth")
        self.building = tk.StringVar(value="mine")
        self.selected = (0, 0)
        self.status = tk.StringVar(value="Ready. Select a tile, or start with research.")
        self.admin = tk.BooleanVar(value=self.engine.admin_enabled)
        self.legacy_path = None
        self.timer_id = None
        self.setup_style()
        self.layout()
        self.refresh()
        self.timer_id = root.after(1000, self.timer)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def setup_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG)
        style.configure("TButton", background=PANEL, foreground=INK, padding=(10, 6))
        style.map("TButton", background=[("active", "#2c4863")])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, padding=(18, 10))
        style.map("TNotebook.Tab", background=[("selected", "#28516a")])
        style.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=INK)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", INK)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK, rowheight=30)
        style.configure("Treeview.Heading", background="#25425b", foreground=INK, padding=7)
        style.map("Treeview", background=[("selected", "#286452")])
        style.configure("TEntry", fieldbackground=PANEL, foreground=INK)

    def button(self, parent, label, callback):
        b = ttk.Button(parent, text=label, command=callback)
        b.pack(side="left", padx=(0, 6), pady=4)
        return b

    def combo(self, parent, variable, values, width=18):
        box = ttk.Combobox(parent, textvariable=variable, values=list(values), state="readonly", width=width)
        box.pack(side="left", padx=(0, 8), pady=4)
        return box

    def text(self, parent, height=10):
        widget = ScrolledText(parent, height=height, bg=PANEL, fg=INK, insertbackground=INK,
                              font=("Consolas", 10), relief="flat", padx=12, pady=12, wrap="word")
        widget.pack(fill="both", expand=True, pady=8)
        widget.configure(state="disabled")
        return widget

    @staticmethod
    def replace_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def layout(self):
        shell = ttk.Frame(self.root, padding=20)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x")
        ttk.Label(header, text="OPEN REUNION", font=("Segoe UI", 25, "bold"), foreground=ACCENT).pack(side="left")
        ttk.Label(header, text="RECONSTRUCTION / 0.1", foreground=MUTED).pack(side="right")
        ttk.Label(shell, text="Playable development scenario. Original campaign, combat, graphics and balance are not yet reconstructed.", foreground=MUTED).pack(anchor="w", pady=(2, 12))
        self.headline = ttk.Label(shell, font=("Consolas", 12))
        self.headline.pack(anchor="w", pady=5)
        bar = ttk.Frame(shell)
        bar.pack(fill="x")
        ttk.Checkbutton(bar, text="Paused", variable=self.paused).pack(side="left", padx=(0, 12))
        self.combo(bar, self.speed, ["1", "6", "24"], width=4)
        ttk.Label(bar, text="hours / second").pack(side="left", padx=(0, 12))
        self.button(bar, "+1 hour", lambda: self.action("advance", hours=1))
        self.button(bar, "+24 hours", lambda: self.action("advance", hours=24))
        self.button(bar, "Save", self.save)
        self.button(bar, "Load", self.load)
        self.button(bar, "New scenario", self.reset)
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill="both", expand=True, pady=12)
        self.pages = {}
        for title in ("Colony", "Research & production", "Trade fleets", "Messages", "Legacy tools", "Admin console"):
            page = ttk.Frame(self.tabs, padding=12)
            self.tabs.add(page, text=title)
            self.pages[title] = page
        self.colony_page()
        self.production_page()
        self.fleet_page()
        self.messages = self.text(self.pages["Messages"])
        self.legacy_page()
        self.admin_page()
        ttk.Label(shell, textvariable=self.status, foreground=ACCENT, wraplength=1100).pack(fill="x")

    def colony_page(self):
        page = self.pages["Colony"]
        bar = ttk.Frame(page)
        bar.pack(fill="x")
        box = self.combo(bar, self.world, self.engine.state.planets)
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.button(bar, "Deploy satellite", lambda: self.action("survey", world=self.world.get()))
        self.button(bar, "Colonize · 100,000", lambda: self.action("colonize", world=self.world.get()))
        body = ttk.Frame(page)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(left, width=504, height=504, bg="#142c39", highlightthickness=0)
        self.canvas.pack(anchor="nw", pady=8)
        self.canvas.bind("<Button-1>", self.select_tile)
        right = ttk.Frame(body, padding=(20, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)
        self.world_info = self.text(right, 14)
        self.tile_label = ttk.Label(right, text="Selected tile: 0, 0")
        self.tile_label.pack(anchor="w")
        row = ttk.Frame(right)
        row.pack(fill="x")
        self.combo(row, self.building, [x for x in RULES["buildings"] if x != "command_centre"], 12)
        self.button(row, "Build", lambda: self.action("build", world=self.world.get(), kind=self.building.get(), x=self.selected[0], y=self.selected[1]))
        row = ttk.Frame(right)
        row.pack(fill="x")
        self.button(row, "Demolish selected", lambda: self.action("demolish", world=self.world.get(), x=self.selected[0], y=self.selected[1]))
        self.button(row, "Assign droid", lambda: self.action("assign_droid", world=self.world.get()))
        row = ttk.Frame(right)
        row.pack(fill="x")
        self.tax = tk.StringVar(value="10")
        self.combo(row, self.tax, [str(x) for x in range(0, 31, 5)], 5)
        self.button(row, "Set tax %", lambda: self.action("set_tax", world=self.world.get(), rate=int(self.tax.get())))

    def production_page(self):
        page = self.pages["Research & production"]
        self.products = ttk.Treeview(page, columns=("name", "state", "credits", "ore", "work"), show="headings", height=5, selectmode="browse")
        for col, title, width in (("name", "Product", 160), ("state", "Research", 180), ("credits", "Credits / unit", 120), ("ore", "Ore cost / unit", 250), ("work", "Work / unit", 100)):
            self.products.heading(col, text=title)
            self.products.column(col, width=width)
        self.products.pack(fill="x", pady=8)
        row = ttk.Frame(page)
        row.pack(fill="x")
        self.button(row, "Research selected", lambda: self.product_action("research"))
        self.quantity = tk.StringVar(value="1")
        self.combo(row, self.quantity, ["1", "5", "10", "100"], 5)
        self.button(row, "Produce selected", lambda: self.product_action("produce"))
        ttk.Label(page, text="Production is at New Earth. Orders share 10 work/hour; research has a separate 10 work/hour budget.", foreground=MUTED).pack(anchor="w", pady=10)
        self.queue = ttk.Treeview(page, columns=("item", "remaining", "work"), show="headings", height=6, selectmode="browse")
        for col, title in (("item", "Queued product"), ("remaining", "Units left"), ("work", "Work left on current unit")):
            self.queue.heading(col, text=title)
        self.queue.pack(fill="both", expand=True)
        row = ttk.Frame(page)
        row.pack(fill="x")
        self.button(row, "Cancel order & refund", self.cancel_order)

    def fleet_page(self):
        page = self.pages["Trade fleets"]
        row = ttk.Frame(page)
        row.pack(fill="x")
        self.fleet_name = tk.StringVar(value="Apollo transport")
        ttk.Entry(row, textvariable=self.fleet_name, width=26).pack(side="left", padx=6)
        self.button(row, "Create from 1 trade ship", lambda: self.action("create_fleet", name=self.fleet_name.get()))
        self.fleets = ttk.Treeview(page, columns=("name", "location", "destination", "cargo"), show="headings", height=7, selectmode="browse")
        for col, title in (("name", "Fleet"), ("location", "Location"), ("destination", "Destination / arrival hour"), ("cargo", "Cargo")):
            self.fleets.heading(col, text=title)
        self.fleets.pack(fill="both", expand=True, pady=10)
        row = ttk.Frame(page)
        row.pack(fill="x")
        self.destination = tk.StringVar(value="apollo")
        self.combo(row, self.destination, self.engine.state.planets)
        self.button(row, "Send selected fleet", lambda: self.fleet_action("travel", destination=self.destination.get()))
        self.button(row, "Deploy cargo miner station", lambda: self.fleet_action("deploy_station"))
        row = ttk.Frame(page)
        row.pack(fill="x")
        self.cargo = tk.StringVar(value="miner_station")
        self.combo(row, self.cargo, [*ORES, *RULES["products"]])
        self.cargo_count = tk.StringVar(value="1")
        self.combo(row, self.cargo_count, ["1", "10", "100", "1000"], 6)
        self.button(row, "Load cargo", lambda: self.fleet_action("transfer", item=self.cargo.get(), quantity=int(self.cargo_count.get()), load=True))
        self.button(row, "Unload cargo", lambda: self.fleet_action("transfer", item=self.cargo.get(), quantity=int(self.cargo_count.get()), load=False))
        ttk.Label(page, text="Select a fleet before issuing orders. Prototype: one trade ship per fleet, 1,000 cargo units, six hours per journey.", foreground=MUTED).pack(anchor="w", pady=12)

    def legacy_page(self):
        page = self.pages["Legacy tools"]
        row = ttk.Frame(page)
        row.pack(fill="x")
        self.button(row, "Inspect DOS save", self.inspect_legacy)
        self.button(row, "View DOS terrain map", self.inspect_map)
        row = ttk.Frame(page)
        row.pack(fill="x")
        self.legacy_resource = tk.StringVar(value="credits")
        self.combo(row, self.legacy_resource, RESOURCE_OFFSETS, 12)
        self.legacy_amount = tk.StringVar(value="1000000")
        ttk.Entry(row, textvariable=self.legacy_amount, width=16).pack(side="left", padx=6)
        self.button(row, "Export edited save copy", self.export_legacy)
        ttk.Label(page, text="DOS tools operate independently of the prototype. Export changes one known field in a new file.", foreground=MUTED).pack(anchor="w", pady=8)
        self.legacy_info = self.text(page, 9)
        self.terrain_canvas = tk.Canvas(page, width=750, height=240, bg=PANEL, highlightthickness=0)
        self.terrain_canvas.pack(fill="both", expand=True)
        self.replace_text(self.legacy_info, "Open a local SPIDYSAV file to inspect resources, or a MAP file to view tile IDs.\nOriginal art and collision meanings are not yet decoded.")

    def admin_page(self):
        page = self.pages["Admin console"]
        ttk.Checkbutton(page, text="Enable admin changes for this session", variable=self.admin,
                        command=lambda: setattr(self.engine, "admin_enabled", self.admin.get())).pack(anchor="w")
        ttk.Label(page, text="Successful changes mark the save as assisted and record the command. Normal play requires no admin access.", foreground=MUTED).pack(anchor="w", pady=8)
        row = ttk.Frame(page)
        row.pack(fill="x")
        self.command = tk.StringVar(value="give credits 100000")
        entry = ttk.Entry(row, textvariable=self.command)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry.bind("<Return>", lambda e: self.run_console())
        self.button(row, "Run", self.run_console)
        row = ttk.Frame(page)
        row.pack(fill="x")
        self.button(row, "+100,000 credits", lambda: self.run_console("give credits 100000"))
        self.button(row, "+1,000 of each ore", self.give_ores)
        self.button(row, "Finish queued work", lambda: self.run_console("finish"))
        self.console_output = self.text(page, 18)
        self.replace_text(self.console_output, ADMIN_HELP)

    def action(self, action, **args):
        try:
            self.engine.apply(action, **args)
            self.status.set(f"Applied: {action.replace('_', ' ')}")
            self.refresh()
            return True
        except (GameError, OSError) as exc:
            self.status.set(str(exc))
            return False

    def product_action(self, action):
        selection = self.products.selection()
        if not selection:
            self.status.set("Select a product first.")
            return
        args = {"item": selection[0]}
        if action == "produce":
            args["quantity"] = int(self.quantity.get())
        self.action(action, **args)

    def cancel_order(self):
        selection = self.queue.selection()
        if selection:
            self.action("cancel", index=int(selection[0]))
        else:
            self.status.set("Select a queued order first.")

    def fleet_action(self, action, **args):
        selection = self.fleets.selection()
        if selection:
            self.action(action, index=int(selection[0]), **args)
        else:
            self.status.set("Select a fleet first.")

    def select_tile(self, event):
        self.selected = (max(0, min(11, event.x // 42)), max(0, min(11, event.y // 42)))
        self.refresh()

    @staticmethod
    def populate(tree, rows):
        selection = tree.selection()
        tree.delete(*tree.get_children())
        for key, values in rows:
            tree.insert("", "end", iid=str(key), values=values)
        for key in selection:
            if tree.exists(key):
                tree.selection_set(key)

    def refresh(self):
        s = self.engine.state
        self.headline.configure(text=f"HOUR {s.hour:06,}     CREDITS {s.credits:>12,}     {'ASSISTED' if s.assisted else 'STANDARD'}")
        p = s.planets[self.world.get()]
        supply, demand, efficiency = power(p)
        info = f"{p.name.upper()}\n"
        if not p.surveyed:
            info += "No satellite coverage.\nDeploy a satellite to survey."
        else:
            info += f"{'Colony' if p.colony else 'Miner station' if p.station else 'Unsettled'} | {'Habitable' if p.habitable else 'Uninhabitable'}\nPopulation {p.population:,} | Tax {p.tax}%\nPower {supply}/{demand} | Working {efficiency}%\n\nORES\n"
            info += "\n".join(f"{k:<13} {v:>10,}" for k, v in p.ores.items())
            info += "\n\nSTORES\n" + "\n".join(f"{k:<15} {v:>8,}" for k, v in p.inventory.items())
        self.replace_text(self.world_info, info)
        self.canvas.delete("all")
        if p.surveyed:
            for y in range(12):
                for x in range(12):
                    color = "#1e3941" if (x*7+y*11) % 5 else "#29434a"
                    self.canvas.create_rectangle(x*42, y*42, x*42+41, y*42+41, fill=color, outline="#152a38")
            for b in p.buildings:
                color = "#aa843f" if b.work_left else "#34796c" if b.active else "#476784"
                self.canvas.create_rectangle(b.x*42+3, b.y*42+3, b.x*42+39, b.y*42+39, fill=color, outline=ACCENT if b.active else MUTED)
                label = {"windtrap": "PWR", "mine": "M", "derrick": "D", "housing": "H", "hospital": "+", "farm": "F", "command_centre": "HQ"}[b.kind]
                self.canvas.create_text(b.x*42+21, b.y*42+21, text=label, fill=INK, font=("Consolas", 10, "bold"))
            x, y = self.selected
            self.canvas.create_rectangle(x*42+1, y*42+1, x*42+41, y*42+41, outline=ACCENT, width=2)
        else:
            self.canvas.create_text(252, 230, text="NO SATELLITE COVERAGE", fill=MUTED, font=("Consolas", 15))
        b = next((b for b in p.buildings if (b.x, b.y) == self.selected), None)
        detail = f" · {b.kind} · {b.work_left} work left" if b else " · empty"
        self.tile_label.configure(text=f"Tile {self.selected[0]}, {self.selected[1]}{detail}")
        rows = []
        for key, spec in RULES["products"].items():
            status = "Available" if key in s.researched else f"{s.research_left} work left" if s.research == key else "Requires satellite" if spec["requires"] and "satellite" not in s.researched else "Not researched"
            rows.append((key, (spec["name"], status, f"{spec['credits']:,}", ", ".join(f"{v} {k}" for k, v in spec["ores"].items()), spec["work"])))
        self.populate(self.products, rows)
        self.populate(self.queue, [(i, (product.item, product.remaining, product.work_left)) for i, product in enumerate(s.production)])
        self.populate(self.fleets, [(i, (f.name, f.planet, f"{f.destination} / {f.eta}" if f.destination else "Docked", ", ".join(f"{v} {k}" for k, v in f.cargo.items() if v) or "Empty")) for i, f in enumerate(s.fleets)])
        self.replace_text(self.messages, "\n".join(reversed(s.messages)))

    def run_console(self, command=None):
        try:
            output = self.engine.console(command if command is not None else self.command.get())
            self.status.set(output.splitlines()[0])
            history = self.console_output.get("1.0", "end").strip()
            self.replace_text(self.console_output, (history + "\n\n" + output)[-20000:])
            self.console_output.see("end")
            self.refresh()
            return True
        except GameError as exc:
            self.status.set(str(exc))
            return False

    def give_ores(self):
        # Validate the whole group on a temporary engine before committing any ore.
        candidate = Engine(self.engine.state, admin_enabled=self.engine.admin_enabled)
        try:
            for ore in ORES:
                candidate.console(f"give {ore} 1000 {self.world.get()}")
            self.engine.state = candidate.state
            self.refresh()
            self.status.set(f"Added 1,000 of each ore to {self.world.get()}.")
        except GameError as exc:
            self.status.set(str(exc))

    def save(self):
        self.paused.set(True)
        directory = default_save_directory()
        try:
            directory.mkdir(exist_ok=True)
        except OSError as exc:
            self.status.set(str(exc))
            return
        path = filedialog.asksaveasfilename(parent=self.root, initialdir=directory, defaultextension=".json", filetypes=[("Modern save", "*.json")])
        if path:
            try:
                save_game(self.engine.state, path)
                self.status.set(f"Saved {Path(path).name}.")
            except (OSError, GameError) as exc:
                self.status.set(str(exc))

    def load(self):
        self.paused.set(True)
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Modern save", "*.json")])
        if path:
            try:
                self.engine = Engine(load_game(path), admin_enabled=self.admin.get())
                self.refresh()
                self.status.set(f"Loaded {Path(path).name}.")
            except (OSError, GameError) as exc:
                self.status.set(str(exc))

    def reset(self):
        self.paused.set(True)
        # Preserve a recovery save automatically before replacing the current scenario.
        path = default_save_directory() / "before-new-game.json"
        try:
            save_game(self.engine.state, path)
            self.engine = Engine(new_game(), admin_enabled=self.admin.get())
            self.refresh()
            self.status.set("New scenario. Previous state saved to saves/before-new-game.json.")
        except (OSError, GameError) as exc:
            self.status.set(str(exc))

    def inspect_legacy(self):
        self.paused.set(True)
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("DOS saves", "SPIDYSAV.*"), ("All files", "*.*")])
        if path:
            try:
                import json
                save = LegacySave.read(path)
                self.legacy_path = path
                self.replace_text(self.legacy_info, json.dumps(save.describe(), indent=2))
            except (OSError, GameError) as exc:
                self.status.set(str(exc))

    def export_legacy(self):
        self.paused.set(True)
        if not self.legacy_path:
            self.status.set("Inspect a DOS save first.")
            return
        try:
            amount = int(self.legacy_amount.get())
            LegacySave.read(self.legacy_path).with_resources({self.legacy_resource.get(): amount})
            path = filedialog.asksaveasfilename(parent=self.root, initialfile="SPIDYSAV.edited")
            if path:
                export_legacy(self.legacy_path, path, {self.legacy_resource.get(): amount})
                self.status.set(f"Exported {Path(path).name}; source unchanged.")
        except (OSError, ValueError) as exc:
            self.status.set(str(exc))

    def inspect_map(self):
        self.paused.set(True)
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("DOS terrain", "*.MAP")])
        if not path:
            return
        try:
            terrain = TerrainMap.read(path)
            self.terrain_canvas.delete("all")
            width = max(100, self.terrain_canvas.winfo_width())
            height = max(100, self.terrain_canvas.winfo_height())
            scale = min(width / terrain.width, height / terrain.height)
            for y in range(terrain.height):
                for x in range(terrain.width):
                    tile = terrain.tile(x, y)
                    color = f"#{30+tile*31%100:02x}{60+tile*47%150:02x}{65+tile*17%140:02x}"
                    self.terrain_canvas.create_rectangle(x*scale, y*scale, (x+1)*scale, (y+1)*scale, fill=color, outline="")
            self.replace_text(self.legacy_info, f"{Path(path).name}: {terrain.width} × {terrain.height}, {len(set(terrain.tiles))} tile IDs.\nColors represent tile IDs, not original graphics. Row-major orientation is provisional.")
        except (OSError, GameError) as exc:
            self.status.set(str(exc))

    def timer(self):
        if not self.paused.get():
            if not self.action("advance", hours=int(self.speed.get())):
                self.paused.set(True)
        self.timer_id = self.root.after(1000, self.timer)

    def close(self):
        self.paused.set(True)
        try:
            save_game(self.engine.state, default_save_directory() / "autosave.json")
        except (OSError, GameError) as exc:
            self.status.set(f"Autosave failed: {exc}. Save to another location before closing.")
            return
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        self.root.destroy()


def play():
    root = tk.Tk()
    App(root)
    root.mainloop()
