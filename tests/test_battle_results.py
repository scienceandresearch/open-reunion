"""Result rendering bounds and visible complete casualty totals."""
import unittest
from openreunion.core import GameError
from openreunion.dos.assets import Picture
from openreunion.dos.battle_results import compose_result,draw_text,loss_labels,advance_ground_result,result_palette

CHARACTERS='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz?!()\'"+-:;.,1234567890%& /'


class BattleResultTests(unittest.TestCase):
    def test_totals_keep_every_digit_and_original_padding(self):
        losses={'friendly':[0,12,12345,4294967295],'hostile':[1,123,9999,10000]}
        labels=loss_labels(losses)
        self.assertEqual([row['text'] for row in labels[:4]],['   0','  12','12345','4294967295'])
        self.assertEqual([row['columns'] for row in labels[:4]],[4,4,5,10])
        font=Picture(320,32,bytes([2])*10240,bytes(768));background=Picture(320,151,bytes(48320),bytes(768))
        fixed=compose_result(background,font,CHARACTERS,losses)
        legacy=compose_result(background,font,CHARACTERS,losses,original_columns=True)
        self.assertEqual(fixed.pixels[57*320+87:57*320+117],bytes([187])*30)
        self.assertEqual(legacy.pixels[57*320+111:57*320+117],bytes(6))

    def test_glyph_writes_reject_overrun_without_touching_buffer(self):
        font=Picture(320,32,bytes(10240),bytes(768));pixels=bytearray([44])*64000
        for x,y,columns in ((315,0,1),(0,193,1),(0,0,54),(-1,0,1)):
            with self.assertRaises(GameError):draw_text(pixels,320,200,font,CHARACTERS,'1',x,y,columns,-7)
        self.assertEqual(pixels,bytearray([44])*64000)

    def test_defeat_cycle_draws_three_frames_without_gameplay_state(self):
        frame,counter=1,0;draws=[]
        for tick in range(40):
            frame,counter,paint=advance_ground_result(frame,counter)
            if paint is not None:draws.append((tick,paint))
        self.assertEqual(draws,[(0,1),(13,2),(26,3),(39,1)])
        self.assertEqual(advance_ground_result(2,1,False),(2,1,None))

    def test_reserved_font_colors_survive_unused_garbage_in_picture_palette(self):
        background=Picture(320,151,bytes(48320),bytes([0,255,0])*256)
        palette=result_palette(background)
        self.assertEqual(palette[185*3:188*3],bytes([0,0,0,182,170,0,129,117,0]))
        self.assertEqual(palette[:3],bytes([0,255,0]))
        self.assertEqual(loss_labels({'friendly':[2**63-1]*4,'hostile':[0]*4})[0]['columns'],19)


if __name__=='__main__':unittest.main()
