"""Literal translations of bounded DOS arithmetic; see differential validation.

These functions preserve original 16-bit arithmetic. Application code must reject
unsafe player inputs before calling them; wraparound here is reference behavior.
"""
from dataclasses import dataclass


def i16(value):
    value &= 0xFFFF
    return value-65536 if value & 0x8000 else value


def trunc_div(numerator, denominator):
    if denominator == 0:
        raise ZeroDivisionError("Original DOS division by zero")
    quotient = abs(numerator)//abs(denominator)
    return -quotient if (numerator < 0) != (denominator < 0) else quotient


@dataclass(frozen=True)
class ProductionResult:
    stock: int
    queued: int
    work_remaining: int
    completed: bool


def production_tick(stock, queued, base_work, work_remaining, workforce, *, buying=False):
    """REUNION.PRG 0x10ABB..0x10AF9, one product per invocation of the outer tick."""
    if queued == 0 or buying:
        return ProductionResult(stock, queued, work_remaining, False)
    work_remaining = i16(work_remaining-workforce)
    if work_remaining > 0:
        return ProductionResult(stock, queued, work_remaining, False)
    stock, queued = i16(stock+1), i16(queued-1)
    return ProductionResult(stock, queued, base_work if queued > 0 else 0, True)


@dataclass(frozen=True)
class ResearchResult:
    remaining: int
    state: int
    threshold: int
    decrement: int
    completed: bool


def research_tick(state, remaining, duration, requirements, skills, developer_level, *, blocked=False):
    """REUNION.PRG 0x10876..0x10942; excludes subsequent campaign/UI side effects."""
    if len(requirements) != 4 or len(skills) != 4:
        raise ValueError("Exactly four research subjects are required")
    deficit = sum(max(0, requirement-skill) for requirement, skill in zip(requirements, skills))
    threshold = 10000-trunc_div(10000, deficit+1)
    if state not in (2, 4) or blocked:
        return ResearchResult(remaining, state, threshold, 0, False)
    decrement = 0
    if remaining > threshold:
        decrement = trunc_div(developer_level*10000, duration)
        remaining = i16(remaining-decrement)
    if remaining <= 0:
        return ResearchResult(0, 5, threshold, decrement, True)
    return ResearchResult(remaining, state, threshold, decrement, False)


def displayed_production_time(queued, base_work, work_remaining, workforce):
    """DOS display formula at 0x29076..0x290D6; distinct from actual tick scheduling."""
    return trunc_div((queued-1)*base_work+work_remaining+workforce-1, workforce)


def calendar_tick(date):
    """0x10380..0x103C4: 24-hour days, 30-day months, 12-month years.

    Does not execute the monthly event callback or screen redraw.
    """
    year, month, day, hour = date
    hour = (hour+1) & 0xFFFF
    if hour > 23:
        hour, day = 0, (day+1) & 0xFFFF
    if day > 30:
        day, month = 1, (month+1) & 0xFFFF
    if month > 12:
        month, year = 1, (year+1) & 0xFFFF
    return [year, month, day, hour]
