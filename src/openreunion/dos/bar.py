"""Timed bar missions, recovered from 0x103EE..0x1083A.

Five agent statuses already belong to campaign flags. Their saved agent records
omit that field so conversations, battles and missions have one writable owner.
"""
from copy import deepcopy
import struct

from ..core import GameError, integer
from .campaign import random_bounded
from .catalog import ORE_KEYS
from .savefile import SaveBlocks

STATUS_FLAGS = {2: "164", 5: "1b5", 7: "1eb", 9: "221", 10: "23c"}


def read_bar(data):
    from .bar_dialogs import SOCIAL_FLAGS
    blocks = SaveBlocks(data)
    agents = []
    for index in range(1, 11):
        raw = blocks.read(0x11F+27*index, 27)
        record = {"prefix": list(raw[:15]), "remaining": struct.unpack_from("<h", raw, 16)[0],
                  "parameter": raw[18], "suffix": list(raw[19:])}
        if index not in STATUS_FLAGS: record["status"] = raw[15]
        agents.append(record)
    return {"agents": agents, "contracts": [list(blocks.read(0x40C+24*i, 24)) for i in range(1, 11)],
            "intelligence": list(blocks.read(0x6518, 12)), "earth_sabotaged": blocks.number(0x5D9A, "B"),
            "social":{key:blocks.number(int(key,16),"B") for key in SOCIAL_FLAGS},"conversation":None}


def validate_bar(bar):
    # Older modern saves omitted these records. None preserves that fact;
    # reconstructing live mission timers from initial data would invent history.
    if bar is None: return
    if not isinstance(bar, dict) or set(bar) != {"agents", "contracts", "intelligence", "earth_sabotaged","social","conversation"}:
        raise GameError("Invalid bar mission fields.")
    from .bar_dialogs import SOCIAL_FLAGS
    if bar["social"] is None:
        if bar["conversation"] is not None:raise GameError("Missing knowledge flags for bar conversation.")
    else:
        if not isinstance(bar["social"],dict) or set(bar["social"])!=set(SOCIAL_FLAGS):raise GameError("Incomplete bar knowledge flags.")
        for value in bar["social"].values():integer(value,"Bar knowledge flag",maximum=255)
    def bytes_table(value, size):
        if not isinstance(value, list) or len(value) != size: raise GameError("Invalid bar record size.")
        for byte in value: integer(byte, "Bar byte", maximum=255)
    integer(bar["earth_sabotaged"], "Earth sabotage flag", maximum=255)
    bytes_table(bar["intelligence"], 12)
    for key in ("agents", "contracts"):
        if not isinstance(bar[key], list) or len(bar[key]) != 10: raise GameError("Ten bar records are required.")
    for index, row in enumerate(bar["agents"], 1):
        expected = {"prefix", "remaining", "parameter", "suffix"}
        if index not in STATUS_FLAGS: expected.add("status")
        if not isinstance(row, dict) or set(row) != expected: raise GameError("Invalid agent fields or duplicated status.")
        bytes_table(row["prefix"], 15); bytes_table(row["suffix"], 8)
        integer(row["remaining"], "Mission timer", minimum=-32768, maximum=32767)
        integer(row["parameter"], "Mission parameter", maximum=255)
        if "status" in row: integer(row["status"], "Agent status", maximum=255)
    for row in bar["contracts"]: bytes_table(row, 24)


def agent_status(work, index):
    return work["flags"][STATUS_FLAGS[index]] if index in STATUS_FLAGS else work["bar"]["agents"][index-1]["status"]


def intelligence_reports(work, race, kind):
    """Read-only report selectors inside 0x202B9; values are captured now."""
    integer(race, "Intelligence civilization", minimum=2, maximum=12)
    integer(kind, "Intelligence report", minimum=1, maximum=4)
    reports = []
    civilization = work["civilizations"][race-2]
    if kind in (1, 3):
        # Original traversal visits each primary followed by its moons.
        for identity in sorted(work["worlds"], key=lambda key: tuple(map(int, key.split(":")))):
            raw = work["worlds"][identity]["raw"]
            if raw[0] != race: continue
            forces=list(struct.unpack_from('<8I',bytes(raw),27))
            # DOS omits non-colony garrisons, although their ships participate
            # in orbital combat. Detailed military intelligence must include
            # those defenses. The colony-only purchase still lists colonies.
            if not raw[6] and (kind!=3 or not any(forces)):continue
            report = {"world": identity, "base": bool(raw[1])}
            if kind == 3:
                report['forces']=forces
                if not raw[6]:report['garrison']=True
            reports.append(report)
    elif kind == 2:
        from .aliens import fleet_at
        for slot in range(1, civilization[38]+1):
            raw = fleet_at(civilization, slot)
            if raw[0] > 0 and raw[2] > 0:
                reports.append({"slot": slot, "forces": list(struct.unpack_from("<8H", bytes(raw), 11))})
    else:
        reports.append({"weapons": [i+1 for i in range(8) if civilization[19+i]]})
    return {"race": race, "kind": kind, "reports": reports}


