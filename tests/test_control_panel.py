"""Bounded icon recovery and original frame composition without game assets."""
import struct
import unittest
from openreunion.core import GameError
from openreunion.dos.assets import Picture
from openreunion.dos.control_panel import decode_icon,decode_icons,converted_icons,decode_converted_icons,button_picture,panel_pixels,panel_picture,pointer_slot


def icon(value=5):return (bytes([0xFF,value])*15+bytes([0xCF,value])+b'\x0c')


class ControlPanelTests(unittest.TestCase):
    def test_rle_marker_and_wrapping_palette_offset(self):
        self.assertEqual(decode_icon(icon(255)),bytes([1])*960)
        self.assertEqual(decode_icon(bytes([0xC1,192])*960+b'\x0c'),bytes([194])*960)
        for bad in (b'',icon()[:-1],icon()+b'\x0c',b'\xc0\x05'+icon(),b'\xff\x05\x0c'):
            with self.assertRaises(GameError):decode_icon(bad)

    def test_exactly_sixty_eight_records_and_portable_roundtrip(self):
        data=b''.join(struct.pack('<H',len(icon(i)))+icon(i) for i in range(68))
        bank=decode_icons(data);self.assertEqual(len(bank),68)
        self.assertEqual(decode_converted_icons(converted_icons(bank)),bank)
        for bad in (data[:-1],data+b'\0\0',data[:10]):
            with self.assertRaises(GameError):decode_icons(bad)
        with self.assertRaises(GameError):decode_converted_icons(converted_icons(bank)+b'\0')

    def test_padding_column_is_not_painted_and_rgb_survives_index_rotation(self):
        palette=b''.join(bytes([i,i,i]) for i in range(256))
        frame=Picture(240,32,bytes([7])*(240*32),palette)
        bank=tuple((bytes([10])*39+b'\xff')*24 for _ in range(68))
        result=button_picture(frame,bank,1)
        self.assertEqual(result.pixels[4*48+4:4*48+43],bytes([10])*39)
        self.assertEqual(result.pixels[4*48+43],9)
        self.assertEqual(result.rgb()[:3],bytes([7])*3)
        self.assertEqual(button_picture(frame,bank,0).pixels,bytes([9])*(48*32))

    def test_display_offset_aligns_six_buttons_and_complete_page_tile(self):
        frame=Picture(240,32,bytes(range(240))*32,bytes(768))
        bank=tuple(bytes(960) for _ in range(68))
        buttons=[{'id':i,'label':'','icon':0} for i in range(78)]
        slots=[1]*7+[0]*5;background=bytes([201])*(320*66)
        backing=panel_pixels(frame,bank,buttons,slots,background)
        self.assertEqual(backing[0],201)
        first=panel_picture(frame,backing,0);second=panel_picture(frame,backing,1)
        self.assertEqual(first.pixels[:288],bytes(range(2,50))*6)
        self.assertEqual(first.pixels[288:320],bytes(range(82,114)))
        self.assertEqual(second.pixels[-32:],bytes(range(50,82)))
        self.assertEqual(backing[32*320],113,'Last tile byte spills into spacer row')
        slots[6]=0;one=panel_pixels(frame,bank,buttons,slots,background)
        self.assertEqual(one[33*320:],background[33*320:],'Absent page must not overwrite caller storage')

    def test_panel_rejects_out_of_bank_action_art_before_display(self):
        frame=Picture(240,32,bytes(240*32),bytes(768));bank=tuple(bytes(960) for _ in range(68))
        buttons=[{'id':i,'label':'','icon':0} for i in range(78)];buttons[61]['icon']=157
        for slots in ([61]+[0]*11,[78]+[0]*11,[1]*13):
            with self.assertRaises(GameError):panel_pixels(frame,bank,buttons,slots)

    def test_pointer_edges_status_priority_and_lowest_overlapping_hotspot(self):
        overlapping=((0,0,320,200),(40,60,20,20))
        self.assertEqual(pointer_slot(47,32,overlapping),1)
        self.assertEqual(pointer_slot(48,32,overlapping),2)
        self.assertEqual(pointer_slot(287,32,overlapping),6)
        self.assertEqual(pointer_slot(288,32,overlapping),13)
        self.assertEqual(pointer_slot(218,33,overlapping),21)
        self.assertEqual(pointer_slot(218,34,overlapping),14)
        self.assertEqual(pointer_slot(218,46,overlapping),21)
        self.assertEqual(pointer_slot(45,65,overlapping),21)
        self.assertEqual(pointer_slot(60,60,((40,60,20,20),)),0)


if __name__=='__main__':unittest.main()
