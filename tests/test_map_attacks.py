"""Map target identity, original offers and stale/overflow attack regressions."""
from copy import deepcopy
import unittest
from test_battle_dispatch import ready
from openreunion.core import GameError
from openreunion.dos.aliens import store_fleet
from openreunion.dos.orbital_screen import map_buttons,map_attack,attack_signature


def scenario():
    state=ready().state
    civ=state['campaign']['civilizations'][2];civ[38]=1;civ[27]=4
    row=[0]*27;row[0]=2;row[2]=1;row[8:11]=[1,5,0];store_fleet(civ,1,row)
    entries=[{'key':('player',0),'icon':1},{'key':('alien',4,0),'icon':7}]
    return state,entries


class MapAttackTests(unittest.TestCase):
    def test_selection_distinguishes_space_target_and_exact_moon_assault(self):
        state,entries=scenario();before=deepcopy(state)
        self.assertEqual(map_attack(state,5,entries,('player',0),71),{'fleet_index':0})
        self.assertEqual(map_attack(state,5,entries,('alien',4,0),55),{'fleet_index':0,'target_race':4,'target_slot':1})
        for key,action in ((('player',0),55),(('alien',4,0),71)):
            with self.assertRaises(GameError):map_attack(state,5,entries,key,action)
        self.assertEqual(state,before)

    def test_commander_errors_happen_on_activation_not_by_hiding_original_offer(self):
        state,entries=scenario();state['levels']['fighter']=0
        self.assertIn(71,map_buttons(state,5,entries,('player',0)))
        self.assertIn(55,map_buttons(state,5,entries,('alien',4,0)))
        for key,action in ((('player',0),71),(('alien',4,0),55)):
            with self.assertRaisesRegex(GameError,'commander'):map_attack(state,5,entries,key,action)
        state['levels']['fighter']=20;state['ranks']['fighter']=1
        with self.assertRaisesRegex(GameError,'rank'):map_attack(state,5,entries,('player',0),71)
        map_attack(state,5,entries,('alien',4,0),55)

    def test_current_diplomacy_survey_target_location_and_count_rechecked(self):
        edits=[lambda s:s['campaign']['civilizations'][2].__setitem__(27,6),
               lambda s:s['campaign']['civilizations'][2].__setitem__(38,0),
               lambda s:s['campaign']['civilizations'][2].__setitem__(47,2),
               lambda s:s['fleets']['moving'][0].__setitem__(22,4)]
        for edit in edits:
            state,entries=scenario();edit(state);before=deepcopy(state)
            with self.assertRaises(GameError):map_attack(state,5,entries,('alien',4,0),55)
            self.assertEqual(state,before)
        state,entries=scenario();state['worlds']['1:5:1']['raw'][12]=39
        self.assertNotIn(71,map_buttons(state,5,entries,('player',0)))
        with self.assertRaises(GameError):map_attack(state,5,[],('alien',4,0),55)

    def test_army_on_other_page_participates_and_state_three_is_not_chosen(self):
        state,entries=scenario();state['fleets']['moving'][0][22]=3
        with self.assertRaisesRegex(GameError,'arrive'):map_attack(state,5,entries,('alien',4,0),55)
        state['fleets']['moving'].append(deepcopy(state['fleets']['moving'][0]))
        state['fleets']['moving'][1][22]=2
        entries.extend([None]*18+[{'key':('player',1),'icon':1}])
        self.assertEqual(map_attack(state,5,entries,('alien',4,0),55)['fleet_index'],1)

    def test_held_signature_changes_when_same_slot_target_or_commander_changes(self):
        state,entries=scenario();key=('alien',4,0);buttons=map_buttons(state,5,entries,key)
        before=attack_signature(state,entries,key,buttons)
        state['campaign']['civilizations'][2][50]+=1
        self.assertNotEqual(before,attack_signature(state,entries,key,buttons))
        before=attack_signature(state,entries,key,buttons);state['levels']['fighter']=0
        self.assertNotEqual(before,attack_signature(state,entries,key,buttons))