def bar_hour(state):
    """Return a copied work state and ordered semantic notices for one hour.

    Ore reward indices deliberately follow their original displayed names.
    The DOS addition is one stock too far forward (Texon writes DS95DA).
    Invalid active targets and overflowing awards fail atomically at the session
    boundary instead of corrupting neighboring fields or wrapping inventory.
    """
    state = deepcopy(state)
    bar = state["bar"]
    if bar is None: return state, []
    events = []
    def message(number): events.append(("message", number))
    def unlock(product, complete):
        row = state["products"][product-1]
        if row["research_state"] == 0:
            row["research_state"] = 5 if complete else 3
            if complete: row["research_remaining"] = 0
    for index, row in enumerate(bar["agents"], 1):
        if agent_status(state, index) not in (0, 2) or row["remaining"] <= 0: continue
        row["remaining"] -= 1
        if row["remaining"]: continue
        parameter = row["parameter"]
        if index == 2:
            kind, race = divmod(parameter, 20)
            report = intelligence_reports(state, race, kind)
            message(39); events.append(("intelligence", report))
            if kind == 1 and bar["intelligence"][race-1] != 2: bar["intelligence"][race-1] = 1
            if kind == 3: bar["intelligence"][race-1] = 2
        elif index == 5:
            if parameter in (1, 2): state["civilizations"][parameter+4][27] = 6
            message(40)
            if parameter == 1: message(43)
            if parameter == 2:
                message(44); unlock(29, True); unlock(26, False)
                bar["agents"][2]["status"] = 2
        elif index == 7:
            bar["earth_sabotaged"] = 1; state["flags"]["1eb"] = 1
            if "8:3:0" not in state["worlds"]: raise GameError("Earth is missing from the campaign.")
            raw = state["worlds"]["8:3:0"]["raw"]
            quantities = struct.unpack_from("<8i", bytes(raw), 27)
            raw[27:59] = struct.pack("<8I", *(max(0, value-damage) for value, damage in
                zip(quantities, (20, 0, 1, 2, 0, 10, 10, 10))))
            message(41)
        elif index == 9:
            integer(parameter, "Pirate contract selection", minimum=1, maximum=20)
            divisor = 2 if parameter > 10 else 1
            contract = bar["contracts"][(parameter-1) % 10]
            state["rng"], roll = random_bounded(state["rng"], 100)
            if contract[13] > roll:
                message(47)
                for code, amount in zip(contract[:4], struct.unpack_from("<4H", bytes(contract), 4)):
                    if not code: continue
                    amount //= divisor
                    if 1 <= code <= 6:
                        key = ORE_KEYS[code-1]
                        total = state["resources"][key]+amount
                        integer(total, "Mission ore stock", maximum=2**32-1)
                        state["resources"][key] = total
                        events.append(("ore_reward", {"ore": key, "quantity": amount}))
                    elif 11 <= code <= 45:
                        product = state["products"][code-11]
                        total = product["stock"]+amount
                        integer(total+product.get("queued", 0), "Mission stock and pending production", maximum=32767)
                        product["stock"] = total
                        events.append(("product_reward", {"product": code-10, "quantity": amount}))
                    else: raise GameError("Pirate contract has an invalid reward code.")
            else: message(42)
            contract[19:21] = [0, 0]
        row["parameter"] = 0
    for index, contract in enumerate(bar["contracts"], 1):
        date = [struct.unpack_from("<h", bytes(contract), 14)[0], *contract[16:19]]
        if date == state["date"]:
            # DOS tests Random(3) >= 4: its cancellation arm is unreachable.
            state["rng"], _ = random_bounded(state["rng"], 3)
            events.append(("pirate_announcement", index))
    # 0x1B948 exits DOS through 0x36A03 when the legacy guard DS088A is 263.
    # This runtime termination mechanism is deliberately not carried into the
    # modern campaign. Desktop refresh replaces DS95E6/95F5 invalidation.
    return state, events
