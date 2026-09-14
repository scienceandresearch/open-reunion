"""Mission snapshots, archive isolation and v21 save compatibility."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from test_bar import prepared,mission,contract
from openreunion.core import GameError
from openreunion.dos.session import RecoveredSession,validate,SCHEMA
from openreunion.dos.rules import calendar_tick
from openreunion.dos.mission_messages import append_report_text,report_size,REPORT_BUDGET


class MissionMessageTests(unittest.TestCase):
    def test_completed_intelligence_is_a_saved_snapshot_not_live_enemy_data(self):
        for kind in range(1,5):
            with self.subTest(kind=kind):
                s=prepared();mission(s,2,kind*20+3)
                s.state['worlds']['1:2:0']['raw'][0]=3
                s.state['worlds']['1:2:0']['raw'][6]=1
                s.state['worlds']['1:2:0']['raw'][27:59]=struct.pack('<8I',123,2,3,4,5,6,7,8)
                s.apply('advance',hours=1)
                event=s.state['events'][-1];request=s.state['presentation_requests'][-1]
                self.assertEqual(event['id'],39);self.assertEqual(event['report'],request['report'])
                self.assertIsNot(event['report'],request['report'])
                if kind==3:self.assertIn('123 hunters','\n'.join(event['report']))
                with tempfile.TemporaryDirectory() as tmp:
                    path=Path(tmp)/'report.json';s.save(path);loaded=RecoveredSession.load(s.catalog,path)
                    self.assertEqual(s.state,loaded.state)
                    before=deepcopy(event);loaded.apply('dismiss_presentation')
                    loaded.state['worlds']['1:2:0']['raw'][27:59]=[0]*32
                    loaded.state['campaign']['civilizations'][1][19:27]=[0]*8
                    self.assertEqual(loaded.state['events'][-1],before)
                    loaded.save(path);self.assertEqual(RecoveredSession.load(s.catalog,path).state,loaded.state)

    def test_rewards_share_completion_notice_and_do_not_repeat_after_acknowledgement(self):
        s=prepared();mission(s,9,11);contract(s);s.apply('advance',hours=1)
        request=s.state['presentation_requests'][0]
        self.assertEqual(request['id'],47)
        self.assertEqual(request['report'],['You got 50 t of Detoxin.','You got 101 t of Texon.','You got 2 pieces of Synthetic 1.'])
        before=deepcopy(s.state['resources']);stock=s.state['products'][0]['stock']
        s.apply('dismiss_presentation');s.apply('advance',hours=1)
        self.assertEqual(s.state['resources'],before);self.assertEqual(s.state['products'][0]['stock'],stock)

    def test_pirate_announcements_are_dated_queued_and_retained(self):
        s=prepared();date=calendar_tick(s.state['date'])
        s.state['campaign']['bar']['contracts'][3][14:19]=[*struct.pack('<h',date[0]),*date[1:]]
        s.apply('advance',hours=12)
        self.assertEqual(s.state['date'],date)
        self.assertEqual(s.state['events'][-1],{'kind':'report','id':4,'date':date,'report':['Original pirate notice 4']})
        self.assertEqual(append_report_text('',s.state['events'][-1]),'Original pirate notice 4')
        s.apply('dismiss_presentation');self.assertEqual(len(s.state['events']),1)

    def test_malformed_reports_rejected_and_old_saves_cannot_smuggle_them(self):
        s=prepared();mission(s,9,1);contract(s);s.apply('advance',hours=1)
        for value in (None,[],[''],[123],['bad\nline'],['x'*501],['ok']*513):
            bad=deepcopy(s.state);bad['events'][-1]['report']=value
            with self.subTest(value=repr(value)[:40]),self.assertRaises(GameError):validate(bad,s.catalog)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'old.json';old=deepcopy(s.state);old['schema']='recovered-strategy-v21'
            path.write_text(json.dumps(old))
            with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)

    def test_v21_save_migrates_without_inventing_historical_report_text(self):
        s=prepared();s.state['events']=[{'kind':'message','id':39,'date':list(s.state['date'])}]
        s.state['presentation_requests']=[{'kind':'message','id':39}]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'v21.json';s.save(path);old=json.loads(path.read_text());old['schema']='recovered-strategy-v21'
            old.pop('hero');path.write_text(json.dumps(old));loaded=RecoveredSession.load(s.catalog,path)
            self.assertEqual(loaded.state,s.state);self.assertEqual(loaded.state['schema'],SCHEMA)
            self.assertNotIn('report',loaded.state['events'][0])
            self.assertEqual(loaded.result_animation,s.result_animation)

    def test_archive_budget_keeps_new_report_and_atomic_save_readable(self):
        s=prepared();date=list(s.state['date'])
        s.state['events']=[{'kind':'report','id':1,'date':date,'report':[f'{i:03}'+('x'*497)]*10} for i in range(99)]
        s.state['events'].append({'kind':'report','id':1,'date':date,'report':['y'*500]*3})
        self.assertLess(report_size(s.state['events']),REPORT_BUDGET);validate(s.state,s.catalog)
        date=calendar_tick(date);s.state['campaign']['bar']['contracts'][3][14:19]=[*struct.pack('<h',date[0]),*date[1:]]
        s.catalog['pirate_messages'][3]='z'*500
        s.apply('advance',hours=1)
        self.assertEqual(len(s.state['events']),100)
        self.assertTrue(s.state['events'][0]['report'][0].startswith('001'))
        self.assertEqual(s.state['events'][-1]['report'],['z'*500])
        self.assertEqual(s.state['presentation_requests'][-1]['report'],['z'*500])
        self.assertLessEqual(report_size(s.state['events']),REPORT_BUDGET)
        self.assertGreater(report_size([{'report':['\u754c'*500]}]),1500)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'archive.json';s.save(path)
            self.assertEqual(RecoveredSession.load(s.catalog,path).state,s.state)


if __name__=='__main__':unittest.main()

