"""Reject incomplete original module assets before native decoding."""
import unittest
from openreunion.core import GameError
from openreunion.dos.module_music import decode_module


def module():
    data=bytearray(1084+1024);data[950]=1;data[1080:1084]=b'M.K.';return data


class ModuleMusicTests(unittest.TestCase):
    def test_complete_four_channel_stream(self):
        song=decode_module(bytes(module()))
        self.assertEqual((song.orders,song.patterns,song.sample_bytes),((0,),1,0))

    def test_missing_pattern_sample_and_trailing_bytes_rejected(self):
        data=module()
        for value in (bytes(data[:-1]),bytes(data)+b'\0'):
            with self.assertRaises(GameError):decode_module(value)
        data[43]=1
        with self.assertRaises(GameError):decode_module(bytes(data))
        song=decode_module(bytes(data)+b'\0\0');self.assertEqual(song.sample_bytes,2)

    def test_order_signature_tuning_and_volume_bounds(self):
        for offset,value in ((950,0),(950,129),(952,128),(1080,0),(44,16),(45,65)):
            with self.subTest(offset=offset):
                data=module();data[offset]=value
                with self.assertRaises(GameError):decode_module(bytes(data))
        with self.assertRaises(GameError):decode_module(module())


if __name__=='__main__':unittest.main()
