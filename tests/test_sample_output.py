"""Finite sample device lifecycle without requiring a physical audio device."""
import ctypes
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openreunion.core import GameError
from openreunion.dos.audio_output import WaveOutput,WaveHeader
from openreunion.dos.sample_output import SamplePlayer
from openreunion.dos.samples import Sample,SampleRenderer


class Device:
    instances=[]
    def __init__(self,rate):
        self.rate=rate;self.consumed=0;self.queued=bytearray();self.paused=False;self.closed=False
        self.ready=threading.Event();self.instances.append(self)
    def fill(self,renderer,*,remaining=None):
        if remaining:self.queued.extend(renderer.render(min(remaining,4096)))
        self.ready.set()
    def position(self):return self.consumed
    def pause(self,value):self.paused=value
    def close(self):self.closed=True


class SampleOutputTests(unittest.TestCase):
    def setUp(self):
        Device.instances=[];self.player=SamplePlayer()
        self.mock=patch('openreunion.dos.sample_output.WaveOutput',Device);self.mock.start()
        self.addCleanup(self.mock.stop);self.addCleanup(self.player.stop)
        self.sample=Sample(156,bytes(range(200)))

    def wait_for(self,condition):
        until=time.monotonic()+1
        while not condition() and time.monotonic()<until:time.sleep(.001)
        self.assertTrue(condition(),self.player.error)

    def device(self):
        self.wait_for(lambda:bool(Device.instances));return Device.instances[-1]

    def test_drains_finite_output_and_retains_completed_position(self):
        self.player.start(self.sample);device=self.device();self.assertTrue(device.ready.wait(1))
        self.assertEqual(self.player.rendered_frames,self.sample.frames())
        self.assertEqual(self.player.position(),0);self.assertTrue(self.player.playing)
        device.consumed=self.sample.frames()+100
        self.wait_for(lambda:not self.player.playing)
        self.assertTrue(self.player.completed);self.assertTrue(device.closed)
        self.assertEqual(self.player.position(),self.sample.frames());self.assertIsNone(self.player.error)
        self.assertEqual(bytes(device.queued),SampleRenderer(self.sample).render(self.sample.frames()))

    def test_pause_stop_and_resume_use_consumed_not_queued_position(self):
        self.player.start(self.sample);device=self.device();self.assertTrue(device.ready.wait(1))
        device.consumed=41;self.player.pause(True)
        self.assertTrue(device.paused);self.assertEqual(self.player.position(),41)
        queued=len(device.queued);time.sleep(.02);self.assertEqual(len(device.queued),queued)
        self.player.stop();self.assertTrue(device.closed);self.assertEqual(self.player.position(),41)
        self.assertFalse(self.player.completed)
        self.player.start(self.sample,frames=41,paused=True)
        self.wait_for(lambda:len(Device.instances)==2 and Device.instances[-1].paused)
        second=Device.instances[-1];self.assertEqual(len(second.queued),0);self.assertEqual(self.player.position(),41)
        self.player.pause(False);self.assertTrue(second.ready.wait(1))
        expected=SampleRenderer(self.sample,position=41).render(self.sample.frames()-41)
        self.assertEqual(bytes(second.queued),expected)

    def test_replacement_closes_old_device_before_opening_new_one(self):
        self.player.start(self.sample);first=self.device();self.assertTrue(first.ready.wait(1))
        seen=[]
        class Replacement(Device):
            def __init__(self,rate):seen.append(first.closed);super().__init__(rate)
        with patch('openreunion.dos.sample_output.WaveOutput',Replacement):
            self.player.start(Sample(145,b'\x80'*500));self.wait_for(lambda:len(Device.instances)==2)
        self.assertEqual(seen,[True]);self.assertEqual(self.player.position(),0)

    def test_invalid_resume_keeps_active_device_and_end_resume_opens_none(self):
        self.player.start(self.sample);first=self.device();self.assertTrue(first.ready.wait(1))
        for args in ({'frames':True},{'frames':-1},{'frames':self.sample.frames()+1},{'paused':1}):
            with self.assertRaises(GameError):self.player.start(self.sample,**args)
            self.assertTrue(self.player.playing);self.assertFalse(first.closed)
        self.player.start(self.sample,frames=self.sample.frames())
        self.assertTrue(first.closed);self.assertEqual(len(Device.instances),1)
        self.assertTrue(self.player.completed);self.assertFalse(self.player.playing)

    def test_device_failures_close_and_preserve_consumed_position(self):
        for failure in ('fill','pause','position'):
            with self.subTest(failure=failure):
                class Broken(Device):
                    def fill(self,renderer,**kw):
                        if failure=='fill':raise GameError('disconnected')
                        super().fill(renderer,**kw)
                    def pause(self,value):
                        if failure=='pause':raise GameError('disconnected')
                    def position(self):
                        if failure=='position':raise GameError('disconnected')
                        return 0
                with patch('openreunion.dos.sample_output.WaveOutput',Broken):
                    self.player.start(self.sample,frames=17,paused=failure=='pause')
                    self.wait_for(lambda:not self.player.playing)
                self.assertEqual(self.player.error,'disconnected');self.assertTrue(Device.instances[-1].closed)
                self.assertEqual(self.player.position(),17);self.assertFalse(self.player.completed)

    def test_open_failure_can_be_retried(self):
        with patch('openreunion.dos.sample_output.WaveOutput',side_effect=GameError('unavailable')):
            self.player.start(self.sample,frames=18);self.wait_for(lambda:not self.player.playing)
        self.assertEqual(self.player.position(),18);self.assertEqual(self.player.error,'unavailable')
        self.player.start(self.sample,frames=18);self.device()
        self.assertIsNone(self.player.error)

    def test_finite_wave_queue_pads_only_last_block_and_does_not_requeue_silence(self):
        output=WaveOutput.__new__(WaveOutput);output.handle=None;output.buffers=[];written=[]
        for _ in range(4):
            data=ctypes.create_string_buffer(output.block_frames*4)
            header=WaveHeader(ctypes.cast(data,ctypes.c_void_p),len(data),0,0,0,0,None,0)
            output.buffers.append((data,header))
        class Api:
            def waveOutWrite(self,handle,pointer,size):
                header=ctypes.cast(pointer,ctypes.POINTER(WaveHeader)).contents
                written.append(ctypes.string_at(header.data,header.length));header.flags|=16;return 0
        output.api=Api();renderer=SampleRenderer(self.sample)
        output.fill(renderer,remaining=renderer.total)
        self.assertEqual(len(written),1)
        self.assertEqual(written[0],SampleRenderer(self.sample).render(1024))
        output.buffers[0][1].flags=0
        output.fill(renderer,remaining=renderer.total-renderer.position)
        self.assertEqual(len(written),1)

    def test_bad_pcm_block_never_reaches_native_copy_or_device(self):
        output=WaveOutput.__new__(WaveOutput);output.buffers=[(None,WaveHeader())]
        class BadRenderer:
            def render(self,n):return b'x'
        with self.assertRaises(GameError):output.fill(BadRenderer())


if __name__=='__main__':unittest.main()
