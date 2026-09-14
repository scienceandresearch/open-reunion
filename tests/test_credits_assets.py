"""Regressions for the credits' skipped frames and misleading geometry table."""
from pathlib import Path
import struct,tempfile,unittest
from unittest.mock import patch
from openreunion.core import GameError
from openreunion.dos.assets import Picture
from openreunion.dos.credits_assets import animation_frames,original_frames,high_resolution_picture,raw_palette
from openreunion.dos.story_cinema import draw_frame


def solid(value):
    return struct.pack('<H',4)+b'SpidyAnim'+struct.pack('<HH',320,200)+b'\xc0'+struct.pack('<H',64000)+bytes([value])


class CreditsAssetTests(unittest.TestCase):
    def test_skipped_opening_never_seeds_displayed_deltas(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'PAL3.PIC').write_bytes(bytes(768))
            (root/'ANIM3.ANI').write_bytes(solid(7)*30+b'\0\0'*135)
            with patch('openreunion.dos.credits_assets.ASSETS',(3,)):
                frames=list(original_frames(root))
        self.assertEqual([index for _,index,_ in frames],list(range(31,166)))
        self.assertTrue(all(p.pixels==bytes(64000) for _,_,p in frames))

    def test_anim4_uses_embedded_200_pixel_height_and_retains_unused_tail(self):
        frames,tail=animation_frames(solid(9)*41+b'unused',4)
        self.assertEqual(tail,b'unused')
        self.assertEqual(draw_frame(frames,41,bytes(64000)),bytes([9])*64000)

    def test_high_resolution_last_strip_is_eighty_rows(self):
        pictures=[Picture(640,80 if i==5 else 100,bytes([i])*(640*(80 if i==5 else 100)),bytes(768)) for i in range(1,6)]
        with patch('openreunion.dos.credits_assets.read_picture',side_effect=pictures):
            result=high_resolution_picture(Path('.'))
        self.assertEqual((result.width,result.height),(640,480))
        self.assertEqual(result.pixels[640*399],4)
        self.assertEqual(result.pixels[640*400:],bytes([5])*(640*80))

    def test_palette_preserves_eight_bit_channels_but_rejects_truncation(self):
        self.assertEqual(raw_palette(bytes([255])*768),bytes([255])*768)
        with self.assertRaises(GameError):raw_palette(bytes(767))


if __name__=='__main__':unittest.main()
