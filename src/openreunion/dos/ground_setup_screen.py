"""Original GRBEOSZT deployment grid, targets and contextual menu."""
import struct
from tkinter import ttk
from ..core import GameError
from .production_screen import display_number

ADD_ACTIONS={12:1,19:2,44:3,36:4}
DEPLOY_NAMES=('Trooper','Battle tank','Aircraft','Rocket launcher')


def setup_encounter(state):
    encounter=state['ground_encounter']
    if not encounter or encounter['phase']!='setup':raise GameError('Ground deployment is no longer active.')
    return encounter


def setup_buttons(state):
    encounter=setup_encounter(state)
    return [11]+([42] if encounter['player_attacking'] else [])+[
        action for action,kind in ADD_ACTIONS.items() if encounter['battle']['friendly_totals'][kind-1]>0]


def group_rect(index, *, quantity=False):
    """Zero-based twenty-group grid, original 99F4..9AED."""
    return ((51 if quantity else 10)+77*(index%4),56+23*(index//4),30 if quantity else 18,16)


def group_report(battle,index):
    row=battle['friendly_groups'][index];kind=row[0]-1
    quantity=struct.unpack('<h',bytes(row[1:3]))[0];total=battle['friendly_totals'][kind]
    return row[0],quantity,quantity*battle['friendly_primary'][kind]//total if total else 0


def setup_signature(state):
    encounter=setup_encounter(state);battle=encounter['battle']
    return (tuple(encounter['destination']),encounter['player_attacking'],
            tuple(tuple(r) for r in battle['friendly_groups']),
            *(tuple(battle['friendly_'+field]) for field in ('totals','primary','secondary','reserve')))


def setup_targets(state):
    battle=setup_encounter(state)['battle']
    return [(group_rect(i,quantity=quantity),'Add/Subtract troop' if quantity else 'Remove unit',
             ('ground_quantity' if quantity else 'ground_remove',i+1))
            for quantity in (False,True) for i in range(len(battle['friendly_groups']))]


def draw_setup(renderer,state,caption):
    encounter=setup_encounter(state);battle=encounter['battle']
    target=renderer.frame(state,'WAR/GRBEOSZT.PIC',19,0,caption,buttons=setup_buttons(state))
    icons=renderer.path_asset('WAR/GRICON.PIC')
    for i in range(len(battle['friendly_groups'])):
        kind,quantity,power=group_report(battle,i);x,y,_,_=group_rect(i)
        target.blit(icons,x,y,source=((kind-1)*80,0,16,16))
        renderer.text(target,str(quantity).rjust(3),x+51,y,columns=3)
        renderer.text(target,display_number(power,4).rjust(4),x+45,y+8,columns=4)
    for kind in range(4):
        if not battle['friendly_totals'][kind]:continue
        x=60 if kind<2 else 160;y=176+10*(kind%2)
        renderer.text(target,DEPLOY_NAMES[kind],x,y,columns=12 if kind<2 else 16)
        renderer.text(target,display_number(battle['friendly_reserve'][kind],5),130 if kind<2 else 260,y,columns=5)
    return target


class GroundSetupBar(ttk.Frame):
    def __init__(self,app):
        super().__init__(app.root)
        for label,callback in (('Save',app.save),('Load',app.load)):
            ttk.Button(self,text=label,command=lambda callback=callback:app.guard(callback)).pack(side='left')
        ttk.Label(self,text='Icon: remove group. Count: left +1 / right -1.').pack(side='left',padx=8)
