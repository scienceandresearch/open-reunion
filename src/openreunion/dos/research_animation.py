"""Pure research-disc copy and transition plans recovered from the DOS code.

The controller owns scheduling, host bitmap calls and session mutation.  This
module only returns immutable copy/cadence data for the traced routines
22B5A, 22CEE, 22DEA and 22EBB; it is intentionally not wired into a renderer.
"""
from dataclasses import dataclass

from ..core import GameError, integer


PRODUCT_COUNT = 35
CELL_BASE = 0x4240
CELL_ROW_STRIDE = 0x1400
CELL_COLUMN_STRIDE = 0x20
STATIC_FRAME_ARGUMENTS = {1: 10, 2: 19, 3: 30, 4: 39, 5: 0}
SPINNER_FIRST_ARGUMENT = 40
SPINNER_LAST_ARGUMENT = 48
SPINNER_CYCLE = 45
SPINNER_CALLS_PER_ITERATION = 3
RETRACE_CALLS = 1

_TRANSITION_ARGUMENTS = {
    "22DEA": {
        1: (9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0),
        2: (19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 10),
        4: (39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 30),
    },
    "22EBB": {
        1: (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9),
        2: (10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 19),
        4: (30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 39),
    },
}


def _cell_product(value, label="Product"):
    return integer(value, label, minimum=1, maximum=PRODUCT_COUNT)


def _active_product(value, label="Active product"):
    return integer(value, label, maximum=PRODUCT_COUNT)


def cell_destination(product_id):
    """Return the original 320x200 destination offset for one product cell."""
    _cell_product(product_id)
    row, column = divmod(product_id - 1, 5)
    return CELL_BASE + row * CELL_ROW_STRIDE + column * CELL_COLUMN_STRIDE


def _copy(source_frame_argument, product_id):
    integer(source_frame_argument, "Research source frame", maximum=SPINNER_LAST_ARGUMENT)
    _cell_product(product_id)
    source_offset = ((source_frame_argument // 10) * 0x12C0
                     + source_frame_argument * 32)
    return CopyFrame(source_frame_argument, source_offset, cell_destination(product_id))


def static_copy(research_state, product_id):
    """Return the static `22B5A` copy, or ``None`` for state zero."""
    integer(research_state, "Research state", maximum=5)
    _cell_product(product_id)
    frame = STATIC_FRAME_ARGUMENTS.get(research_state)
    return None if frame is None else _copy(frame, product_id)


@dataclass(frozen=True)
class CopyFrame:
    source_frame_argument: int
    source_offset: int
    destination_offset: int


@dataclass(frozen=True)
class SpinnerGuard:
    """Original `22CEE` gates plus the modern explicit research pause."""

    active_product: int
    developer_level: int
    research_block_remaining: int
    training_role: int
    remaining: int
    threshold: int
    research_paused: bool = False

    def __post_init__(self):
        _active_product(self.active_product)
        integer(self.developer_level, "Developer level", maximum=0xFFFF)
        integer(self.research_block_remaining, "Research block remaining", maximum=0xFFFF)
        integer(self.training_role, "Training role", maximum=0xFFFF)
        integer(self.remaining, "Research remaining", maximum=0xFFFF)
        integer(self.threshold, "Research threshold", maximum=0xFFFF)
        if type(self.research_paused) is not bool:
            raise GameError("Research paused must be a boolean.")

    def accepts(self):
        return (self.active_product != 0 and self.developer_level != 0
                and self.research_block_remaining == 0
                and self.training_role != 4 and not self.research_paused
                and self.remaining > self.threshold)


@dataclass(frozen=True)
class SpinnerFrame:
    counter_before: int
    counter_after: int
    copy: CopyFrame


def spinner_frame(counter, product_id, guard):
    """Return one accepted `22CEE` frame, or ``None`` when a raw guard rejects it."""
    integer(counter, "Spinner counter", maximum=SPINNER_CYCLE - 1)
    _active_product(product_id, "Active product")
    if not isinstance(guard, SpinnerGuard) or guard.active_product != product_id:
        raise GameError("Spinner guard must describe the active product.")
    if not guard.accepts():
        return None
    argument = SPINNER_FIRST_ARGUMENT + counter // 5
    after = (counter + 1) % SPINNER_CYCLE
    return SpinnerFrame(counter, after, _copy(argument, product_id))


@dataclass(frozen=True)
class TransitionStep:
    iteration: int
    transition: CopyFrame
    spinner_frames: tuple
    spinner_invocations: int
    retrace_calls: int


@dataclass(frozen=True)
class TransitionPlan:
    routine: str
    selector: int
    target_product: int
    active_product: int
    counter_before: int
    counter_after: int
    steps: tuple

    @property
    def spinner_invocations(self):
        return sum(step.spinner_invocations for step in self.steps)

    @property
    def retrace_calls(self):
        return sum(step.retrace_calls for step in self.steps)

    @property
    def spinner_copies(self):
        return sum(len(step.spinner_frames) for step in self.steps)


def transition_plan(routine, selector, target_product, active_product, counter, *, spinner_guard):
    """Return one exact 11-iteration `22DEA` or `22EBB` caller plan.

    ``selector`` is the CDS transition family (1, 2 or 4), while
    ``target_product`` is the one-based product cell passed as the first
    original argument.  The caller skips `22CEE` only when the active product
    equals that target.  The following retrace call still occurs at every
    conditional call site, including that skip.  A guard-rejected `22CEE`
    produces no spinner copy or counter advance but still has its retrace.
    """
    if routine not in _TRANSITION_ARGUMENTS:
        raise GameError("Unknown research transition routine.")
    integer(selector, "Research transition selector", minimum=1, maximum=4)
    if selector not in _TRANSITION_ARGUMENTS[routine]:
        raise GameError("Research transition selector is not traced.")
    _cell_product(target_product, "Target product")
    _active_product(active_product, "Active product")
    integer(counter, "Spinner counter", maximum=SPINNER_CYCLE - 1)
    if not isinstance(spinner_guard, SpinnerGuard) or spinner_guard.active_product != active_product:
        raise GameError("Transition guard must describe the active product.")

    calls = (SPINNER_CALLS_PER_ITERATION if active_product != target_product else 0)
    current = counter
    steps = []
    for iteration, argument in enumerate(_TRANSITION_ARGUMENTS[routine][selector]):
        frames = []
        for _ in range(calls):
            frame = spinner_frame(current, active_product, spinner_guard)
            if frame is not None:
                frames.append(frame)
                current = frame.counter_after
        steps.append(TransitionStep(
            iteration, _copy(argument, target_product), tuple(frames), calls,
            SPINNER_CALLS_PER_ITERATION * RETRACE_CALLS))
    return TransitionPlan(routine, selector, target_product, active_product,
                          counter, current, tuple(steps))
