"""Live Tk input and timer verification, also executed in the frozen runtime."""
from copy import deepcopy
import time
from unittest.mock import patch


def check_graphical_clock(app):
    from openreunion.dos.session import RecoveredSession
    root=app.root;clock=app.clock_panel.clock;hours=[]
    was_withdrawn=root.state()=='withdrawn'
    if was_withdrawn:root.deiconify()
    original_act=app.act
    def act(action,**kwargs):
        manual=None
        if action=='advance':
            manual=RecoveredSession(app.catalog,deepcopy(app.session.state))
            manual.apply(action,**kwargs)
        result=original_act(action,**kwargs)
        if manual is not None:
            assert app.session.state==manual.state,'Live tick differs from a manual hour'
            hours.append(list(app.session.state['date']))
        return result
    app.act=act
    def pump(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:root.update();time.sleep(.005)
    def until(test,timeout=8):
        end=time.monotonic()+timeout
        while not test():
            assert time.monotonic()<end,'Live graphical timer timed out'
            root.update();time.sleep(.005)
    def click(x,y,button=1):
        ox,oy=app.origin
        for kind in ('Press','Release'):
            app.original.event_generate(f'<Button{kind}-{button}>',x=ox+x*app.scale,y=oy+y*app.scale)
        root.update()
    def stopped():
        state=deepcopy(app.session.state);pump(.2)
        assert not clock.running and clock.pending is None and app.session.state==state
        assert 'Paused' in app.clock_bar.message.get() or 'paused' in app.clock_bar.message.get()
    try:
        root.update();app.show_original();app.original.focus_force();root.update()
        assert not clock.running and app.clock_bar.run['text']=='Run (Space)'
        app.act('hire',role='developer',rank=1);app.act('research',product_id=2)
        remaining=app.session.state['products'][1]['research_remaining']
        # Date-box mouse input; wait for scheduled callbacks, never call tick directly.
        click(260,39);assert clock.running
        until(lambda:len(hours)>=3);click(260,39);stopped()
        assert len(hours)==3 and app.session.state['products'][1]['research_remaining']<remaining
        assert hours[0]==[2927,8,14,0],'Fresh game must cross midnight'
        # Actual Space binding and visible button use the same single timer.
        app.original.event_generate('<KeyPress-space>');root.update()
        assert clock.running and app.clock_bar.run['text']=='Pause (Space)'
        until(lambda:len(hours)>=5);app.clock_bar.run.invoke();stopped()
        for label,count in (('1x',1),('12x',3)):
            app.clock_bar.speed.set(label);app.clock_bar.selector.event_generate('<<ComboboxSelected>>')
            start=len(hours);app.clock_bar.run.invoke();until(lambda:len(hours)>=start+count)
            app.clock_bar.run.invoke();stopped();assert len(hours)==start+count
        # Time is deliberately blocked while placing a structure; explain why.
        app.open_surface('1:5:0');app.surface_view.selected=4
        app.dispatch(('surface_mode','build'));root.update()
        assert 'placement' in app.clock_bar.message.get()
        assert app.clock_bar.run.instate(['disabled'])
        click(260,39);stopped()
        app.dispatch(('surface_tile',20,16),3)
        assert not app.clock_bar.run.instate(['disabled'])
        # Order editing is similarly paused and explained.
        app.show_original('production');app.production_view.quantity=1;app.render_original()
        click(260,39);stopped();assert 'production order' in app.clock_bar.message.get()
        app.show_original()
        # Actual Save/Load dialog path stops the live clock before replacing state.
        saved=app.save_dir/'graphical-clock-check.json'
        app.clock_bar.run.invoke()
        with patch('openreunion.dos.ui.filedialog.asksaveasfilename',return_value=str(saved)):app.save()
        stopped();saved_state=deepcopy(app.session.state)
        app.clock_bar.run.invoke();start=len(hours);until(lambda:len(hours)>start)
        with patch('openreunion.dos.ui.filedialog.askopenfilename',return_value=str(saved)):app.load()
        stopped();assert app.session.state==saved_state
        # Loaded pending presentations must show their reason instead of appearing frozen.
        session=app.session;fixture=deepcopy(session.state)
        fixture['presentation_requests'].append({'kind':'message','id':1})
        app.session=RecoveredSession(app.catalog,fixture)
        app.clock_bar.refresh()
        assert app.clock_bar.run.instate(['disabled']) and 'Story needs attention' in app.clock_bar.message.get()
        app.session=session;app.clock_bar.refresh()
        return {'passed':True,'live_hours_checked':len(hours),'date_box':True,'space_key':True,
                'visible_run_pause':True,'three_speeds':True,'research_progress':True,
                'manual_hour_equality':True,'midnight':True,'placement_order_pause_feedback':True,
                'save_load_paused':True,'pending_story_feedback_fixture':True,
                'assisted':app.session.state['assisted']}
    finally:
        app.act=original_act;clock.pause()
        if was_withdrawn:root.withdraw()


def main():
    import argparse,json,sys,tempfile,tkinter as tk
    from pathlib import Path
    project=Path(__file__).resolve().parents[1];sys.path.insert(0,str(project/'src'))
    from openreunion.dos.original_ui import OriginalApp
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('sources',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(project):p.error('Choose a new report under opensource')
    results=[]
    for source in a.sources:
        root=tk.Tk();errors=[];root.report_callback_exception=lambda *e:errors.append(str(e))
        app=None
        try:
            with tempfile.TemporaryDirectory() as tmp,patch('openreunion.dos.ui.messagebox.showerror') as box:
                app=OriginalApp(root,source);app.save_dir=Path(tmp)
                result=check_graphical_clock(app);assert not errors and not box.called,(errors,box.call_args)
                results.append({'source':str(source),**result})
        finally:
            if app is not None:app.close()
    a.output.write_text(json.dumps({'passed':True,'adapters':results},indent=2)+'\n')


if __name__=='__main__':main()
