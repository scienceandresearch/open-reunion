"""Bar visitors and saved .LOC conversations in the native campaign client."""
import tkinter as tk
from tkinter import ttk
from .bar import agent_status
from .bar_dialogs import available_agents,choices,answer_text,question_text
from .strategy import campaign_work


class BarPanel:
    def __init__(self,app,parent):
        self.app=app
        left=ttk.Frame(parent,width=235);left.pack(side="left",fill="y",padx=(0,14))
        ttk.Label(left,text="Space Local",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,10))
        self.people=ttk.Treeview(left,columns=("name","state"),show="headings",selectmode="browse",height=10)
        self.people.heading("name",text="Visitor");self.people.heading("state",text="Status")
        self.people.column("name",width=125,stretch=False);self.people.column("state",width=95,stretch=False)
        self.people.pack(fill="y",expand=True)
        self.talk=ttk.Button(left,text="Talk",command=lambda:app.guard(self.begin));self.talk.pack(fill="x",pady=8)
        self.people.bind("<<TreeviewSelect>>",lambda _:self.update_talk())
        self.info=tk.StringVar();ttk.Label(left,textvariable=self.info,wraplength=220).pack(anchor="w",pady=6)
        right=ttk.Frame(parent);right.pack(side="left",fill="both",expand=True)
        self.heading=tk.StringVar(value="Choose someone to talk to.")
        ttk.Label(right,textvariable=self.heading,font=("Segoe UI",13,"bold")).pack(anchor="w",pady=(0,8))
        self.text=tk.Text(right,wrap="word",height=7,font=("Segoe UI",11),padx=10,pady=8,state="disabled")
        self.text.pack(fill="both",expand=True)
        holder=ttk.Frame(right);holder.pack(fill="both",expand=True,pady=8)
        self.canvas=tk.Canvas(holder,height=220,highlightthickness=0)
        scroll=ttk.Scrollbar(holder,orient="vertical",command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set);scroll.pack(side="right",fill="y");self.canvas.pack(side="left",fill="both",expand=True)
        self.options=ttk.Frame(self.canvas);self.item=self.canvas.create_window(0,0,anchor="nw",window=self.options)
        self.options.bind("<Configure>",lambda _:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",self.resize)
        footer=ttk.Frame(right);footer.pack(fill="x")
        self.continue_button=ttk.Button(footer,text="Continue",command=lambda:app.guard(lambda:app.act("bar_acknowledge")))
        self.continue_button.pack(side="left")
        self.leave=ttk.Button(footer,text="Leave conversation",command=lambda:app.guard(lambda:app.act("bar_leave")))
        self.leave.pack(side="left",padx=8)

    def resize(self,event):
        self.canvas.itemconfigure(self.item,width=event.width)
        for child in self.options.winfo_children():
            if isinstance(child,tk.Button):child.configure(wraplength=max(120,event.width-32))

    def begin(self):
        selected=self.people.selection()
        if selected:self.app.act("bar_talk",agent=int(selected[0]))

    def update_talk(self):
        work=campaign_work(self.app.session.state);bar=work["bar"]
        selected=self.people.selection()
        enabled=bar is not None and bar["conversation"] is None and selected and int(selected[0]) in available_agents(work)
        self.talk.configure(state="normal" if enabled else "disabled")

    def refresh(self):
        state=self.app.session.state;bar=state["campaign"]["bar"];current=(bar or {}).get("conversation")
        work=campaign_work(state);available=available_agents(work)
        selection=self.people.selection();self.people.delete(*self.people.get_children())
        names={}
        if bar is not None:
            for index,row in enumerate(bar["agents"],1):
                if index==8:continue
                prefix=row["prefix"];name=bytes(prefix[1:1+min(prefix[0],13)]).decode("cp437").strip() or f"Visitor {index}"
                names[index]=name
                if index in available or row["remaining"]>0 and agent_status(work,index) in (0,2):
                    self.people.insert("","end",iid=str(index),values=(name,"Available" if index in available else f"{row['remaining']} hours"))
        if selection and self.people.exists(selection[0]):self.people.selection_set(selection)
        elif self.people.get_children():self.people.selection_set(self.people.get_children()[0])
        self.update_talk()
        self.leave.configure(state="normal" if current else "disabled")
        self.continue_button.configure(state="normal" if current and current["phase"]=="answer" else "disabled")
        self.info.set("Time pauses during a conversation. Purchases take effect when you choose a response." if bar is not None and bar["social"] is not None else
                      "This older session lacks bar knowledge records. Import a DOS save to recover them.")
        if current is None:
            self.heading.set("Choose someone to talk to.");text=""
        else:
            self.heading.set(names[current["agent"]]);rules=self.app.catalog["bar_dialogs"]
            text=answer_text(current,rules)
        self.text.configure(state="normal");self.text.delete("1.0","end");self.text.insert("end",text);self.text.configure(state="disabled")
        # Rebuild even after loading a different session with the same choice;
        # callbacks always refer to the current transactional session.
        for child in self.options.winfo_children():child.destroy()
        if current and current["phase"]=="choices":
            for question in choices(work,rules,current):
                button=tk.Button(self.options,text=question_text(current,question,rules),anchor="w",justify="left",
                    wraplength=max(120,self.canvas.winfo_width()-32),padx=10,pady=6,
                    command=lambda q=question:self.app.guard(lambda:self.app.act("bar_answer",question=q)))
                button.pack(fill="x",pady=3)
        self.canvas.yview_moveto(0)
