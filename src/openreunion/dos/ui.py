"""Native inspection/playback client for verified portions of DOS gameplay."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from ..core import GameError
from ..persistence import default_save_directory
from .catalog import ORE_KEYS, SUBJECTS
from .content import ContentSource
from .session import NOTICE, RecoveredSession
from .worlds import describe_world,force_intelligence
from .world_info import survey_information,owner_label,environment_summary
from .world_lists import FILTERS,filtered_worlds,world_visible
from .race_info import revealed_race
from .descriptions import product_description_available
from .fleets import storage_limit,payload_count
from .surface import occupancy,building_available,footprint,placement_fits
from .commanders import ROLES,COURSES,skill_limits
import struct

STATES = ("Locked", "Available (1)", "Researching (2)", "Available (3)", "Researching (4)", "Complete")


class RecoveredApp:
    def __init__(self,root,installation,save=None):
        self.root,self.installation = root,Path(installation).resolve()
        self.content = ContentSource(self.installation)
        self.catalog = self.content.catalog
        self.session = self.content.new_game() if save is None else self.content.initial_session(save)
        self.save_dir = default_save_directory()
        self.refresh_listeners=[]
        self.ground_window=None
        self.space_window=None
        self.dialog_window=None
        self.scene_window=None
        root.title("Open Reunion — recovered DOS systems")
        root.geometry("1180x820")
        root.minsize(980,720)
        root.protocol("WM_DELETE_WINDOW",self.close)
        outer = ttk.Frame(root,padding=12)
        outer.pack(fill="both",expand=True)
        self.summary = tk.StringVar()
        ttk.Label(outer,text="OPEN REUNION",font=("Segoe UI",18,"bold")).pack(anchor="w")
        ttk.Label(outer,textvariable=self.summary,font=("Segoe UI",11)).pack(anchor="w",pady=6)
        notice=ttk.Label(outer,text=NOTICE,wraplength=1080,foreground="#8a4200")
        notice.pack(anchor="w",fill="x")
        from .outcome_ui import OutcomePanel
        self.outcome_panel = OutcomePanel(outer, self)
        self.hour_buttons = []
        toolbar = self.toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x",pady=8)
        for label,callback in (("+1 hour",lambda:self.act("advance",hours=1)),("+24 hours",lambda:self.act("advance",hours=24)),
                               ("New game",self.new_game),("Import DOS save",self.import_save),("Save session",self.save),("Load session",self.load),
                               ("Ground battle",self.show_ground_battle),("Space battle",self.show_space_battle),("Story",self.show_presentation)):
            button = ttk.Button(toolbar,text=label,command=lambda fn=callback:self.guard(fn))
            button.pack(side="left",padx=(0,6))
            if label in ('+1 hour', '+24 hours'):self.hour_buttons.append(button)
        from .clock_ui import ClockPanel
        self.clock_panel=ClockPanel(outer,self)
        self.book = ttk.Notebook(outer)
        self.book.pack(fill="both",expand=True)
        self.tabs = {}
        for name in ("Research & production","Worlds","Commanders","Bar","Original artwork","Original text","Music","Admin & log"):
            tab = ttk.Frame(self.book,padding=8)
            self.book.add(tab,text=name)
            self.tabs[name] = tab
        self.build_products()
        self.build_worlds()
        self.build_commanders()
        from .bar_ui import BarPanel
        self.bar_panel=BarPanel(self,self.tabs["Bar"])
        self.build_art()
        self.build_text()
        from .music_ui import MusicPanel
        self.music_panel=MusicPanel(self,self.tabs['Music'])
        self.build_admin()
        self.status = tk.StringVar(value="Ready. Use Run to advance time continuously, or step with the hour buttons.")
        status_label=ttk.Label(outer,textvariable=self.status,wraplength=1080)
        status_label.pack(side="bottom",anchor="w",fill="x",pady=(8,0),before=self.book)
        def wrap_labels(event):
            width=max(200,event.width-24)
            notice.configure(wraplength=width);status_label.configure(wraplength=width)
        outer.bind("<Configure>",wrap_labels)
        from .effect_output import EffectOutput
        self.effects=EffectOutput(self)
        self.sound=tk.BooleanVar(value=True)
        ttk.Checkbutton(self.tabs['Music'],text='Sound effects',variable=self.sound,
                        command=lambda:self.guard(self.set_sound)).pack(anchor='w',pady=8)
        self.refresh()
        if self.session.state['active_scene'] is not None or self.session.state["active_dialog"] is not None:self.show_presentation(autoplay=False)
        if (self.session.state["campaign"]["bar"] or {}).get("conversation") is not None:self.book.select(self.tabs["Bar"])

    def set_sound(self):
        self.effects.set_enabled(self.sound.get());self.refresh()

    def guard(self,callback):
        try:
            callback()
        except (GameError,ValueError,OSError,tk.TclError) as exc:
            self.pause_battles()
            self.status.set(str(exc))
            messagebox.showerror("Open Reunion",str(exc),parent=self.root)

    def act(self,action,*,defer_presentation=False,**kwargs):
        self.session.admin_enabled = self.admin.get()
        events=self.session.apply(action,**kwargs)
        self.refresh()
        problem=self.effects.error or self.effects.warning
        self.status.set('Sound effect unavailable: '+problem if problem else
                        "Updated. "+("Admin assistance recorded." if self.session.state["assisted"] else ""))
        if not defer_presentation and (self.session.state['presentation_requests'] or action in ("advance","space_acknowledge","ground_acknowledge","ground_cancel","dialog_answer","dialog_acknowledge","scene_acknowledge","dismiss_presentation")):
            if self.session.state["active_dialog"] is not None or self.session.state['active_scene'] is not None or self.session.state['presentation_requests']:self.show_presentation()
            elif (self.session.state["space_encounter"] or {}).get("phase","closed")!="closed":self.show_space_battle()
            elif (self.session.state["ground_encounter"] or {}).get("phase","closed")!="closed":self.show_ground_battle()
        return events

    @staticmethod
    def tree(parent,columns,widths,height=12):
        holder = ttk.Frame(parent)
        holder.pack(fill="both",expand=True)
        tree = ttk.Treeview(holder,columns=columns,show="headings",height=height,selectmode="browse")
        for name,width in zip(columns,widths):
            tree.heading(name,text=name)
            tree.column(name,width=width,minwidth=45,stretch=True)
        bar = ttk.Scrollbar(holder,orient="vertical",command=tree.yview)
        tree.configure(yscrollcommand=bar.set)
        tree.pack(side="left",fill="both",expand=True)
        bar.pack(side="right",fill="y")
        return tree

    def selected_id(self,tree):
        if not tree.selection():
            raise GameError("Select an item first.")
        return int(tree.selection()[0])

    def watch_session(self,window,callback):
        def refresh():
            if window.winfo_exists():callback()
        self.refresh_listeners.append(refresh)
        def remove(event):
            if event.widget==window and refresh in self.refresh_listeners:self.refresh_listeners.remove(refresh)
        window.bind("<Destroy>",remove,add="+")

    def watch_fleet(self,window,callback=None):
        from .editor_context import FleetContext
        context=FleetContext(self.session)
        def refresh():
            if not context.current(self.session):
                window.destroy()
                self.status.set("The campaign or fleet list changed; reopen the fleet editor to select a fleet.")
            elif callback:callback()
        self.watch_session(window,refresh)
        return context

    def watch_world(self,window,definition,callback,*,fleets=False):
        from .editor_context import WorldContext
        context=WorldContext(self.session,definition,fleets=fleets)
        def refresh():
            if not context.current(self.session):
                window.destroy()
                self.status.set('The campaign, world or fleet list changed; reopen the world editor.')
            else:callback()
        self.watch_session(window,refresh)
        return context

    def build_products(self):
        tab = self.tabs["Research & production"]
        self.products = self.tree(tab,("ID","Product","State","Progress","Credits/unit","Stock","Pending","Work left"),
                                  (45,170,120,75,90,60,60,80))
        self.products.bind("<<TreeviewSelect>>",lambda _:self.product_detail())
        self.details = tk.StringVar()
        ttk.Label(tab,textvariable=self.details,wraplength=1060).pack(anchor="w",pady=8)
        controls = ttk.Frame(tab)
        controls.pack(fill="x")
        ttk.Button(controls,text="Start / pause research",command=lambda:self.guard(lambda:self.act("research",product_id=self.selected_id(self.products)))).pack(side="left")
        ttk.Label(controls,text="Pending quantity:").pack(side="left",padx=(16,4))
        self.quantity = tk.StringVar(value="1")
        ttk.Entry(controls,textvariable=self.quantity,width=7).pack(side="left")
        ttk.Button(controls,text="Set order",command=lambda:self.guard(lambda:self.act("order",product_id=self.selected_id(self.products),quantity=int(self.quantity.get())))).pack(side="left",padx=6)
        self.product_description_button=ttk.Button(controls,text='Product description',state='disabled',
            command=lambda:self.guard(self.product_description_window))
        self.product_description_button.pack(side='left',padx=6)

    def product_detail(self):
        if not self.products.selection():
            self.product_description_button.configure(state='disabled')
            return
        p = self.catalog["products"][self.selected_id(self.products)-1]
        self.product_description_button.configure(state='normal' if product_description_available(self.session.state['products'][p['id']-1]) else 'disabled')
        self.details.set("Ore cost/unit: "+", ".join(f"{k} {p['ore_costs'][k]:,}" for k in ORE_KEYS)
                         +"\nRequired skills: "+", ".join(f"{k.replace('_',' ')} {p['requirements'][k]}" for k in SUBJECTS)
                         +f" | Research duration parameter: {p['research_duration']} | Production work/unit: {p['base_work']}")

    def product_description_window(self):
        product_id=self.selected_id(self.products);session=self.session
        if not product_description_available(session.state['products'][product_id-1]):
            raise GameError('Complete this research to read its product description.')
        data=self.content.description('product',product_id)
        definition=self.catalog['products'][product_id-1]
        window=tk.Toplevel(self.root);window.title(definition['name']+' — Product description')
        window.geometry('620x330');window.minsize(480,300)
        body=ttk.Frame(window,padding=14);body.pack(fill='both',expand=True)
        ttk.Label(body,text=definition['name'],font=('Segoe UI',12,'bold')).pack(anchor='w')
        if data['title'].casefold()!=definition['name'].casefold():
            ttk.Label(body,text='Original name: '+data['title']).pack(anchor='w',pady=(4,0))
        label=ttk.Label(body,text=data['description'],wraplength=580,justify='left');label.pack(anchor='w',pady=14)
        window.bind('<Configure>',lambda e:label.configure(wraplength=max(240,e.width-32)) if e.widget==window else None,add='+')
        def refresh():
            if self.session is not session or not product_description_available(self.session.state['products'][product_id-1]):window.destroy()
        self.watch_session(window,refresh);return window

    def build_commanders(self):
        tab = self.tabs["Commanders"]
        self.commanders = self.tree(tab,("Role","Rank","Name","Hire price","Level","Limit"),(130,60,180,100,90,70),height=8)
        for i,c in enumerate(self.catalog["commanders"]):
            self.commanders.insert("","end",iid=str(i),values=(c["role"],c["rank"],c["name"],f"{c['hire_price']:,}",c["level"]))
        self.commander_status = tk.StringVar()
        ttk.Label(tab,textvariable=self.commander_status,wraplength=1060).pack(anchor="w",pady=8)
        def hire():
            c = self.catalog["commanders"][self.selected_id(self.commanders)]
            self.act("hire",role=c["role"],rank=c["rank"])
        actions=ttk.Frame(tab);actions.pack(fill='x')
        ttk.Button(actions,text="Hire selected commander",command=lambda:self.guard(hire)).pack(side='left')
        ttk.Button(actions,text='Consult selected commander',command=lambda:self.guard(self.consult_window)).pack(side='left',padx=8)
        ttk.Button(actions,text='Candidate profile',command=lambda:self.guard(self.candidate_window)).pack(side='left')
        training=ttk.LabelFrame(tab,text="University",padding=8)
        training.pack(fill="x",pady=8)
        row=ttk.Frame(training);row.pack(fill="x")
        ttk.Label(row,text="Hired role:").pack(side="left")
        self.training_role=tk.StringVar(value="developer")
        ttk.Combobox(row,textvariable=self.training_role,values=ROLES,state="readonly",width=12).pack(side="left",padx=6)
        self.training_course=tk.StringVar(value=COURSES[0])
        ttk.Combobox(row,textvariable=self.training_course,values=COURSES,state="readonly",width=29).pack(side="left",padx=6)
        def quote():
            role=self.training_role.get()
            self.act("quote_training",role=role,course=COURSES.index(self.training_course.get())+1 if role=="developer" else 0)
        ttk.Button(row,text="Get training quote",command=lambda:self.guard(quote)).pack(side="left",padx=6)
        self.training_status=tk.StringVar()
        ttk.Label(training,textvariable=self.training_status,wraplength=880).pack(anchor="w",pady=6)
        self.training_buy=ttk.Button(training,text="Accept quoted training",command=lambda:self.guard(lambda:self.act("train")))
        self.training_buy.pack(anchor="w")
        ttk.Label(training,text="One commander at a time. Developer training pauses research. Replacing a commander ends their course without a refund.",
                  wraplength=880).pack(anchor="w",pady=(6,0))

    def candidate_window(self):
        index=self.selected_id(self.commanders);definition=self.catalog['commanders'][index]
        session=self.session;role=definition['role'];rank=definition['rank']
        data=self.content.description('candidate',index+1)
        window=tk.Toplevel(self.root);window.title(definition['name']+' — Candidate profile')
        window.geometry('620x350');window.minsize(480,330)
        body=ttk.Frame(window,padding=14);body.pack(fill='both',expand=True)
        ttk.Label(body,text=definition['name']+' — '+role.title(),font=('Segoe UI',12,'bold')).pack(anchor='w')
        intro=ttk.Label(body,text=data['description'],wraplength=580,justify='left');intro.pack(anchor='w',pady=12)
        details=tk.StringVar();label=ttk.Label(body,textvariable=details,wraplength=580,justify='left');label.pack(anchor='w')
        def refresh():
            if self.session is not session:window.destroy();return
            state=session.state;current=state['ranks'][role];hired=current==rank
            level=state['levels'][role] if hired else state['campaign']['commander_levels'][index]
            status='Currently hired' if hired else 'Available to hire' if current<rank else 'A higher-ranked commander is already hired'
            text=f"Rank: {rank} | Level: {level} | Level limit: {self.catalog['training_rules']['level_caps'][index]}\n{status}"
            if current<rank:text+=f"\nHire price: {definition['hire_price']:,} credits"
            if role=='developer':
                skills=state['skills'] if hired else dict(zip(SUBJECTS,state['campaign']['developer_skill_choices'][4*(rank-1):4*rank]))
                text+='\n'+', '.join(f"{key.replace('_',' ').title()}: {value}" for key,value in skills.items())
            details.set(text)
        def resize(event):
            if event.widget==window:
                for widget in (intro,label):widget.configure(wraplength=max(240,event.width-32))
        window.bind('<Configure>',resize,add='+');self.watch_session(window,refresh);refresh();return window

    def consult_window(self):
        self.clock_panel.clock.pause()
        from .advice import unavailable
        selected=self.catalog['commanders'][self.selected_id(self.commanders)]
        role=selected['role'];session=self.session;rank=session.state['ranks'][role]
        if rank!=selected['rank']:raise GameError('Select your hired commander to consult them.')
        reason=unavailable(session.state,role)
        if reason:raise GameError(reason)
        rules=self.catalog.get('commander_advice')
        if rules is None:raise GameError('Commander advice is missing; extract the original content again.')
        window=tk.Toplevel(self.root);window.title(selected['name']+' — Consultation')
        window.geometry('650x420');window.minsize(540,400)
        body=ttk.Frame(window,padding=12);body.pack(fill='both',expand=True)
        ttk.Label(body,text=selected['name']+' — '+role.title(),font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,8))
        reply=tk.StringVar(value='Choose a question to ask your commander.')
        def current():
            return self.session is session and self.session.state['ranks'][role]==rank
        def ask(question):
            if not current():raise GameError('This consultation has ended. Select your current commander.')
            response=self.act('consult_commander',role=role,question=question)[0]
            reply.set(response['question']+'\n\n'+response['answer'])
        for question,text in enumerate(rules['questions'],1):
            ttk.Button(body,text=text,command=lambda q=question:self.guard(lambda:ask(q))).pack(anchor='w',pady=3)
        def university():
            if not current():raise GameError('This consultation has ended. Select your current commander.')
            self.training_role.set(role);self.book.select(self.tabs['Commanders']);self.root.lift();window.destroy()
        ttk.Button(body,text='University training',command=lambda:self.guard(university)).pack(anchor='w',pady=3)
        label=ttk.Label(body,textvariable=reply,wraplength=610,justify='left');label.pack(anchor='w',pady=16)
        window.bind('<Configure>',lambda e:label.configure(wraplength=max(250,e.width-32)) if e.widget==window else None,add='+')
        def refresh():
            if not current() or unavailable(self.session.state,role):window.destroy()
        self.watch_session(window,refresh);return window

    def build_worlds(self):
        tab = self.tabs["Worlds"]
        filters=ttk.Frame(tab);filters.pack(fill='x',pady=(0,6))
        ttk.Label(filters,text='Show:').pack(side='left',padx=(0,6))
        self.world_filter=tk.StringVar(value=FILTERS[0])
        self.world_filter_selector=ttk.Combobox(filters,textvariable=self.world_filter,values=FILTERS,state='readonly',width=22)
        self.world_filter_selector.pack(side='left')
        self.world_filter_selector.bind('<<ComboboxSelected>>',lambda _:self.guard(self.refresh))
        self.world_count=tk.StringVar();ttk.Label(filters,textvariable=self.world_count).pack(side='left',padx=12)
        self.first_world_refresh=True
        self.worlds = self.tree(tab,("World","Orbit","Owner","Satellite","Survey / 60","Population","Status"),
                                (145,75,125,80,90,90,115),height=7)
        self.worlds.bind("<<TreeviewSelect>>",lambda _:self.world_detail())
        self.world_details = tk.StringVar()
        ttk.Label(tab,textvariable=self.world_details,wraplength=900).pack(anchor="w",pady=8)
        self.world_buildings = self.tree(tab,("Building","Position","Condition %","Operating","Workers","Power","Performance %"),
                                         (180,75,85,85,75,75,100),height=6)
        def launch():
            if not self.worlds.selection():
                raise GameError("Select a world first.")
            self.act("launch_satellite",world_id=self.worlds.selection()[0])
        controls=ttk.Frame(tab)
        controls.pack(side='bottom',fill="x",before=self.worlds.master)
        ttk.Button(controls,text="Launch satellite",command=lambda:self.guard(launch)).pack(side="left")
        def assign():
            if not self.worlds.selection():
                raise GameError("Select a world first.")
            self.act("assign_droid",world_id=self.worlds.selection()[0])
        ttk.Button(controls,text="Assign Miner droid",command=lambda:self.guard(assign)).pack(side="left",padx=5)
        ttk.Button(controls,text="Build on surface",command=lambda:self.guard(self.surface_window)).pack(side="left")
        def demolish():
            if not self.worlds.selection() or not self.world_buildings.selection():
                raise GameError("Select a colony building first.")
            self.act("demolish",world_id=self.worlds.selection()[0],building_index=int(self.world_buildings.selection()[0]))
        ttk.Button(controls,text="Demolish (2,000 credits)",command=lambda:self.guard(demolish)).pack(side="left",padx=5)
        ttk.Button(controls,text="Colonize",command=lambda:self.guard(self.colonize_window)).pack(side="left")
        orbital_controls=ttk.Frame(tab)
        orbital_controls.pack(side='bottom',fill="x",pady=6,before=controls)
        ttk.Button(orbital_controls,text="Orbital support",command=lambda:self.guard(self.orbital_window)).pack(side="left")
        ttk.Button(orbital_controls,text="Fleets & equipment",command=lambda:self.guard(self.fleet_window)).pack(side="left",padx=5)
        ttk.Button(orbital_controls,text="Colony taxes",command=lambda:self.guard(self.tax_window)).pack(side="left",padx=5)
        ttk.Button(orbital_controls,text="Survey report",command=lambda:self.guard(self.survey_window)).pack(side="left",padx=5)
        ttk.Label(orbital_controls,text="Deploy carried stations or satellites, or manage fleet routes and cargo.",
                  wraplength=400).pack(side="left",padx=8)

    def tax_window(self):
        from .colony import TAX_LABELS,can_change_tax,set_tax_level,daily_tax
        if not self.worlds.selection():raise GameError('Select a colony first.')
        world_id=self.worlds.selection()[0]
        world,raw,_=self.session._orbital_world(self.session.state,world_id)
        if not can_change_tax(raw):raise GameError('Taxes can be changed only at an owned active colony.')
        window=tk.Toplevel(self.root);window.title('Colony taxes — '+world['name'])
        window.geometry('510x235');window.minsize(480,235)
        body=ttk.Frame(window,padding=12);body.pack(fill='both',expand=True)
        ttk.Label(body,text=world['name'],font=('Segoe UI',13,'bold')).pack(anchor='w')
        labels=[f'{i} — {label}' for i,label in enumerate(TAX_LABELS)]
        choice=ttk.Combobox(body,values=labels,state='readonly',width=28);choice.pack(anchor='w',pady=8)
        choice.current(raw[18] if raw[18]<8 else 3)
        preview=tk.StringVar();ttk.Label(body,textvariable=preview,wraplength=450).pack(anchor='w')
        def refresh(_=None):
            context.require(self.session)
            current=self.session.state['worlds'][world_id]['raw']
            changed=set_tax_level(current,choice.current())
            preview.set(f'Daily tax at current population and morale: {daily_tax(changed):,} credits.'
                +'\nCollected at midnight. Higher taxes lower target morale and can reduce population growth.')
        def apply():
            context.require(self.session)
            self.act('set_tax',world_id=world_id,level=choice.current())
        choice.bind('<<ComboboxSelected>>',lambda event:self.guard(lambda:refresh(event)))
        ttk.Button(body,text='Apply tax level',command=lambda:self.guard(apply)).pack(anchor='w',pady=12)
        context=self.watch_world(window,world,refresh)
        refresh();return window

    def fleet_window(self, selected=None):
        from .editor_context import FleetContext
        context=FleetContext(self.session)
        window=tk.Toplevel(self.root)
        window.title("Fleets and equipment")
        window.geometry("900x640")
        window.minsize(800,560)
        body=ttk.Frame(window,padding=12)
        body.pack(fill="both",expand=True)
        fleets=self.tree(body,("Name","Type","Location","State","Hours left"),(200,120,140,110,80),height=5)
        create=ttk.Frame(body)
        create.pack(fill="x",pady=6)
        kind=tk.StringVar(value="2: Trade")
        ttk.Combobox(create,textvariable=kind,state="readonly",width=17,
                     values=[f"{r['id']}: {r['name']}" for r in self.catalog["fleet_rules"][:4]]).pack(side="left")
        name=tk.StringVar()
        ttk.Entry(create,textvariable=name,width=22).pack(side="left",padx=6)
        details=tk.StringVar(value="Select a fleet. Transfers require a landed fleet at an owned colony.")
        ttk.Label(body,textvariable=details,wraplength=850).pack(anchor="w",pady=6)
        equipment=self.tree(body,("Hull / equipment","On fleet","Depot stock","Capacity"),(310,100,100,100),height=8)
        controls=ttk.Frame(body)
        controls.pack(fill="x",pady=8)
        amount=tk.StringVar(value="1")
        ttk.Label(controls,text="Quantity:").pack(side="left")
        ttk.Entry(controls,textvariable=amount,width=7).pack(side="left",padx=6)
        def refresh_equipment():
            selected=equipment.selection()
            equipment.delete(*equipment.get_children())
            if not fleets.selection():
                details.set("Select a fleet. Transfers require a landed fleet at an owned colony.")
                return
            bank,index=fleets.selection()[0].split(":")
            row=self.session.state["fleets"][bank][int(index)]
            rule=next((r for r in self.catalog["fleet_rules"] if r["id"]==row[0]),None)
            if rule is None:return
            identity=tuple(row[19:22])
            from .fleets import local_record
            local=local_record(self.session.state["fleets"],identity)
            details.set("New Earth depot" if identity==(1,5,0) else "Local colony depot; some equipment is supplied only by New Earth.")
            for cat in rule["categories"]:
                for h,hull in enumerate(cat["hulls"],1):
                    at=29+40*(cat["bank"]-1)+10*(h-1)
                    values=struct.unpack_from("<5h",bytes(row),at)
                    for comp,item in enumerate([hull,*cat["components"]]):
                        if comp and hull["limits"][comp-1]==0 and values[comp]==0:continue
                        stock=(self.session.state["products"][item["product"]-1]["stock"] if identity==(1,5,0)
                               else struct.unpack_from("<h",bytes(local),131+2*item["local_slot"])[0] if local and item["local_slot"] else "—")
                        limit=1000 if comp==0 else hull["limits"][comp-1]*values[0]
                        label=hull["name"] if not comp else hull["name"]+" / "+self.catalog["products"][item["product"]-1]["name"]
                        equipment.insert("","end",iid=f"{cat['id']}:{h}:{comp}",values=(label,values[comp],stock,limit))
            if selected and equipment.exists(selected[0]):equipment.selection_set(selected[0])
        def refresh(select=None):
            nonlocal context
            from .navigation import remaining_hours
            selected=fleets.selection() if context.current(self.session) else ()
            context=FleetContext(self.session)
            fleets.delete(*fleets.get_children())
            for bank,rows in self.session.state["fleets"].items():
                for index,row in enumerate(rows):
                    label=bytes(row[2:2+min(17,row[1])]).decode("cp437") or f"Fleet {index+1}"
                    rule=next((r for r in self.catalog["fleet_rules"] if r["id"]==row[0]),None)
                    fleets.insert("","end",iid=f"{bank}:{index}",values=(label,rule["name"] if rule else row[0],
                        ":".join(map(str,row[19:22])),{1:"Landed",2:"Orbit",4:"Approaching",5:"Hyperspace",6:"Departing",7:"Local defense"}.get(row[22],"Unavailable"),
                        remaining_hours(row,self.session.state["levels"]["pilot"])))
            choice=select or (selected[0] if selected else None)
            if choice and fleets.exists(choice):fleets.selection_set(choice)
            refresh_equipment()
        def new():
            self.act("create_fleet",fleet_type=int(kind.get().split(":")[0]),name=name.get() or None)
            refresh(f"moving:{len(self.session.state['fleets']['moving'])-1}")
        def transfer(sign):
            if not fleets.selection() or not equipment.selection():
                raise GameError("Select a fleet and a hull or equipment row.")
            bank,index=fleets.selection()[0].split(":")
            category,hull,component=map(int,equipment.selection()[0].split(":"))
            quantity=int(amount.get())
            if quantity<=0:raise GameError("Enter a positive quantity.")
            self.act("equip_fleet",bank=bank,fleet_index=int(index),category=category,hull=hull,component=component,quantity=sign*quantity)
            refresh_equipment()
        ttk.Button(create,text="Create at New Earth",command=lambda:self.guard(new)).pack(side="left")
        def rename():
            if not fleets.selection():raise GameError("Select a fleet first.")
            bank,index=fleets.selection()[0].split(":")
            row=self.session.state["fleets"][bank][int(index)]
            old=bytes(row[2:2+min(17,row[1])]).decode("cp437")
            rename_context=FleetContext(self.session)
            self.clock_panel.clock.pause()
            value=simpledialog.askstring("Rename fleet","Fleet name (1–17 characters):",
                                         initialvalue=old,parent=window)
            if value is not None:
                rename_context.require(self.session)
                self.act("rename_fleet",bank=bank,fleet_index=int(index),name=value)
        ttk.Button(create,text="Rename selected",command=lambda:self.guard(rename)).pack(side="left",padx=6)
        if hasattr(self,'open_equipment'):
            def original_equipment():
                context.require(self.session)
                if not fleets.selection():raise GameError('Select a fleet first.')
                bank,index=fleets.selection()[0].split(':')
                self.open_equipment(bank,int(index))
                window.destroy()
            ttk.Button(create,text='Original equipment',command=lambda:self.guard(original_equipment)).pack(side='left')
        ttk.Button(controls,text="Load",command=lambda:self.guard(lambda:transfer(1))).pack(side="left",padx=6)
        ttk.Button(controls,text="Unload",command=lambda:self.guard(lambda:transfer(-1))).pack(side="left")
        def cargo():
            if not fleets.selection():raise GameError("Select a fleet first.")
            bank,index=fleets.selection()[0].split(":")
            if bank!="moving":raise GameError("Select a Trade or Pirate fleet.")
            self.cargo_window(int(index))
        ttk.Button(controls,text="Cargo",command=lambda:self.guard(cargo)).pack(side="left",padx=6)
        def moving_index():
            if not fleets.selection():raise GameError("Select a fleet first.")
            bank,index=fleets.selection()[0].split(":")
            if bank!="moving":raise GameError("Select a moving fleet.")
            return int(index)
        def orbit():
            self.act("orbit",fleet_index=moving_index());refresh()
        ttk.Button(controls,text="Launch / land",command=lambda:self.guard(orbit)).pack(side="left",padx=6)
        ttk.Button(controls,text="Route",command=lambda:self.guard(lambda:self.navigation_window(moving_index()))).pack(side="left")
        ttk.Button(controls,text="Attack...",command=lambda:self.guard(lambda:self.attack_window(moving_index()))).pack(side="left",padx=6)
        ttk.Label(body,text="Launch into orbit before choosing a route. Land before transferring cargo. An Army can attack after arrival; ground assaults also need a surveyed alien world and a rank 2 or 3 fighter commander.",wraplength=850).pack(anchor="w")
        fleets.bind("<<TreeviewSelect>>",lambda _:refresh_equipment())
        self.watch_session(window,refresh)
        refresh(selected)
        return window

    def attack_window(self,index):
        from .aliens import fleet_at
        from .battle_dispatch import player_attack_request
        state=self.session.state
        row=state["fleets"]["moving"][index]
        if row[0]!=1:raise GameError("Select an Army fleet to attack.")
        candidates=[("Assault current world",{})]
        for race,civilization in enumerate(state["campaign"]["civilizations"],2):
            for slot in range(1,civilization[38]+1):
                alien=fleet_at(civilization,slot)
                if alien[8:10]==row[19:21] and alien[2]==1 and alien[0]>1:
                    name=self.catalog.get("alien_names",["Civilization"]*11)[race-2]
                    candidates.append((f"Attack {name} fleet {slot}",{"target_race":race,"target_slot":slot}))
        choices={};reasons=[]
        for label,arguments in candidates:
            try:player_attack_request(state,index,**arguments)
            except GameError as error:reasons.append(str(error))
            else:choices[label]=arguments
        if not choices:raise GameError(reasons[0] if len(candidates)==1 else "No eligible attack target. "+reasons[0])
        window=tk.Toplevel(self.root);window.title("Army attack");window.geometry("580x250");window.minsize(520,230)
        body=ttk.Frame(window,padding=12);body.pack(fill="both",expand=True)
        selected=tk.StringVar(value=next(iter(choices)))
        ttk.Label(body,text="Choose an attack target",font=("Segoe UI",12,"bold")).pack(anchor="w")
        ttk.Combobox(body,textvariable=selected,state="readonly",values=list(choices),width=55).pack(fill="x",pady=12)
        ttk.Label(body,text="Attacking makes this civilization hostile. Space combat includes forces around this planet and its moons. A successful assault then opens ground deployment.",wraplength=490).pack(anchor="w")
        # Other campaign dialogs can compact the fleet banks. Recheck the
        # selected record so a stale dialog cannot order a different Army.
        original=row
        context=self.watch_fleet(window)
        def attack():
            context.require(self.session)
            fleets=self.session.state["fleets"]["moving"]
            if index>=len(fleets) or fleets[index]!=original:
                raise GameError("The fleet has changed. Reopen the attack selection.")
            self.act("attack",fleet_index=index,**choices[selected.get()])
            window.destroy();self.show_space_battle()
        ttk.Button(body,text="Attack",command=lambda:self.guard(attack)).pack(anchor="w",pady=12)
        return window

    def navigation_window(self,index):
        state=self.session.state;nav=state["campaign"]["navigation"]
        choices={}
        for system,known in enumerate(state["known_systems"],1):
            if known>=128:continue
            label=self.catalog["system_names"][system-1]+" system"
            choices[f"{system}:0:0 - {label}"]=[system,0,0]
            if known!=1:continue
            for w in self.catalog["worlds"]:
                if w["system"]==system and nav["planet_visibility"][8*(system-1)+w["planet"]-1]<128:
                    choices[w["id"]+" - "+w["name"]]=[w[k] for k in ("system","planet","moon")]
        if not choices:raise GameError("No navigable destinations are known.")
        window=tk.Toplevel(self.root);window.title("Fleet route");window.geometry("580x230");window.minsize(520,210)
        body=ttk.Frame(window,padding=12);body.pack(fill="both",expand=True)
        ttk.Label(body,text="Choose a destination",font=("Segoe UI",12,"bold")).pack(anchor="w")
        selected=tk.StringVar(value=next(iter(choices)))
        ttk.Combobox(body,textvariable=selected,state="readonly",values=list(choices),width=55).pack(fill="x",pady=12)
        ttk.Label(body,text="Travel requires ships and a pilot; satellite carriers navigate independently. Interstellar routes also require suitable hulls and pilot rank.",wraplength=490).pack(anchor="w")
        context=self.watch_fleet(window)
        def travel():
            context.require(self.session)
            self.act("travel",fleet_index=index,destination=choices[selected.get()])
            window.destroy()
        ttk.Button(body,text="Set route",command=lambda:self.guard(travel)).pack(anchor="w",pady=12)
        return window

    def cargo_window(self,index):
        from .cargo import cargo_capacity,cargo_used
        from .fleets import local_record
        from .industry import world_stocks
        row=self.session.state["fleets"]["moving"][index]
        if row[0] not in (2,3):raise GameError("Select a Trade or Pirate fleet.")
        window=tk.Toplevel(self.root)
        window.title("Fleet cargo")
        window.geometry("760x580")
        window.minsize(650,500)
        body=ttk.Frame(window,padding=12)
        body.pack(fill="both",expand=True)
        details=tk.StringVar()
        ttk.Label(body,textvariable=details,wraplength=610).pack(anchor="w",pady=6)
        cargo=self.tree(body,("Cargo","Aboard","Depot","Weight/unit"),(230,100,100,100))
        controls=ttk.Frame(body)
        controls.pack(fill="x",pady=8)
        amount=tk.StringVar(value="1")
        ttk.Label(controls,text="Quantity:").pack(side="left")
        ttk.Entry(controls,textvariable=amount,width=9).pack(side="left",padx=6)
        def refresh():
            state=self.session.state
            row=state["fleets"]["moving"][index]
            identity=tuple(row[19:22]);home=identity==(1,5,0)
            world=state["worlds"].get(":".join(map(str,identity)))
            depot=[state["resources"][k] for k in ORE_KEYS] if home else world_stocks(world["raw"]) if world else [0]*6
            local=local_record(state["fleets"],identity)
            rules=self.catalog["cargo_rules"]
            details.set(f"Shared cargo weight: {cargo_used(row,rules):,} / {cargo_capacity(row,self.catalog):,}. "
                        +"Transfers require landing at an owned colony or outpost. Stored items also need a completed Space Port.")
            selected=cargo.selection()
            cargo.delete(*cargo.get_children())
            for i,key in enumerate(ORE_KEYS):
                aboard=struct.unpack_from("<I",bytes(row),109+4*i)[0]
                cargo.insert("","end",iid="ore:"+key,values=(key.capitalize(),aboard,depot[i],1))
            for item in rules["items"]:
                product=item["product"];slot=item["slot"]
                if product is None or state["products"][product-1]["research_state"]!=5:continue
                stock=state["products"][product-1]["stock"] if home else struct.unpack_from("<h",bytes(local),131+2*slot)[0] if local else 0
                cargo.insert("","end",iid=f"slot:{slot}",values=(self.catalog["products"][product-1]["name"],
                    struct.unpack_from("<h",bytes(row),131+2*slot)[0],stock,item["weight"]))
            if selected and cargo.exists(selected[0]):cargo.selection_set(selected[0])
        def transfer(sign,maximum=False):
            context.require(self.session)
            if not cargo.selection():raise GameError("Select an ore or stored item.")
            kind,key=cargo.selection()[0].split(":")
            quantity=1 if maximum else int(amount.get())
            if quantity<=0:raise GameError("Enter a positive quantity.")
            self.act("transfer_cargo",fleet_index=index,quantity=sign*quantity,maximum=maximum,
                     **{kind:int(key) if kind=="slot" else key})
            refresh()
        for label,sign in (("Load",1),("Unload",-1)):
            ttk.Button(controls,text=label,command=lambda s=sign:self.guard(lambda:transfer(s))).pack(side="left",padx=6)
        for label,sign in (("Load maximum",1),("Unload maximum",-1)):
            ttk.Button(controls,text=label,command=lambda s=sign:self.guard(lambda:transfer(s,True))).pack(side="left",padx=4)
        context=self.watch_fleet(window,refresh)
        refresh()
        return window

    def orbital_window(self):
        if not self.worlds.selection():
            raise GameError("Select a world first.")
        world_id=self.worlds.selection()[0]
        world,raw,identity=self.session._deployment_world(self.session.state,world_id)
        window=tk.Toplevel(self.root)
        window.title(f"Orbital support — {world['name']}")
        window.geometry("790x420")
        window.minsize(680,350)
        body=ttk.Frame(window,padding=12)
        body.pack(fill="both",expand=True)
        ttk.Label(body,text=f"Deploy at {world['name']}",font=("Segoe UI",13,"bold")).pack(anchor="w")
        details=tk.StringVar()
        ttk.Label(body,textvariable=details,wraplength=630).pack(anchor="w",pady=8)
        fleet_tree=self.tree(body,("Fleet","Role","Available","Miner stations","Solar","Survey","Spy sat","Spy ship"),
            (115,105,55,80,45,50,55,60),height=6)
        def refresh():
            selected=fleet_tree.selection()
            fleet_tree.delete(*fleet_tree.get_children())
            fleets=self.session.state["fleets"]
            for index,row in enumerate(fleets["moving"]):
                if row[0] not in (2,4) or row[19:21]!=list(identity[:2]):
                    continue
                cargo={"moving":[row],"local":[]}
                name=bytes(row[2:2+min(17,row[1])]).decode("cp437") or f"Fleet {index+1}"
                fleet_tree.insert("","end",iid=str(index),values=(name,"Transfer fleet" if row[0]==2 else "Satellite carrier",
                    "Yes" if row[22] in (1,2) else "No",*[payload_count(cargo,identity,kind) for kind in
                        ('miner_station','solar_satellite','survey_satellite','spy_satellite','spy_ship')]))
            if selected and fleet_tree.exists(selected[0]):
                fleet_tree.selection_set(selected[0])
            current=self.session.state["worlds"][world_id]["raw"]
            satellite='Spy' if current[8]==2 else 'Survey' if current[8]==1 else 'In transit' if current[8]>=128 else 'None'
            details.set(f"Deployed: satellite {satellite}; spy ship {'Yes' if current[9] else 'No'}; solar {current[11]}/5."
                +"\nStationary fleets support every moon of this planet. Select a fleet to use its cargo first."
                +"\nOrdinary survey satellites are lost on alien worlds. Spy ships require an alien world with survey 30 or more.")
        def deploy(action):
            context.require(self.session)
            chosen=fleet_tree.selection()
            self.act(action,world_id=world_id,fleet_index=int(chosen[0]) if chosen else None)
        controls=ttk.Frame(body)
        controls.pack(side='bottom',fill="x",pady=8,before=fleet_tree.master)
        for index,(label,action) in enumerate((("Deploy Miner station","deploy_station"),("Deploy solar satellite","deploy_solar_satellite"),
                ("Deploy survey satellite","deploy_survey_satellite"),("Deploy spy satellite","deploy_spy_satellite"),("Deploy spy ship","deploy_spy_ship"))):
            ttk.Button(controls,text=label,command=lambda a=action:self.guard(lambda:deploy(a))).grid(row=index//3,column=index%3,sticky='w',padx=(0,8),pady=3)
        context=self.watch_world(window,world,refresh,fleets=True)
        refresh()
        return window

    def world_detail(self):
        if not self.worlds.selection():
            self.world_details.set('Select a discovered world.' if self.worlds.get_children() else 'No discovered worlds match this filter.')
            self.world_buildings.delete(*self.world_buildings.get_children())
            return
        world_id = self.worlds.selection()[0]
        definition = next(w for w in self.catalog["worlds"] if w["id"]==world_id)
        info = describe_world(self.session.state["worlds"][world_id])
        buildings = [b for b in self.session.state["buildings"] if b[1:4]==[definition[k] for k in ("system","planet","moon")]]
        names = {b["id"]:b["name"] for b in self.catalog["buildings"]}
        ores=self.session.state["resources"] if world_id=="1:5:0" else info["ores"]
        raw=self.session.state["worlds"][world_id]["raw"]
        report=survey_information(raw,self.catalog)
        colony_status="yes" if info["colony"] else f"establishing ({raw[7]} days)" if raw[7] else "no"
        if info['owner']>=2:
            campaign=self.session.state['campaign'];forces=force_intelligence(raw,campaign['civilizations'],campaign['bar'])
            self.world_details.set(f"{definition['name']} | Survey: {info['survey_progress']} | Spy ship: {'Yes' if raw[9] else 'No'}"
                +("\nForces: "+(' | '.join(f"{self.catalog['products'][p-1]['name']} {count:,}" for p,count in forces.items()) or 'No known weapon types.') if forces is not None else
                  '\nForce intelligence unavailable. Deploy a spy ship after survey 30, or obtain a forces report from a Bar agent.' if report['survey']>=30 else ''))
        else:
            self._world_economy_details(definition,info,raw,buildings,ores,colony_status)
        self.world_details.set(self.world_details.get()+'\n'+environment_summary(report))
        self.world_buildings.delete(*self.world_buildings.get_children())
        for i,b in enumerate(self.session.state["buildings"]):
            if b[1:4]!=[definition[k] for k in ("system","planet","moon")]:
                continue
            self.world_buildings.insert("","end",iid=str(i),values=(names.get(b[0],"Type "+str(b[0])),f"{b[4]}, {b[5]}",b[7],
                f"Building ({b[6]} left)" if b[6] else "Yes" if b[8] else "No",b[9]+256*b[10],b[11]+256*b[12],b[13]))

    def _world_economy_details(self,definition,info,raw,buildings,ores,colony_status):
        from .colony import industrial_output
        offline=sum(b[6]==0 and not b[8] for b in buildings)
        industry=industrial_output(buildings,self.catalog['buildings'],tuple(definition[k] for k in ('system','planet','moon')))
        self.world_details.set(f"{definition['name']} | Colony: {colony_status} | Tax level: {info['tax_level']} | Morale: {info['morale']}"
            +f"\nSatellite stock: {self.session.state['products'][2]['stock']} | Buildings: {len(buildings)} | Assigned droids: {raw[10]}"
            +f" | Ore storage limit: {storage_limit(self.session.state['fleets'],tuple(definition[k] for k in ('system','planet','moon')),self.session.state['buildings']):,}"
            +"\n"+" | ".join(f"{key.capitalize()} {ores[key]:,}" for key in ORE_KEYS)
            +(f"\nBuilder output: {industry:,} | Offline buildings: {offline}"+(' — check colony power.' if offline else '') if info['owner']==1 and info['colony'] else ''))

    def survey_window(self):
        if not self.worlds.selection():raise GameError("Select a discovered world first.")
        world_id=self.worlds.selection()[0]
        definition=next(w for w in self.catalog['worlds'] if w['id']==world_id)
        session=self.session
        window=tk.Toplevel(self.root);window.title(definition['name']+' — Survey report')
        window.geometry('680x440');window.minsize(560,400)
        body=ttk.Frame(window,padding=12);body.pack(fill='both',expand=True)
        title=tk.StringVar();details=tk.StringVar()
        ttk.Label(body,textvariable=title,font=('Segoe UI',12,'bold')).pack(anchor='w')
        label=ttk.Label(body,textvariable=details,wraplength=640);label.pack(anchor='w',pady=10)
        ores=self.tree(body,('Ore','Deposit detected','Abundance'),(190,170,110),height=6)
        ttk.Label(body,text='Higher abundance means richer deposits. Your stored ore is listed separately in Worlds.',
                  wraplength=520).pack(anchor='w',pady=(8,0))
        race_button=ttk.Button(body,text='Race profile',command=lambda:self.guard(lambda:self.race_window(world_id)))
        race_button.pack(anchor='w',pady=(8,0))
        def refresh():
            state=self.session.state
            if self.session is not session or not world_visible(state,definition):
                window.destroy();return
            report=survey_information(state['worlds'][world_id]['raw'],self.catalog)
            race_button.configure(state='normal' if revealed_race(state['worlds'][world_id]['raw']) else 'disabled')
            title.set(f"{definition['name']} | Survey {report['survey']}/60 | {owner_label(report,self.catalog)}")
            diameter=f"{report['diameter_km']:,} km" if report['diameter_km'] is not None else 'unknown (survey 3)'
            habitat=('Supports human life' if report['habitable'] else 'Unsuitable for human colonies') if report['habitable'] is not None else 'unknown (survey 20)'
            population=f"{report['population']:,}" if report['population'] is not None else 'unknown (survey 40)'
            details.set(environment_summary(report)+f'\nDiameter: {diameter}\nHabitability: {habitat}\nPopulation: {population}')
            ores.delete(*ores.get_children())
            for key in ORE_KEYS:
                present=report['ore_presence'];abundance=report['ore_abundance']
                ores.insert('','end',iid=key,values=(self.catalog['ore_names'][key],
                    'Unknown (survey 10)' if present is None else 'Yes' if present[key] else 'No',
                    'Unknown' if abundance is None else abundance[key]))
        window.bind('<Configure>',lambda event:label.configure(wraplength=max(200,event.width-32)) if event.widget==window else None,add='+')
        self.watch_session(window,refresh);refresh()
        return window

    def race_window(self,world_id):
        definition=next(w for w in self.catalog['worlds'] if w['id']==world_id)
        if not world_visible(self.session.state,definition):raise GameError('Select a discovered world first.')
        session=self.session;owner=revealed_race(session.state['worlds'][world_id]['raw'])
        if owner is None:raise GameError('An alien race profile requires survey 40.')
        profile=self.content.race_profile(owner)
        data,_,_=self.content.picture(f'ALIEN/ALIEN{owner}.PIC')
        photo=tk.PhotoImage(data=data,format='png',master=self.root).zoom(2)
        window=tk.Toplevel(self.root);window.title(definition['name']+' — Race profile')
        window.geometry('680x440');window.minsize(580,430)
        body=ttk.Frame(window,padding=12);body.pack(fill='both',expand=True)
        ttk.Label(body,text=profile['title'],font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,10))
        content=ttk.Frame(body);content.pack(fill='both',expand=True)
        portrait=ttk.Label(content,image=photo);portrait.image=photo;portrait.pack(side='left',anchor='n',padx=(0,16))
        text=ttk.Label(content,text=profile['description'],wraplength=420,justify='left');text.pack(side='left',anchor='n',fill='x',expand=True)
        forces=tk.StringVar();force_label=ttk.Label(body,textvariable=forces,wraplength=640)
        force_label.pack(anchor='w',pady=(10,0))
        def refresh():
            if self.session is not session or not world_visible(self.session.state,definition):window.destroy();return
            raw=session.state['worlds'][world_id]['raw']
            if revealed_race(raw)!=owner:window.destroy();return
            campaign=session.state['campaign'];known=force_intelligence(raw,campaign['civilizations'],campaign['bar'])
            forces.set('Forces at '+definition['name']+': '+
                ('Intelligence unavailable. Deploy a spy ship or obtain a forces report from a Bar agent.' if known is None else
                 ' | '.join(f"{self.catalog['products'][p-1]['name']} {n:,}" for p,n in known.items()) or 'No known weapon types.'))
        def resize(event):
            if event.widget==window:
                text.configure(wraplength=max(240,event.width-240));force_label.configure(wraplength=max(300,event.width-32))
        window.bind('<Configure>',resize,add='+')
        self.watch_session(window,refresh);refresh()
        return window

    def surface_window(self):
        if not self.worlds.selection():
            raise GameError("Select a colony first.")
        world_id=self.worlds.selection()[0]
        self.act("prepare_surface",world_id=world_id)
        world,raw,identity=self.session._surface_colony(self.session.state,world_id)
        choices=[b for b in self.catalog["buildings"] if b["id"] not in (1,25)
                 and building_available(b,raw,self.session.state["products"],self.session.state["levels"]["builder"])]
        if not choices:
            raise GameError("No structures are available to build yet.")
        width,height,blocked=occupancy(self.catalog,raw,self.session.state["buildings"],identity)
        window=tk.Toplevel(self.root)
        window.title(f"{world['name']} — Colony construction")
        body=ttk.Frame(window,padding=12)
        body.pack(fill="both",expand=True)
        ttk.Label(body,text="Choose a building, then click its top-left tile. Grey cells are blocked terrain or existing structures.").pack(anchor="w")
        selection=tk.StringVar(value=f"{choices[0]['id']}: {choices[0]['name']}")
        combo=ttk.Combobox(body,textvariable=selection,values=[f"{b['id']}: {b['name']}" for b in choices],state="readonly",width=32)
        combo.pack(anchor="w",pady=6)
        detail=tk.StringVar()
        ttk.Label(body,textvariable=detail).pack(anchor="w")
        scale=min(14,640//max(width,height))
        canvas=tk.Canvas(body,width=width*scale,height=height*scale,highlightthickness=0)
        canvas.pack(pady=8)
        position=[1,1]
        def redraw(*_):
            context.require(self.session)
            current=self.session.state["worlds"][world_id]["raw"]
            _,_,blocked_now=occupancy(self.catalog,current,self.session.state["buildings"],identity)
            choices[:]=[b for b in self.catalog['buildings'] if b['id'] not in (1,25)
                and building_available(b,current,self.session.state['products'],self.session.state['levels']['builder'])]
            values=[f"{b['id']}: {b['name']}" for b in choices];combo.configure(values=values)
            if selection.get() not in values:selection.set('')
            canvas.delete("all")
            for y in range(height):
                for x in range(width):
                    canvas.create_rectangle(x*scale,y*scale,(x+1)*scale,(y+1)*scale,fill="#66717b" if blocked_now[y*width+x] else "#dee8d4",outline="#a4b09e")
            if not selection.get():
                detail.set('Select an available building.');build_button.configure(state='disabled');return
            definition=next(b for b in choices if b['id']==int(selection.get().split(':')[0]))
            fits=placement_fits(definition,*position,width,height,blocked_now)
            for x,y in footprint(definition,*position):
                if 1<=x<=width and 1<=y<=height:
                    canvas.create_rectangle((x-1)*scale,(y-1)*scale,x*scale,y*scale,outline="#168448" if fits else "#cc3333",width=3)
            detail.set(f"Cost: {definition['price']:,} credits | Footprint: {definition['width']} × {definition['height']} | Position: {position[0]}, {position[1]} | {'Clear' if fits else 'Blocked'}")
            build_button.configure(state='normal' if fits and self.session.state['resources']['credits']>=definition['price'] else 'disabled')
        def choose(event):
            position[:]=[max(1,min(width,event.x//scale+1)),max(1,min(height,event.y//scale+1))]
            redraw()
        def construct():
            context.require(self.session)
            if not selection.get():raise GameError('Select an available building.')
            self.act("build",world_id=world_id,building_id=int(selection.get().split(":")[0]),x=position[0],y=position[1])
        canvas.bind("<Button-1>",choose)
        combo.bind("<<ComboboxSelected>>",redraw)
        build_button=ttk.Button(body,text="Start construction",command=lambda:self.guard(construct));build_button.pack(anchor="w")
        context=self.watch_world(window,world,redraw)
        redraw()
        return window

    def colonize_window(self):
        if not self.worlds.selection():
            raise GameError("Select a world first.")
        world_id=self.worlds.selection()[0]
        world=next(w for w in self.catalog["worlds"] if w["id"]==world_id)
        window=tk.Toplevel(self.root)
        window.title(f"Colonize {world['name']}")
        body=ttk.Frame(window,padding=14)
        body.pack(fill="both",expand=True)
        ttk.Label(body,text=f"Establish a colony on {world['name']}",font=("Segoe UI",13,"bold")).pack(anchor="w")
        ttk.Label(body,text="Requires Control Centre research, survey 30, suitable terrain and builder rank 2 (systems 1–2) or rank 3.",wraplength=460).pack(anchor="w",pady=8)
        ttk.Label(body,text="Base cost: 100,000 credits. Optional buildings arrive after the site is established.",wraplength=460).pack(anchor="w")
        definitions={b["id"]:b for b in self.catalog["buildings"]}
        choices={kind:tk.BooleanVar(value=False) for kind in self.catalog["settlement_options"]}
        total=tk.StringVar()
        def update_cost():
            context.require(self.session)
            total.set(f"Total: {100000+sum(definitions[k]['price'] for k,v in choices.items() if v.get()):,} credits"
                +f"\nAvailable: {self.session.state['resources']['credits']:,} credits")
        for kind,value in choices.items():
            ttk.Checkbutton(body,text=f"{definitions[kind]['name']} (+{definitions[kind]['price']:,} credits)",variable=value,command=update_cost).pack(anchor="w",pady=2)
        ttk.Label(body,textvariable=total).pack(anchor="w",pady=8)
        def begin():
            context.require(self.session)
            self.act("colonize",world_id=world_id,options=[k for k,v in choices.items() if v.get()])
            if window.winfo_exists():window.destroy()
        ttk.Button(body,text="Start colonization",command=lambda:self.guard(begin)).pack(anchor="w")
        context=self.watch_world(window,world,update_cost)
        update_cost()
        return window

    def build_art(self):
        tab = self.tabs["Original artwork"]
        self.picture_choice = tk.StringVar()
        paths = self.content.pictures()
        combo = ttk.Combobox(tab,textvariable=self.picture_choice,values=paths,state="readonly",width=60)
        combo.pack(anchor="w")
        combo.bind("<<ComboboxSelected>>",lambda _:self.guard(self.show_picture))
        self.picture_label = ttk.Label(tab,anchor="center")
        self.picture_label.pack(fill="both",expand=True,pady=8)
        self.picture_info = tk.StringVar(value="Choose an original PIC image. Unsupported formats and malformed files are reported explicitly.")
        ttk.Label(tab,textvariable=self.picture_info,wraplength=1050).pack(anchor="w")
        if "GRAFIKA/MAIN.PIC" in paths:
            self.picture_choice.set("GRAFIKA/MAIN.PIC")
            self.show_picture()

    def show_picture(self):
        data,width,height = self.content.picture(self.picture_choice.get())
        photo = tk.PhotoImage(data=data,format="png",master=self.root)
        factor = min(3,900//width,410//height)
        if factor>1:
            photo = photo.zoom(factor)
        self.photo = photo
        self.picture_label.configure(image=photo)
        self.picture_info.set(f"{self.picture_choice.get()} — {width} × {height}; original indexed palette, integer scaling.")

    def build_text(self):
        tab = self.tabs["Original text"]
        self.text_choice = tk.StringVar(value="MESSAGE.TXT")
        choices = self.content.texts()
        combo = ttk.Combobox(tab,textvariable=self.text_choice,values=choices,state="readonly",width=55)
        combo.pack(anchor="w")
        combo.bind("<<ComboboxSelected>>",lambda _:self.guard(self.show_text))
        self.text = tk.Text(tab,wrap="word",height=20,font=("Consolas",10))
        self.text.pack(fill="both",expand=True,pady=8)
        ttk.Label(tab,text="Record numbers, dialog prefixes and | layout markers are preserved. Play conversations through the Bar tab or Conversation window.").pack(anchor="w")
        self.show_text()

    def show_text(self):
        lines = self.content.text(self.text_choice.get())
        self.text.configure(state="normal")
        self.text.delete("1.0","end")
        self.text.insert("end","\n\n".join(f"{i:03d}  {line}" for i,line in enumerate(lines,1)))
        self.text.configure(state="disabled")

    def build_admin(self):
        tab = self.tabs["Admin & log"]
        self.admin = tk.BooleanVar(value=False)
        ttk.Checkbutton(tab,text="Enable admin changes for this session",variable=self.admin).pack(anchor="w")
        ttk.Label(tab,text="Examples: give credits 100000 | give texon 5000 | set lepitium 500 | stock 2 10").pack(anchor="w",pady=8)
        row = ttk.Frame(tab)
        row.pack(fill="x")
        self.command = tk.StringVar(value="give credits 100000")
        entry = ttk.Entry(row,textvariable=self.command)
        entry.pack(side="left",fill="x",expand=True)
        entry.bind("<Return>",lambda _:self.guard(lambda:self.act("admin",command=self.command.get())))
        ttk.Button(row,text="Run",command=lambda:self.guard(lambda:self.act("admin",command=self.command.get()))).pack(side="left",padx=6)
        self.log = tk.Text(tab,wrap="word",height=20)
        self.log.pack(fill="both",expand=True,pady=8)
        self.event_text = {"message":self.content.text("MESSAGE.TXT"),"idea":self.content.text("KITALAL.TXT")}

    def refresh(self):
        self.outcome_panel.refresh()
        self.clock_panel.refresh()
        self.sound.set((self.session.effects or {'enabled':True})['enabled'])
        self.bar_panel.refresh()
        s = self.session.state
        y,m,d,h = s["date"]
        self.summary.set(f"{y:04d}-{m:02d}-{d:02d}  {h:02d}:00  |  Credits {s['resources']['credits']:,}  |  Workforce {s['workforce']}"
                         +(" | Campaign ended: New Earth lost" if self.session.defeated() else "")
                         +(" | Campaign won" if s["campaign_phase"]=="victory" else "")
                         +"\n"+"   ".join(f"{self.catalog['ore_names'][k]} {s['resources'][k]:,}" for k in ORE_KEYS))
        selected = self.products.selection()
        self.products.delete(*self.products.get_children())
        for row,p in zip(s["products"],self.catalog["products"]):
            self.products.insert("","end",iid=str(p["id"]),values=(p["id"],p["name"],STATES[row["research_state"]],
                f"{(10000-row['research_remaining'])/100:.0f}%",f"{p['price']:,}",row["stock"],row["queued"],row["work_remaining"]))
        if selected:
            self.products.selection_set(selected)
        self.product_detail()
        self.commander_status.set("Hired commanders: "+", ".join(f"{r}: rank {s['ranks'][r]}, level {s['levels'][r]}" for r in ROLES)
            +"\nDeveloper skills: "+", ".join(f"{k.replace('_',' ')} {s['skills'][k]}" for k in SUBJECTS))
        for i,c in enumerate(self.catalog["commanders"]):
            hired=s["ranks"][c["role"]]==c["rank"]
            self.commanders.item(str(i),values=(c["role"],c["rank"],c["name"]+(" (hired)" if hired else ""),f"{c['hire_price']:,}",
                s["levels"][c["role"]] if hired else s["campaign"]["commander_levels"][i],self.catalog["training_rules"]["level_caps"][i]))
        campaign=s["campaign"];training=campaign["training"];quote=training["quote"]
        if campaign["training_role"]:
            role=ROLES[campaign["training_role"]-1]
            text=f"{role.title()} at university: {campaign['training_remaining']} hours remaining."
            if role=="developer":text+=" "+COURSES[training["course"]-1]+"."
        elif quote:
            course=COURSES[quote["course"]-1] if quote["course"] else "General training"
            text=f"Quote: {quote['role']} rank {quote['rank']}, {course}; {quote['cost']:,} credits, 50-69 hours."
        else:text="Select a hired role and request a quote. Course selection applies to developers."
        if s["ranks"]["developer"]:
            caps=skill_limits(self.catalog["training_rules"],training["phase"],s["ranks"]["developer"])
            text+="\nCurrent developer skill limits: "+", ".join(f"{k.replace('_',' ')} {v}" for k,v in zip(SUBJECTS,caps))+"."
        self.training_status.set(text)
        self.training_buy.configure(state="normal" if quote and not self.session.defeated() else "disabled")
        selected_world = self.worlds.selection()
        self.worlds.delete(*self.worlds.get_children())
        for world,label in filtered_worlds(s,self.catalog,self.world_filter.get()):
            info = describe_world(s["worlds"][world["id"]])
            report=survey_information(s['worlds'][world['id']]['raw'],self.catalog)
            satellite = "In transit" if info["satellite"]<0 else "Active" if info["satellite"] else "None"
            self.worlds.insert("","end",iid=world["id"],values=(world["name"],world["id"],owner_label(report,self.catalog),satellite,info["survey_progress"],
                f"{report['population']:,}" if report['population'] is not None else 'Unknown',label))
        choice = selected_world[0] if selected_world else '1:5:1' if self.first_world_refresh else ''
        self.first_world_refresh=False
        if choice and self.worlds.exists(choice):
            self.worlds.selection_set(choice)
            self.worlds.see(choice)
        self.world_count.set(f'{len(self.worlds.get_children())} worlds')
        self.world_detail()
        self.log.configure(state="normal")
        self.log.delete("1.0","end")
        self.log.insert("end","\n".join(s["log"]).replace("|","\n"))
        for event in s["events"]:
            from .mission_messages import append_report_text
            text = '' if event['kind']=='report' else self.event_text[event['kind']][event['id']-1].replace('|','\n')
            text = append_report_text(text,event)
            self.log.insert("end",f"\n\n{event['date']} — {event['kind']} {event['id']}\n{text}")
        self.log.see("end")
        self.log.configure(state="disabled")
        for callback in tuple(self.refresh_listeners):callback()

    def new_game(self,*,hero=2):
        self.pause_battles()
        candidate = self.content.new_game(hero=hero)
        self.effects.prepare(candidate)
        self.music_panel.capture()
        previous = self.save_dir/'recovered-before-new-game.json'
        self.session.save(previous)
        self.session = candidate
        self.admin.set(False)
        self.refresh()
        self.status.set(f'New game started. Previous session saved to {previous}')

    def import_save(self):
        self.pause_battles()
        path = filedialog.askopenfilename(parent=self.root,initialdir=self.installation/"SAVE",title="Import recovered fields from a DOS save")
        if path:
            candidate = RecoveredSession.from_dos(self.catalog,path)
            self.music_panel.capture()
            self.session.save(self.save_dir/"recovered-before-import.json")
            self.session = candidate
            self.admin.set(False)
            self.refresh()

    def save(self):
        self.pause_battles()
        path = filedialog.asksaveasfilename(parent=self.root,initialdir=self.save_dir,defaultextension=".json",filetypes=[("Recovered session","*.json")])
        if path:self.save_path(path)

    def save_path(self,path):
        self.pause_battles()
        self.music_panel.capture()
        self.session.save(path)
        self.status.set(f"Saved {path}")

    def load(self):
        self.pause_battles()
        path = filedialog.askopenfilename(parent=self.root,initialdir=self.save_dir,filetypes=[("Recovered session","*.json")])
        if path:self.load_path(path)

    def load_path(self,path):
        self.pause_battles()
        candidate = RecoveredSession.load(self.catalog,path)
        self.effects.prepare(candidate)
        self.music_panel.capture()
        self.session.save(self.save_dir/"recovered-before-load.json")
        self.session = candidate
        self.admin.set(False)
        self.refresh()
        if (candidate.state["campaign"]["bar"] or {}).get("conversation") is not None:
            self.book.select(self.tabs["Bar"])
        elif candidate.state['active_scene'] is not None or candidate.state['active_dialog'] is not None or candidate.state['presentation_requests']:
            self.show_presentation(autoplay=False)

    def close(self):
        self.pause_battles()
        try:
            self.music_panel.capture()
            self.session.save(self.save_dir/"recovered-autosave.json")
        except (GameError,OSError) as exc:
            messagebox.showerror("Session could not be saved",str(exc),parent=self.root)
            return
        try:
            self.music_panel.close()
            self.effects.close()
        except GameError as exc:
            messagebox.showerror("Audio could not be stopped",str(exc),parent=self.root)
            return
        self.root.destroy()

    def show_ground_battle(self):
        if self.session.state["ground_encounter"] is None:raise GameError("There is no ground battle to resume.")
        if self.ground_window is not None:
            self.ground_window.window.lift();self.ground_window.refresh();return
        from .ground_ui import GroundWindow
        self.ground_window=GroundWindow(self)

    def show_conversation(self):
        if self.session.state["active_dialog"] is None:raise GameError("No conversation is waiting for a response.")
        if self.dialog_window is not None:self.dialog_window.window.lift();self.dialog_window.refresh();return
        from .dialog_ui import DialogWindow
        self.dialog_window=DialogWindow(self)

    def show_presentation(self,*,autoplay=True):
        state=self.session.state
        if state['active_scene'] is None and state['active_dialog'] is None and state['presentation_requests']:
            self.session.apply('start_presentation');self.refresh();state=self.session.state
        if state['active_dialog'] is not None:self.show_conversation();return
        if state['active_scene'] is None and not state['presentation_requests']:
            self.status.set('No story presentation is waiting.');return
        if self.scene_window is None:
            from .scene_ui import SceneWindow
            self.scene_window=SceneWindow(self)
        else:self.scene_window.window.lift();self.scene_window.refresh()
        current=state['active_scene']
        if autoplay and current is not None and current['notice'] is None and current['playback']['ticks']==0:self.scene_window.play()

    def pause_battles(self):
        self.clock_panel.clock.pause()
        self.effects.pause()
        if self.scene_window is not None:self.scene_window.pause()
        if self.ground_window is not None:self.ground_window.pause()
        if self.space_window is not None:self.space_window.pause()

    def show_space_battle(self):
        if self.session.state["space_encounter"] is None:raise GameError("There is no space battle to resume.")
        if self.space_window is not None:
            self.space_window.window.lift();self.space_window.refresh();return
        from .space_ui import SpaceWindow
        self.space_window=SpaceWindow(self)


def play(installation,save=None):
    root = tk.Tk()
    try:
        RecoveredApp(root,installation,save)
        root.mainloop()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
