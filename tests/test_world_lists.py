"""Discovery-safe filtering, original site gates and earned alien knowledge."""
from copy import deepcopy
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.dos.world_lists import FILTERS,filtered_worlds,list_category


def fixture():
    definitions=[{'id':f'{s}:{p}:{m}','system':s,'planet':p,'moon':m} for s,p,m in ((1,1,0),(1,1,1),(1,2,0),(2,1,0))]
    catalog={'worlds':definitions,'surface_rules':{'groups':[1,2],'editable':[1,0]}}
    campaign={'bar':{'intelligence':[0]*12},'civilizations':[[0]*228 for _ in range(11)],
              'navigation':{'planet_visibility':[0,255]+[0]*62}}
    state={'known_systems':[1,255]+[255]*6,'campaign':campaign,
           'worlds':{w['id']:{'raw':[0]*65} for w in definitions}}
    return catalog,state


class WorldListTests(unittest.TestCase):
    def test_hidden_systems_planets_and_their_moons_never_leak(self):
        catalog,state=fixture()
        for w in state['worlds'].values():w['raw'][0]=w['raw'][6]=1
        before=deepcopy(state)
        self.assertEqual([w['id'] for w,_ in filtered_worlds(state,catalog)],['1:1:0','1:1:1'])
        self.assertEqual(len(filtered_worlds(state,catalog,FILTERS[1])),2)
        state['campaign']['navigation']['planet_visibility'][0]=128
        self.assertEqual(filtered_worlds(state,catalog),[])
        state['campaign']['navigation']['planet_visibility'][0]=0;self.assertEqual(state,before)

    def test_mining_to_colony_site_transition_and_construction_exclusion(self):
        catalog,state=fixture();raw=state['worlds']['1:1:0']['raw'];raw[2]=raw[3]=raw[21]=1
        for survey,want in ((9,0),(10,2),(29,2),(30,1),(127,1),(128,0),(255,0)):
            raw[12]=survey;self.assertEqual(list_category(raw,catalog,state['campaign'],2),want)
        raw[12]=30;raw[7]=1;self.assertEqual(list_category(raw,catalog,state['campaign'],2),0)
        raw[7]=0;raw[21]=2;self.assertEqual(list_category(raw,catalog,state['campaign'],2),2)

    def test_owned_station_colony_and_claim_without_facilities(self):
        catalog,state=fixture();raw=state['worlds']['1:1:0']['raw'];raw[0]=1
        self.assertEqual(list_category(raw,catalog,state['campaign'],1),0)
        raw[10]=1;self.assertEqual(list_category(raw,catalog,state['campaign'],1),2)
        raw[6]=1;self.assertEqual(list_category(raw,catalog,state['campaign'],1),1)
        raw[0]=2;self.assertEqual(list_category(raw,catalog,state['campaign'],1),0)

    def test_alien_surveys_relations_and_report_knowledge(self):
        catalog,state=fixture();c=state['campaign'];raw=state['worlds']['1:1:0']['raw'];raw[0]=2
        c['civilizations'][0][27]=2
        for survey,want in ((29,0),(30,1),(39,1),(40,2),(128,0)):
            raw[12]=survey;self.assertEqual(list_category(raw,catalog,c,3),want)
        c['bar']['intelligence'][1]=1;raw[12]=0
        self.assertEqual(list_category(raw,catalog,c,3),2)
        c['civilizations'][0][27]=6;self.assertEqual(list_category(raw,catalog,c,3),3)
        c['civilizations'][0][27]=4;self.assertEqual(list_category(raw,catalog,c,3),1)
        c['civilizations'][0][27]=255;self.assertEqual(list_category(raw,catalog,c,3),0)

    def test_filtering_is_read_only_and_older_missing_bar_uses_survey(self):
        catalog,state=fixture();c=state['campaign'];c['bar']=None
        raw=state['worlds']['1:1:0']['raw'];raw[0]=2;raw[12]=40;c['civilizations'][0][27]=6
        before=deepcopy(state)
        self.assertEqual(filtered_worlds(state,catalog,FILTERS[3])[0][1],'Friendly world')
        for selected in FILTERS:filtered_worlds(state,catalog,selected)
        self.assertEqual(state,before)


if __name__=='__main__':unittest.main()
