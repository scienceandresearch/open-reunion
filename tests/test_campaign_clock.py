"""Timer cancellation, encounter barriers and exact hourly command cadence."""
from copy import deepcopy
import unittest
from test_recovered import fixture
from openreunion.dos.campaign_clock import CampaignClock,pause_reason
from openreunion.dos.session import RecoveredSession


class Scheduler:
    def __init__(self):self.callbacks={};self.counter=0
    def after(self,delay,callback):
        self.counter+=1;self.callbacks[self.counter]=(delay,callback);return self.counter
    def after_cancel(self,key):self.callbacks.pop(key,None)
    def fire(self):
        key=next(iter(self.callbacks));_,callback=self.callbacks.pop(key);callback()


class ClockTests(unittest.TestCase):
    def clock(self):
        catalog,state=fixture();session=RecoveredSession(catalog,state);sessions=[session];scheduler=Scheduler()
        clock=CampaignClock(scheduler,lambda:sessions[0],lambda:sessions[0].apply('advance',hours=1))
        return clock,scheduler,sessions

    def test_running_matches_manual_hours_without_changing_saved_schema(self):
        clock,timer,sessions=self.clock();s=sessions[0];manual=RecoveredSession(s.catalog,deepcopy(s.state))
        before=deepcopy(s.state);clock.start();self.assertEqual(s.state,before)
        for interval in (1000,250,83):
            clock.set_interval(interval)
            for _ in range(8):
                self.assertEqual(len(timer.callbacks),1);self.assertEqual(next(iter(timer.callbacks.values()))[0],interval)
                timer.fire();manual.apply('advance',hours=1)
                self.assertEqual(s.state,manual.state)
        clock.pause();self.assertFalse(timer.callbacks)

    def test_canceled_callback_cannot_advance_or_install_a_timer(self):
        clock,timer,sessions=self.clock();clock.start();stale=next(iter(timer.callbacks.values()))[1]
        clock.pause();before=deepcopy(sessions[0].state);stale()
        self.assertEqual(sessions[0].state,before);self.assertFalse(timer.callbacks)
        clock.start();current=clock.pending;stale();self.assertEqual(clock.pending,current)
        self.assertEqual(len(timer.callbacks),1)

    def test_loaded_session_stops_before_any_command(self):
        clock,timer,sessions=self.clock();clock.start();s=sessions[0]
        sessions[0]=RecoveredSession(s.catalog,deepcopy(s.state));before=deepcopy(sessions[0].state)
        timer.fire();self.assertFalse(clock.running);self.assertFalse(timer.callbacks);self.assertEqual(sessions[0].state,before)

    def test_each_encounter_barrier_prevents_start_and_stops_a_live_clock(self):
        edits=[lambda s:s.update(active_dialog={}),lambda s:s.update(active_scene={}),
               lambda s:s['presentation_requests'].append({'kind':'message','id':1}),
               lambda s:s['battle_requests'].append({}),
               lambda s:s.update(ground_encounter={'phase':'setup'}),lambda s:s.update(space_encounter={'phase':'result'}),
               lambda s:s['campaign'].update(bar={'conversation':{}}),
               lambda s:s.update(campaign_phase='victory'),lambda s:s.update(campaign_phase='defeat')]
        for edit in edits:
            clock,timer,sessions=self.clock();clock.start();edit(sessions[0].state);before=deepcopy(sessions[0].state)
            timer.fire();self.assertFalse(clock.running);self.assertFalse(timer.callbacks);self.assertEqual(before,sessions[0].state)
            clock.start();self.assertFalse(clock.running);self.assertFalse(timer.callbacks)

    def test_barrier_created_by_an_hour_stops_before_the_next_hour(self):
        clock,timer,sessions=self.clock();hours=[]
        def step():hours.append(1);sessions[0].state['presentation_requests'].append({'kind':'message','id':1})
        clock.step=step;clock.start();timer.fire()
        self.assertEqual(hours,[1]);self.assertFalse(clock.running);self.assertFalse(timer.callbacks)

    def test_modal_dialog_and_error_stop_without_retry(self):
        clock,timer,sessions=self.clock();clock.start();clock.blocked=lambda:'Modal dialog';timer.fire()
        self.assertFalse(clock.running);self.assertFalse(timer.callbacks)
        clock.blocked=lambda:None
        def fail():raise RuntimeError('test failure')
        clock.step=fail;clock.start()
        with self.assertRaises(RuntimeError):timer.fire()
        self.assertFalse(clock.running);self.assertFalse(timer.callbacks)

    def test_speed_change_and_pause_inside_step_never_duplicate_callbacks(self):
        clock,timer,_=self.clock();clock.step=lambda:clock.set_interval(83);clock.start();timer.fire()
        self.assertEqual(len(timer.callbacks),1)
        clock.step=clock.pause;timer.fire();self.assertFalse(timer.callbacks)

    def test_closed_battles_do_not_block_and_invalid_speed_does_not_mutate_clock(self):
        clock,timer,sessions=self.clock();sessions[0].state['space_encounter']={'phase':'closed'}
        self.assertIsNone(pause_reason(sessions[0]));clock.start();pending=clock.pending
        with self.assertRaises(ValueError):clock.set_interval(1)
        self.assertEqual(clock.pending,pending);self.assertEqual(clock.interval,1000)


if __name__=='__main__':unittest.main()
