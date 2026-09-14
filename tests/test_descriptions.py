"""Fixed-description boundaries, padding, extraction and readable line joins."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.descriptions import FORMATS,decode_descriptions,record,paragraphs,product_description,candidate_description,product_description_available
from openreunion.dos.text import audit_text,read_text


def table(name):
    count,lines,stride=FORMATS[name];data=bytearray()
    for i in range(count):
        for j in range(lines):
            text=f' Record {i+1} ' if j==0 else f'Line {j}' if j!=2 else ''
            encoded=text.encode();data.extend(bytes([len(encoded)])+encoded+b'\xfe'*(stride-1-len(encoded)))
    return bytes(data)


class DescriptionTests(unittest.TestCase):
    def test_both_tables_preserve_empty_slots_and_ignore_padding(self):
        for name,(count,size,stride) in FORMATS.items():
            lines=decode_descriptions(name,table(name))
            self.assertEqual(len(lines),count*size)
            for i in range(1,count+1):
                data=record(name,lines,i)
                self.assertEqual(data[0],f' Record {i} ');self.assertEqual(data[2],'')
        c=candidate_description(decode_descriptions('SZ_FACE.RAW',table('SZ_FACE.RAW')),12)
        self.assertEqual(c,{'title':'Record 12','description':'Line 1','original_offer':'Line 3'})

    def test_malformed_binary_and_converted_tables_reject(self):
        for name,(count,size,stride) in FORMATS.items():
            raw=table(name)
            for bad in (raw[:-1],raw+b'\0',bytes([stride])+raw[1:]):
                with self.assertRaises(GameError):decode_descriptions(name,bad)
            for bad in ([None]*(count*size),['x'*stride]*(count*size),[]):
                with self.assertRaises(GameError):record(name,bad,1)
            for identity in (True,0,count+1):
                with self.assertRaises(GameError):record(name,decode_descriptions(name,raw),identity)

    def test_reflow_preserves_paragraphs_and_hyphenated_words(self):
        self.assertEqual(paragraphs(['  A multi-','role vehicle.','','A second','paragraph.','']),
                         'A multi-role vehicle.\n\nA second paragraph.')
        data=decode_descriptions('SZ_TALAL.RAW',table('SZ_TALAL.RAW'))
        self.assertEqual(product_description(data,35)['title'],'Record 35')

    def test_only_completed_research_has_original_description_access(self):
        for state in range(6):
            self.assertEqual(product_description_available({'research_state':state}),state==5)

    def test_both_raw_files_are_supported_by_reader_and_extractor(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'TEXT').mkdir()
            for name in FORMATS:
                path=root/'TEXT'/name;path.write_bytes(table(name))
                self.assertEqual(read_text(path),decode_descriptions(name,table(name)))
            result=audit_text(root)
            self.assertEqual(len(result['decoded']),2);self.assertFalse(result['malformed']);self.assertFalse(result['unsupported'])
            (root/'TEXT/SZ_FACE.RAW').write_bytes(b'bad')
            self.assertEqual(len(audit_text(root)['malformed']),1)


if __name__=='__main__':unittest.main()
