"""Original scripted conversation text and choices over session transactions."""
import tkinter as tk
from tkinter import ttk


class DialogWindow:
    def __init__(self,app):
        self.app=app;self.last=None
        self.window=tk.Toplevel(app.root);self.window.title("Conversation")
        self.window.geometry("780x580");self.window.minsize(620,480)
        self.window.protocol("WM_DELETE_WINDOW",self.window.destroy)
        body=ttk.Frame(self.window,padding=16);body.pack(fill="both",expand=True)
        ttk.Label(body,text="Incoming conversation",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,10))
        self.text=tk.Text(body,wrap="word",height=10,font=("Segoe UI",12),padx=12,pady=12)
        self.text.pack(fill="both",expand=True)
        self.choices=ttk.Frame(body);self.choices.pack(fill="x",pady=12)
        footer=ttk.Frame(body);footer.pack(fill="x")
        for label,callback in (("Save session",app.save),("Load session",app.load),("Close window",self.window.destroy)):
            ttk.Button(footer,text=label,command=lambda fn=callback:app.guard(fn)).pack(side="left",padx=4)
        self.window.bind("<Destroy>",self.destroyed,add="+")
        app.watch_session(self.window,self.refresh);self.refresh()

    def destroyed(self,event):
        if event.widget==self.window and self.app.dialog_window is self:self.app.dialog_window=None

    def refresh(self):
        current=self.app.session.state["active_dialog"]
        if current is None:self.window.destroy();return
        if current==self.last:return
        self.last=dict(current);definition=self.app.catalog["dialogs"][str(current["script"])]
        # The original initializer draws choices before it ever reads VALASZ.
        # Answer record one is a routing marker, not an opening speech.
        answer=definition["answers"][current["answer"]-1]["text"] if current["answer"] else ""
        self.text.configure(state="normal");self.text.delete("1.0","end");self.text.insert("end",answer);self.text.configure(state="disabled")
        for child in self.choices.winfo_children():child.destroy()
        if current["closed"]:
            ttk.Button(self.choices,text="Continue",command=lambda:self.app.guard(lambda:self.app.act("dialog_acknowledge"))).pack(anchor="w")
        else:
            for question in definition["nodes"][current["node"]]:
                # Native buttons wrap original multiline responses at the
                # minimum width; text routing codes are never player-facing.
                tk.Button(self.choices,text=definition["questions"][question-1]["text"],anchor="w",justify="left",
                    wraplength=560,padx=10,pady=6,command=lambda q=question:self.app.guard(lambda:self.app.act("dialog_answer",question=q))).pack(fill="x",pady=3)
