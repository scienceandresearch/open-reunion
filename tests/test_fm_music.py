"""Original-free FM music decoding and meaningful channel regressions."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.fm_music import (CONVERTED_MAGIC,FmPlayer,decode_music,
                                    decode_converted_music,unpack_music)


def fixture(events=()):
    raw=bytearray(1587+1152);raw[:51]=bytes([0]+[255]*50)
    for row,channel,note,effect in events:
        at=1587+row*18+channel*2;raw[at:at+2]=bytes([note,effect])
    return bytes(raw)


def pack(raw):return bytes((v-47)&255 for v in reversed(raw))


class FmMusicTests(unittest.TestCase):
    def test_unpack_preserves_every_byte_for_odd_and_even_lengths(self):
        for raw in (bytes(range(256)),bytes(range(255)),b'\x00',b'\xff'):
            self.assertEqual(unpack_music(pack(raw)),raw)
        for raw in (b'',bytes(0x7BD5),'wrong type'):
            with self.assertRaises(GameError):unpack_music(raw)

    def test_converted_song_preserves_data_and_trailing_bytes(self):
        raw=fixture()+b'kept trailer'
        a=decode_music(pack(raw));b=decode_converted_music(CONVERTED_MAGIC+raw)
        self.assertEqual(a,b);self.assertEqual(a.trailing,b'kept trailer')

    def test_invalid_orders_notes_and_truncation_fail(self):
        empty=bytearray(fixture());empty[:51]=bytes([255])*51
        missing=bytearray(fixture());missing[0]=1
        unterminated=bytearray(fixture());unterminated[:51]=bytes(51)
        for raw in (bytes(empty),bytes(missing),bytes(unterminated),fixture()[:-1],fixture([(0,0,98,0)])):
            with self.assertRaises(GameError):decode_music(pack(raw))
        with self.assertRaises(GameError):decode_converted_music(b'bad header'+fixture())

    def test_note_off_clears_playing_channel_and_emits_key_off(self):
        player=FmPlayer(decode_music(pack(fixture([(0,2,49,0xF0),(1,2,127,0)]))))
        player.tick();self.assertTrue(player.frequency[2]&0x2000)
        writes=player.tick();self.assertFalse(player.frequency[2]&0x2000)
        self.assertIn([0xB2,player.frequency[2]>>8],writes)
        self.assertEqual(player.frequency[0],0)

    def test_tempo_wait_and_pattern_break_use_channel_order(self):
        player=FmPlayer(decode_music(pack(fixture([(0,0,0,0xF3),(0,8,0,0xF1),(1,0,0,1)]))))
        player.tick();self.assertEqual((player.row,player.wait,player.speed),(1,2,2))
        player.tick();self.assertEqual(player.row,1)
        player.tick();self.assertEqual((player.row,player.order),(0,0))

    def test_instrument_operand_does_not_change_tempo(self):
        player=FmPlayer(decode_music(pack(fixture([(0,0,128,0xFF)]))))
        player.tick();self.assertEqual(player.instrument[0],127)
        self.assertEqual(player.speed,2)

    def test_pitch_slide_wraps_only_low_frequency_byte(self):
        player=FmPlayer(decode_music(pack(fixture([(0,0,0,0x1F)]))))
        player.frequency[0]=0x21FE;player.tick()
        self.assertEqual(player.frequency[0],0x210E)

    def test_sequencer_copy_continues_identically_without_mutating_song(self):
        song=decode_music(pack(fixture([(0,0,49,0xF0),(1,0,0,0xC4),(2,0,127,0)])))
        player=FmPlayer(song);player.tick();resumed=deepcopy(player)
        for _ in range(150):
            self.assertEqual(player.tick(),resumed.tick())
            self.assertEqual(player.__dict__,resumed.__dict__)
        self.assertEqual(song,decode_music(pack(fixture([(0,0,49,0xF0),(1,0,0,0xC4),(2,0,127,0)]))))


if __name__=='__main__':unittest.main()
