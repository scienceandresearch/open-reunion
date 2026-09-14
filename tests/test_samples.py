"""Sound block bounds, portable records and exact rational PCM continuation."""
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.samples import Sample,SampleRenderer,decode_sample,decode_converted_sample,decode_driver


def block(pcm=b'\x00\x80\xff',tc=156):return b'\x01'+(len(pcm)+2).to_bytes(3,'little')+bytes([tc,0])+pcm+b'\0'


class SampleTests(unittest.TestCase):
    def test_payload_excludes_header_and_terminator(self):
        sample=decode_sample(block());self.assertEqual(sample,Sample(156,b'\x00\x80\xff'))
        self.assertEqual(sample.period_us,100);self.assertEqual(sample.frames(10000),3)

    def test_malformed_blocks_reject_instead_of_guessing_audio(self):
        valid=block()
        for raw in (b'',valid[:-1],valid+b'\0',b'\x02'+valid[1:],valid[:5]+b'\x01'+valid[6:],valid[:1]+b'\xff'*3+valid[4:],block(b'')):
            with self.assertRaises(GameError):decode_sample(raw)

    def test_converted_roundtrip_is_bounded_and_versioned(self):
        sample=decode_sample(block());raw=sample.converted();self.assertEqual(decode_converted_sample(raw),sample)
        for value in (raw[:-1],raw+b'\0',raw.replace(b'ORSM\x01',b'ORSM\x02'),raw[:6]+b'\xff'*4+raw[10:]):
            with self.assertRaises(GameError):decode_converted_sample(value)

    def test_unsigned_mono_becomes_signed_stereo_without_volume_changes(self):
        renderer=SampleRenderer(decode_sample(block()),rate=10000)
        self.assertEqual(struct.unpack('<6h',renderer.render(3)),(-32768,-32768,0,0,32512,32512))
        self.assertEqual(renderer.render(5),bytes(20));self.assertEqual(renderer.position,3)

    def test_fractional_rate_uses_exact_hold_boundaries_and_duration(self):
        sample=Sample(145,bytes(range(17)));renderer=SampleRenderer(sample,rate=48000)
        expected=[]
        for i in range(sample.frames()):expected.extend([(sample.pcm[i*1000000//(111*48000)]-128)*256]*2)
        self.assertEqual(struct.unpack('<'+'h'*len(expected),renderer.render(renderer.total)),tuple(expected))
        self.assertEqual(renderer.total,91)

    def test_chunking_and_restored_position_match_one_continuous_render(self):
        sample=Sample(166,bytes(range(256))*3);complete=SampleRenderer(sample).render(sample.frames())
        renderer=SampleRenderer(sample);pieces=[]
        for count in (0,1,7,1024,2048,sample.frames()-3080):pieces.append(renderer.render(count))
        self.assertEqual(b''.join(pieces),complete)
        for position in (0,1,7,sample.frames()//2,sample.frames()-1,sample.frames()):
            result=SampleRenderer(sample,position=position).render(97)
            self.assertEqual(result,(complete[position*4:(position+97)*4]+bytes(388))[:388])

    def test_invalid_renderer_arguments_do_not_move_position(self):
        renderer=SampleRenderer(Sample(156,b'abc'));position=renderer.position
        for frames in (-1,True,65537):
            with self.assertRaises(GameError):renderer.render(frames)
            self.assertEqual(renderer.position,position)
        for value in (-1,True,999):
            with self.assertRaises(GameError):SampleRenderer(renderer.sample,position=value)

    def test_wave_contains_exact_pcm_without_device_dependency(self):
        sample=Sample(156,b'abc')
        with wave.open(io.BytesIO(sample.wav(10000)),'rb') as stream:
            self.assertEqual((stream.getnchannels(),stream.getsampwidth(),stream.getframerate(),stream.getnframes()),(2,2,10000,3))
            self.assertEqual(stream.readframes(3),SampleRenderer(sample,rate=10000).render(3))

    def test_driver_transform_reverses_and_xors_original_length(self):
        self.assertEqual(decode_driver(bytes([1,2,3,4])),bytes([0,0,0,0]))
        with self.assertRaises(GameError):decode_driver(bytes(6001))

    def test_content_names_allow_original_hyphen_and_reject_path_traversal(self):
        from openreunion.dos.content import ContentSource
        with tempfile.TemporaryDirectory() as directory:
            source=object.__new__(ContentSource);source.root=Path(directory);source.bundled=False
            (source.root/'SOUND').mkdir();(source.root/'SOUND/CLICK-OK.SMP').write_bytes(block())
            self.assertEqual(source.sample('click-ok'),decode_sample(block()))
            for name,folder in (('../X','SOUND'),('X','../SOUND'),('X/Y','SOUND'),('X\\Y','SOUND')):
                with self.assertRaises(GameError):source.sample(name,folder)


if __name__=='__main__':unittest.main()
