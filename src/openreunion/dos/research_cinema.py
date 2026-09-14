"""Nonblocking original research discs over transactional research actions."""
from collections import deque
from time import monotonic_ns
import tkinter as tk

from .catalog import SUBJECTS
from .research_animation import SpinnerGuard, spinner_frame, transition_plan
from .rules import research_tick
from .video_timing import RetraceClock


class ResearchCinema:
    def __init__(self, app):
        self.app = app
        self.timer = None
        self.owner = None
        self.signature = None
        self.counter = 0
        self.spinner = None
        self.disc = None
        self.phases = deque()
        self.events = deque()
        self.wait = 0
        self.clock = None
        self.generation = 0

    @property
    def running(self):
        return bool(self.phases or self.events or self.wait)

    def cancel(self):
        self.generation += 1
        if self.timer is not None:
            try:self.app.root.after_cancel(self.timer)
            except tk.TclError:pass
        self.timer = None
        self.phases.clear()
        self.events.clear()
        self.wait = 0
        self.disc = self.spinner = None
        self.clock = None

    def sync(self):
        state = self.app.session.state
        campaign = state['campaign']
        signature = (tuple(row['research_state'] for row in state['products']),
                     state['research_paused'], bool(campaign['research_block_remaining']),
                     campaign['training_role'], state['ranks']['developer'],
                     state['levels']['developer'],
                     tuple(state['skills'][key] for key in SUBJECTS))
        if self.owner is not self.app.session or signature != self.signature:
            self.cancel()
            self.counter = 0
            self.owner = self.app.session
            self.signature = signature

    def guard(self):
        state = self.app.session.state
        campaign = state['campaign']
        active = next((i + 1 for i, row in enumerate(state['products'])
                       if row['research_state'] in (2, 4)), 0)
        remaining = threshold = 0
        if active:
            row = state['products'][active - 1]
            definition = self.app.catalog['products'][active - 1]
            remaining = row['research_remaining']
            # blocked=True computes the literal skill threshold without taking
            # a research tick or changing campaign state.
            threshold = research_tick(row['research_state'], remaining,
                definition['research_duration'],
                [definition['requirements'][key] for key in SUBJECTS],
                [state['skills'][key] for key in SUBJECTS],
                state['levels']['developer'], blocked=True).threshold
        return SpinnerGuard(active_product=active, developer_level=state['levels']['developer'],
            research_block_remaining=campaign['research_block_remaining'],
            training_role=campaign['training_role'], remaining=remaining,
            threshold=threshold, research_paused=state['research_paused'])

    def select(self, product):
        """Commit the authorized command once; animate only its presentation.

        Cancelling a visual sequence cannot later apply a command to a different
        session. Completed products retain the original open/close disc effect.
        """
        if self.running:return
        owner = self.app.session
        before = tuple(row['research_state'] for row in self.app.session.state['products'])
        self.app.research_selected = product
        if before[product - 1] != 5:
            self.app.act('research', product_id=product)
        if self.app.session is not owner or self.app.screen != 'research':
            self.cancel()
            return
        self.sync()
        after = tuple(row['research_state'] for row in self.app.session.state['products'])
        phases = []
        if before[product - 1] == 5:
            phases = [('22EBB', 1, product), ('22DEA', 1, product)]
        else:
            for i, (old, new) in enumerate(zip(before, after), 1):
                if old in (2, 4) and new in (1, 3):
                    phases.append(('22DEA', old, i))
            for i, (old, new) in enumerate(zip(before, after), 1):
                if old in (1, 3) and new in (2, 4):
                    phases.append(('22EBB', new, i))
        self.phases.extend(phases)
        self._consume()
        self.app.render_original()

    def _consume(self):
        while not self.wait:
            if not self.events:
                if not self.phases:
                    self.disc = None
                    return
                routine, selector, target = self.phases.popleft()
                guard = self.guard()
                plan = transition_plan(routine, selector, target, guard.active_product,
                                       self.counter, spinner_guard=guard)
                for step in plan.steps:
                    self.events.append(('disc', step.transition))
                    for index in range(step.retrace_calls):
                        if index < len(step.spinner_frames):
                            self.events.append(('spinner', step.spinner_frames[index]))
                        self.events.append(('wait', 1))
            event, value = self.events.popleft()
            if event == 'disc':self.disc = value
            elif event == 'spinner':
                self.counter = value.counter_after
                self.spinner = value.copy
            else:self.wait = value

    def schedule(self):
        if (self.timer is None and self.app.screen == 'research'
                and self.app.startup is None and self.app.original.winfo_ismapped()):
            now = monotonic_ns()
            if self.clock is None:self.clock = RetraceClock(now)
            generation = self.generation
            self.timer = self.app.root.after(self.clock.delay_ms(now),
                lambda:self.app.guard(lambda:self.tick(generation)))

    def tick(self, generation=None):
        if generation is not None and generation != self.generation:return
        self.timer = None
        if self.owner is not self.app.session or self.app.screen != 'research':
            self.cancel()
            return
        if self.app.startup is not None or not self.app.original.winfo_ismapped():
            self.cancel()
            return
        self.sync()
        if self.app.pointer.buttons:
            self.schedule()
            return
        changed = False
        if self.running:
            previous = (self.disc, self.spinner)
            if self.wait:self.wait -= 1
            self._consume()
            changed = previous != (self.disc, self.spinner)
        else:
            guard = self.guard()
            frame = spinner_frame(self.counter, guard.active_product, guard)
            if frame is not None:
                changed = self.spinner != frame.copy
                self.counter = frame.counter_after
                self.spinner = frame.copy
            elif self.spinner is not None:
                self.spinner = None
                changed = True
        if changed:self.app.render_original()
        self.schedule()

    def draw(self, target):
        self.sync()
        picture = None
        for copy in (self.spinner, self.disc):
            if copy is None:continue
            if picture is None:picture = self.app.screen_renderer.asset('CDS')
            sy, sx = divmod(copy.source_offset, 320)
            y, x = divmod(copy.destination_offset, 320)
            target.blit(picture, x, y, source=(sx, sy, 31, 14))
        self.schedule()
