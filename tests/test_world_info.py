"""Discovery boundaries and decision-relevant planet information."""
import struct
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.dos.world_info import survey_information,owner_label

CATALOG={'surface_rules':{'groups':[1,8,2,7,10,3,9,5,4,6,11],
                         'editable':[1,1,1,0,1,0,0,0,0,1,0]},
         'alien_names':[f'Race {i}' for i in range(2,13)]}


def world(survey=0,owner=0):
    raw=[0]*65;raw[0]=owner;raw[2]=raw[3]=raw[21]=1;raw[12]=survey
    raw[13:17]=struct.pack('<I',12345);raw[23:27]=struct.pack('<Hh',65535,-20)
    raw[59:65]=[0,9,10,40,90,100]
    return raw


class WorldInfoTests(unittest.TestCase):
    def test_unlabelled_original_terrain_does_not_request_more_survey(self):
        raw=world(60);raw[21]=11
        self.assertEqual(survey_information(raw,CATALOG)['terrain'],'Unclassified terrain')
        raw[12]=5
        self.assertIsNone(survey_information(raw,CATALOG)['terrain'])

    def test_reveal_thresholds_and_signed_environment_values(self):
        for survey,key,expected in ((3,'diameter_km',65535),(5,'temperature_k',-20),
                                    (6,'terrain','Earth-like'),(20,'habitable',True)):
            self.assertIsNone(survey_information(world(survey-1),CATALOG)[key])
            self.assertEqual(survey_information(world(survey),CATALOG)[key],expected)
        for survey in (128,255):
            info=survey_information(world(survey),CATALOG)
            self.assertTrue(all(info[k] is None for k in ('terrain','diameter_km','temperature_k','habitable','ore_presence')))

    def test_ore_presence_uses_threshold_and_mining_flag_with_separate_abundance(self):
        self.assertIsNone(survey_information(world(9),CATALOG)['ore_presence'])
        info=survey_information(world(10),CATALOG)
        self.assertEqual(list(info['ore_presence'].values()),[False,False,True,True,True,True])
        self.assertEqual(list(info['ore_abundance'].values()),[0,9,10,40,90,100])
        raw=world(60);raw[3]=0;info=survey_information(raw,CATALOG)
        self.assertFalse(any(info['ore_presence'].values()))
        self.assertFalse(any(info['ore_abundance'].values()))

    def test_suitability_requires_both_life_and_editable_terrain(self):
        for terrain,life,expected in ((1,1,True),(2,1,False),(6,1,True),(1,0,False),(0,1,False),(255,1,False)):
            raw=world(20);raw[21]=terrain;raw[2]=life
            self.assertIs(survey_information(raw,CATALOG)['habitable'],expected)

    def test_alien_identity_and_population_do_not_leak_before_survey(self):
        for survey,owner,population in ((0,None,None),(29,None,None),(30,13,None),(39,13,None),(40,3,12345)):
            info=survey_information(world(survey,3),CATALOG)
            self.assertEqual(info['owner'],owner);self.assertEqual(info['population'],population)
        self.assertEqual(owner_label(survey_information(world(30,3),CATALOG),CATALOG),'Unidentified aliens')
        self.assertEqual(owner_label(survey_information(world(40,3),CATALOG),CATALOG),'Race 3')
        info=survey_information(world(0,1),CATALOG)
        self.assertEqual((info['owner'],info['population']),(1,12345))


if __name__=='__main__':unittest.main()
