import json,tempfile,unittest
from pathlib import Path
from openreunion.core import GameError
from openreunion.dos.disk_slots import slot_at,slot_label,slot_path


class DiskSlotsTests(unittest.TestCase):
    def test_all_twelve_row_boundaries_and_clamping(self):
        for i in range(12):
            self.assertEqual(slot_at(64+9*i),i+1)
            self.assertEqual(slot_at(72+9*i),i+1)
        self.assertEqual(slot_at(-100),1);self.assertEqual(slot_at(999),12)

    def test_empty_and_unreadable_slots_leave_file_bytes_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn('Empty',slot_label(directory,1))
            p=slot_path(directory,1);p.write_bytes(b'broken json')
            self.assertIn('Unreadable',slot_label(directory,1));self.assertEqual(p.read_bytes(),b'broken json')
            for value in (None,[],{'date':[2927,8,13,True]},{'date':[2927,8,13,25]}, {'date':[2927,8,13,23]}):
                p.write_text(json.dumps(value));label=slot_label(directory,1)
                self.assertEqual('2927/08/13/23' in label,value=={'date':[2927,8,13,23]})

    def test_slot_names_are_bounded_and_directory_collisions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for number in (0,13,True,'../other'):
                with self.assertRaises(GameError):slot_path(directory,number)
            p=slot_path(directory,12);self.assertEqual(p.parent,Path(directory).resolve())
            p.mkdir()
            with self.assertRaises(GameError):slot_path(directory,12)


if __name__=='__main__':unittest.main()
