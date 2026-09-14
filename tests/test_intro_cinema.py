"""The connected intro keeps the recovered sequence and private controller state."""
from collections import Counter
from copy import deepcopy
import unittest

from openreunion.dos.intro_cinema import TRACKS,script,timeline
from openreunion.dos.intro_music import decode_intro_module


def song(patterns=14):
    data=bytearray(1084+patterns*1024);data[950]=patterns
    data[952:952+patterns]=bytes(range(patterns));data[1080:1084]=b'M.K.'
    return decode_intro_module(bytes(data))


class IntroCinemaTests(unittest.TestCase):
    def test_script_retains_every_recovered_scene_in_order(self):
        operations=script();counts=Counter(row[0] for row in operations)
        self.assertEqual(tuple(row[1] for row in operations if row[0]=='music'),TRACKS)
        self.assertEqual([row[1] for row in operations if row[0]=='animation'],
            [20,21,12,13,15,14,1,1,3,4,5,6,7,8,10,11,16,23,24,18,19,22])
        self.assertEqual(counts['highres'],22)
        self.assertEqual([row[1] for row in operations if row[0]=='highres'],
            ['1x','2x','3x','4x','5x','6x','7x','8x','9x','10x','10_2x','11x',
             '12x','13x','14x','15x','16x','17x','18x','19x','20x','21x'])
        self.assertEqual(operations[-4:],(('picture','LEADER',3,18,5,140),
            ('picture','GABOR',7,1,5,70),('wait_fade',7,63,70),('input',)))

    def test_timeline_has_all_tracks_and_uses_only_its_private_seed(self):
        songs={name:song() for name in TRACKS};before=deepcopy(songs)
        first=timeline(songs,seed=1994);second=timeline(songs,seed=1994)
        self.assertEqual(first,second);self.assertEqual(songs,before)
        self.assertEqual(tuple(name for _,name in first.music),TRACKS)
        self.assertGreater(len(first.entries),8000);self.assertGreater(first.duration,0)
        self.assertNotEqual(first.next_seed,1994)
        kinds=Counter(shot.operation[0] for _,shot in first.entries if shot.operation)
        self.assertEqual(kinds['highres'],22);self.assertEqual(kinds['flight'],168)
        self.assertEqual(kinds['scroll'],200);self.assertGreater(kinds['shake'],60)

    def test_cue_gate_releases_when_pattern_jump_skips_target_row(self):
        data=bytearray(1084+14*1024);data[950]=14;data[952:966]=bytes(range(14));data[1080:1084]=b'M.K.'
        # D00 after the order-three row-eight cue skips its later row-54 cue.
        at=1084+2*1024+9*16;data[at+2:at+4]=b'\r\0'
        jumped=decode_intro_module(bytes(data))
        songs={name:song() for name in TRACKS};songs['INTRO1']=jumped
        film=timeline(songs)
        self.assertGreater(film.duration,0)


if __name__=='__main__':unittest.main()
