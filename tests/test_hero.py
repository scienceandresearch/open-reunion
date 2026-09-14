"""Hero metadata cannot affect strategy or disappear across save migrations."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from test_campaign import session_fixture
from openreunion.core import GameError
from openreunion.dos.session import RecoveredSession
from openreunion.dos.hero import choice_at,bridge_source,adviser_source,dialog_path


class HeroTests(unittest.TestCase):
    def test_original_identity_and_distinct_bank_orders(self):
        self.assertEqual([choice_at(x) for x in (0,159,160,319)],[2,2,1,1])
        self.assertEqual(bridge_source(1),(69,1,67,59))
        self.assertEqual(bridge_source(2),(1,1,67,59))
        self.assertEqual(adviser_source(1),(101,1,100,109))
        self.assertEqual(adviser_source(2),(1,1,100,109))
        self.assertEqual(dialog_path(2),'PICS/SAJAT2.PIC')

    def test_identity_roundtrip_does_not_change_gameplay(self):
        s=session_fixture();state=deepcopy(s.state)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'hero.json'
            for hero in (1,2):
                s.hero=hero;s.save(path);restored=RecoveredSession.load(s.catalog,path)
                self.assertEqual(restored.hero,hero);self.assertEqual(restored.state,state)
                self.assertNotIn('hero',s.state)

    def test_invalid_identity_cannot_overwrite_valid_save(self):
        s=session_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'hero.json';s.save(path);before=path.read_bytes()
            for hero in (0,3,True,None,'1'):
                s.hero=hero
                with self.assertRaises(GameError):s.save(path)
                self.assertEqual(path.read_bytes(),before)

    def test_current_save_requires_valid_identity(self):
        s=session_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'hero.json';s.save(path);original=json.loads(path.read_text())
            for hero in (0,3,True,None,'2'):
                payload=dict(original,hero=hero);path.write_text(json.dumps(payload))
                with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)
            original.pop('hero');path.write_text(json.dumps(original))
            with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)

    def test_v22_retains_previously_displayed_female_hero(self):
        s=session_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'old.json';s.save(path);payload=json.loads(path.read_text())
            payload['schema']='recovered-strategy-v22';payload.pop('hero');path.write_text(json.dumps(payload))
            restored=RecoveredSession.load(s.catalog,path)
            self.assertEqual(restored.hero,2);self.assertEqual(restored.state,s.state)
            payload['hero']=1;path.write_text(json.dumps(payload))
            with self.assertRaises(GameError):RecoveredSession.load(s.catalog,path)


if __name__=='__main__':unittest.main()
