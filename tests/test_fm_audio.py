"""Original-free checks of rational audio scheduling and output boundaries."""
from pathlib import Path
import ctypes
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.fm_audio import FmRenderer,OplSynth,PIT_HZ,BIOS_DIVISOR,render_wave
from openreunion.dos.fm_music import decode_music
from openreunion.dos.audio_output import AudioPlayer,WaveOutput,WaveTime
from test_fm_music import fixture,pack


class FakeSynth:
    rate=48000
    def __init__(self):self.frames=0;self.events=[];self.closed=False
    def write(self,writes):self.events.append((self.frames,list(writes)))
    def generate(self,frames):self.frames+=frames;return bytes(frames*4)
    def close(self):self.closed=True


class FmAudioTests(unittest.TestCase):
    def song(self):return decode_music(pack(fixture([(0,0,49,0xF0),(1,0,127,0)])))

    def test_block_boundaries_do_not_change_samples_or_tick_positions(self):
        first=FakeSynth();second=FakeSynth()
        a=FmRenderer(self.song(),synth=first);b=FmRenderer(self.song(),synth=second)
        expected=a.render(96000)
        pieces=[b.render(n) for n in (1,2635,0,17,65000,28347)]
        self.assertEqual(b''.join(pieces),expected)
        self.assertEqual(first.events,second.events)
        self.assertEqual(a.player.__dict__,b.player.__dict__)

    def test_first_interrupt_waits_one_tick_and_long_run_has_no_drift(self):
        synth=FakeSynth();renderer=FmRenderer(self.song(),synth=synth)
        first=48000*BIOS_DIVISOR//PIT_HZ
        renderer.render(first);self.assertEqual(renderer.ticks,0)
        renderer.render(1);self.assertEqual(synth.events[1][0],first)
        for _ in range(600):renderer.render(48000)
        for index,(position,_) in enumerate(synth.events):
            self.assertEqual(position,index*48000*BIOS_DIVISOR//PIT_HZ)

    def test_invalid_lengths_do_not_advance_or_close_synth(self):
        synth=FakeSynth();renderer=FmRenderer(self.song(),synth=synth)
        for count in (-1,192001,True,2.5):
            with self.assertRaises(GameError):renderer.render(count)
        self.assertEqual(renderer.frames,0);self.assertFalse(synth.closed)
        renderer.close();self.assertTrue(synth.closed)

    def test_existing_wave_is_not_overwritten_and_synth_closes(self):
        synth=FakeSynth()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'recording.wav';path.write_bytes(b'keep')
            with patch('openreunion.dos.fm_audio.OplSynth',return_value=synth):
                with self.assertRaises(FileExistsError):render_wave(self.song(),path,1)
            self.assertEqual(path.read_bytes(),b'keep');self.assertTrue(synth.closed)

    def test_missing_library_and_invalid_rate_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(GameError):OplSynth(library=Path(directory)/'absent.dll')
        for rate in (0,7999,192001,True):
            with self.assertRaises(GameError):OplSynth(rate)

    def test_output_failure_closes_device_and_renderer(self):
        flags=[]
        class Renderer:
            rate=48000;frames=0
            def __enter__(self):return self
            def __exit__(self,*_):flags.append('renderer closed')
        class Device:
            def __init__(self,rate):pass
            def fill(self,renderer):raise GameError('device disconnected')
            def close(self):flags.append('device closed')
        player=AudioPlayer()
        with patch('openreunion.dos.audio_output.FmRenderer',return_value=Renderer()),patch('openreunion.dos.audio_output.WaveOutput',Device):
            player.start(self.song());player._thread.join(1)
        self.assertFalse(player.playing);self.assertEqual(player.error,'device disconnected')
        self.assertEqual(flags,['device closed','renderer closed']);player.stop()

    def test_missing_synth_is_reported_without_starting_output(self):
        player=AudioPlayer()
        with patch('openreunion.dos.audio_output.FmRenderer',side_effect=GameError('missing synth')),patch('openreunion.dos.audio_output.WaveOutput') as device:
            player.start(self.song());player._thread.join(1)
        self.assertFalse(player.playing);self.assertEqual(player.error,'missing synth')
        self.assertFalse(device.called);player.stop()

    def test_device_position_unwraps_multiple_rollovers_in_each_format(self):
        for kind in (1,2,4):
            with self.subTest(kind=kind):
                values=iter((2**32-8,4,2**32-4,8))
                class Api:
                    def waveOutGetPosition(self,handle,pointer,size):
                        value=ctypes.cast(pointer,ctypes.POINTER(WaveTime)).contents
                        value.kind=kind;value.value=next(values);return 0
                device=WaveOutput.__new__(WaveOutput)
                device.api=Api();device.handle=None;device.rate=48000;device._position_counts={}
                counts=(2**32-8,2**32+4,2*2**32-4,2*2**32+8)
                expected=[n if kind==2 else n//4 if kind==4 else n*48 for n in counts]
                self.assertEqual([device.position() for _ in counts],expected)

    def test_restored_pause_failure_closes_opened_device(self):
        flags=[]
        class Renderer:
            rate=48000;frames=0
            def seek(self,frames,cancelled):self.frames=frames;return True
            def __enter__(self):return self
            def __exit__(self,*_):flags.append('renderer closed')
        class Device:
            def __init__(self,rate):pass
            def pause(self,value):raise GameError('pause failed')
            def close(self):flags.append('device closed')
        player=AudioPlayer()
        with patch('openreunion.dos.audio_output.FmRenderer',return_value=Renderer()),patch('openreunion.dos.audio_output.WaveOutput',Device):
            player.start(self.song(),frames=12345,paused=True);player._thread.join(1)
        self.assertEqual(player.error,'pause failed');self.assertEqual(player.rendered_frames,12345)
        self.assertEqual(flags,['device closed','renderer closed']);player.stop()


if __name__=='__main__':unittest.main()
