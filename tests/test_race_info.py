"""Race table boundaries, discovery and content decoding without game assets."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.race_info import decode_profiles,profile,revealed_race
from openreunion.dos.text import audit_text,read_text


def table():
    data=bytearray()
    for owner in range(1,13):
        for text in (f' Race {owner} ', '', 'First sentence continues', 'onto a second line.', '',
                     'A second paragraph.', '', '', '', '', '', ''):
            encoded=text.encode('cp437');data.extend(bytes([len(encoded)])+encoded+b'\xff'*(35-len(encoded)))
    return bytes(data)


class RaceInfoTests(unittest.TestCase):
    def test_all_records_padding_and_paragraphs(self):
        lines=decode_profiles(table())
        for owner in range(1,13):
            self.assertEqual(profile(lines,owner),{'title':f'Race {owner}',
                'description':'First sentence continues onto a second line.\n\nA second paragraph.'})
        self.assertEqual(lines[0],' Race 1 ')

    def test_malformed_tables_and_bundle_records_reject(self):
        data=table()
        for invalid in (data[:-1],data+b'\0',b'\x24'+data[1:]):
            with self.assertRaises(GameError):decode_profiles(invalid)
        for lines in ([],decode_profiles(data)[:-1],['x'*36]*144,[None]*144):
            with self.assertRaises(GameError):profile(lines,2)
        for owner in (True,0,13,'2'):
            with self.assertRaises(GameError):profile(decode_profiles(data),owner)

    def test_discovery_and_signed_survey(self):
        for owner in range(14):
            for survey in (0,29,30,39,40,60,127,128,255):
                raw=[0]*65;raw[0]=owner;raw[12]=survey
                self.assertEqual(revealed_race(raw),owner if 2<=owner<=12 and 40<=survey<=127 else None)

    def test_reader_and_extractor_support_only_known_raw_format(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'TEXT').mkdir();path=root/'TEXT/SZ_FAJ.RAW';path.write_bytes(table())
            (root/'TEXT/UNKNOWN.RAW').write_bytes(b'unknown format')
            result=audit_text(root)
            self.assertEqual(read_text(path),decode_profiles(table()))
            self.assertEqual(result['decoded'][0]['lines'],read_text(path))
            self.assertEqual(result['decoded'][0]['line_count'],144)
            self.assertEqual(result['unsupported'][0]['path'],'TEXT/UNKNOWN.RAW')
            self.assertFalse(result['malformed'])
            path.write_bytes(b'bad')
            self.assertEqual(len(audit_text(root)['malformed']),1)


if __name__=='__main__':unittest.main()
