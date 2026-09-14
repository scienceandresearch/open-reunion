"""Serializable domain state. No UI, filesystem, or wall-clock dependencies."""
from dataclasses import asdict, dataclass, field
from importlib.resources import files
import json

ORES = ("detoxin", "energon", "raenium", "kremir", "toxon", "lepitium")
MAX_VALUE = 2**31 - 1
MAX_HOUR = 10_000_000
RULES = json.loads(files("openreunion").joinpath("data/prototype.json").read_text())


class GameError(ValueError):
    """Expected input/rule failure, suitable for presenting to a player."""


def integer(value, label, minimum=0, maximum=MAX_VALUE):
    if type(value) is not int or not minimum <= value <= maximum:
        raise GameError(f"{label} must be an integer from {minimum} to {maximum}.")
    return value


@dataclass
class Building:
    kind: str
    x: int
    y: int
    work_left: int = 0
    active: bool = False


@dataclass
class Planet:
    name: str
    habitable: bool
    colony: bool = False
    surveyed: bool = False
    station: bool = False
    population: int = 0
    tax: int = 10
    ores: dict[str, int] = field(default_factory=lambda: dict.fromkeys(ORES, 0))
    inventory: dict[str, int] = field(default_factory=lambda: dict.fromkeys(RULES["products"], 0))
    buildings: list[Building] = field(default_factory=list)


@dataclass
class Job:
    item: str
    remaining: int
    work_left: int


@dataclass
class Fleet:
    name: str
    planet: str = "new_earth"
    destination: str | None = None
    eta: int = 0
    cargo: dict[str, int] = field(default_factory=dict)


@dataclass
class State:
    schema: int = 1
    ruleset: str = "prototype-v1"
    hour: int = 0
    credits: int = 150000
    planets: dict[str, Planet] = field(default_factory=dict)
    researched: list[str] = field(default_factory=list)
    research: str | None = None
    research_left: int = 0
    production: list[Job] = field(default_factory=list)
    fleets: list[Fleet] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    assisted: bool = False
    admin_log: list[dict] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def new_game():
    earth = Planet("New Earth", True, colony=True, surveyed=True, population=1500)
    earth.ores = dict.fromkeys(ORES, 100)
    earth.buildings = [Building("windtrap", 1, 1), Building("housing", 3, 1),
                      Building("mine", 1, 3), Building("derrick", 3, 3)]
    state = State(planets={"new_earth": earth, "apollo": Planet("Apollo", True),
                           "klatoo": Planet("Klatoo", False), "zeus": Planet("Zeus", False)})
    state.messages.append("Prototype scenario ready. Research a miner droid and a satellite to begin.")
    return state


def validate(state):
    if not isinstance(state.planets, dict) or any(type(getattr(state, key)) is not list for key in ("researched", "production", "fleets", "messages", "admin_log")):
        raise GameError("Invalid state collection types.")
    if type(state.schema) is not int or state.schema != 1 or state.ruleset != RULES["id"]:
        raise GameError("Unsupported save schema or ruleset.")
    integer(state.hour, "Hour", maximum=MAX_HOUR)
    integer(state.credits, "Credits")
    if type(state.assisted) is not bool:
        raise GameError("Invalid assisted flag.")
    if set(state.planets) != {"new_earth", "apollo", "klatoo", "zeus"}:
        raise GameError("Save must contain the prototype's four worlds.")
    for pid, p in state.planets.items():
        if not isinstance(p.ores, dict) or not isinstance(p.inventory, dict) or type(p.buildings) is not list:
            raise GameError("Invalid planet collection types.")
        if not isinstance(p.name, str) or not 1 <= len(p.name) <= 80:
            raise GameError("Invalid planet name.")
        if any(type(v) is not bool for v in (p.habitable, p.colony, p.surveyed, p.station)):
            raise GameError("Invalid planet flags.")
        if p.colony and (not p.habitable or not p.surveyed):
            raise GameError("A colony must be habitable and surveyed.")
        if pid == "new_earth" and not p.colony:
            raise GameError("New Earth must have a colony.")
        if p.station and not p.surveyed:
            raise GameError("A miner station needs a survey.")
        integer(p.population, "Population")
        integer(p.tax, "Tax", maximum=30)
        if set(p.ores) != set(ORES) or set(p.inventory) != set(RULES["products"]):
            raise GameError("Invalid resource or inventory keys.")
        for key, value in (p.ores | p.inventory).items():
            integer(value, key)
        occupied = set()
        active = 0
        if len(p.buildings) > 144 or (p.buildings and not p.colony):
            raise GameError("Invalid building count or colony.")
        for b in p.buildings:
            if b.kind not in RULES["buildings"] or type(b.active) is not bool:
                raise GameError("Invalid building.")
            integer(b.x, "X", maximum=11)
            integer(b.y, "Y", maximum=11)
            integer(b.work_left, "Building work", maximum=RULES["buildings"][b.kind]["work"])
            if (b.x, b.y) in occupied:
                raise GameError("Buildings overlap.")
            occupied.add((b.x, b.y))
            if b.active:
                if b.kind != "mine" or b.work_left:
                    raise GameError("Only completed mines can have a droid.")
                active += 1
        if active > 9:
            raise GameError("A planet can have at most nine active mines.")
    if len(state.researched) != len(set(state.researched)) or any(x not in RULES["products"] for x in state.researched):
        raise GameError("Invalid research list.")
    for item in state.researched:
        if not set(RULES["products"][item]["requires"]) <= set(state.researched):
            raise GameError("Missing research prerequisite.")
    integer(state.research_left, "Research work")
    if state.research is None:
        if state.research_left != 0:
            raise GameError("No active research for remaining work.")
    elif (state.research not in RULES["products"] or state.research in state.researched
          or not 1 <= state.research_left <= RULES["products"][state.research]["research_work"]
          or not set(RULES["products"][state.research]["requires"]) <= set(state.researched)):
        raise GameError("Invalid research project.")
    if len(state.production) > 1000 or len(state.fleets) > 100:
        raise GameError("Too many orders or fleets.")
    for job in state.production:
        if job.item not in state.researched:
            raise GameError("Production item has not been researched.")
        integer(job.remaining, "Order quantity", 1, 1000)
        integer(job.work_left, "Production work", 1, RULES["products"][job.item]["work"])
    names = set()
    for fleet in state.fleets:
        if not isinstance(fleet.cargo, dict):
            raise GameError("Cargo must be an object.")
        if not isinstance(fleet.name, str) or not 1 <= len(fleet.name) <= 40 or fleet.name in names:
            raise GameError("Fleet names must be unique and 1-40 characters long.")
        names.add(fleet.name)
        if fleet.planet not in state.planets or (fleet.destination is not None and fleet.destination not in state.planets):
            raise GameError("Unknown fleet location.")
        integer(fleet.eta, "Arrival time", maximum=MAX_HOUR)
        if (fleet.destination is None and fleet.eta != 0) or (fleet.destination is not None and (fleet.eta <= state.hour or fleet.destination == fleet.planet)):
            raise GameError("Invalid fleet travel state.")
        if not set(fleet.cargo) <= set(ORES) | set(RULES["products"]):
            raise GameError("Unknown cargo.")
        for count in fleet.cargo.values():
            integer(count, "Cargo")
        if sum(fleet.cargo.values()) > RULES["cargo_capacity"]:
            raise GameError("Fleet capacity exceeded.")
    if len(state.messages) > 500 or any(not isinstance(x, str) or len(x) > 1000 for x in state.messages):
        raise GameError("Invalid message history.")
    if len(state.admin_log) > 1000:
        raise GameError("Invalid admin history.")
    for entry in state.admin_log:
        if not isinstance(entry, dict) or set(entry) != {"hour", "command"} or not isinstance(entry["command"], str) or len(entry["command"]) > 500:
            raise GameError("Invalid admin entry.")
        integer(entry["hour"], "Admin hour", maximum=state.hour)


def from_dict(raw):
    try:
        if not isinstance(raw, dict):
            raise GameError("Save root must be an object.")
        expected = set(State.__dataclass_fields__)
        if set(raw) != expected:
            raise GameError("Save fields do not match schema 1.")
        for key in ("researched", "production", "fleets", "messages", "admin_log"):
            if type(raw[key]) is not list:
                raise GameError(f"{key} must be an array.")
        if type(raw["planets"]) is not dict:
            raise GameError("Planets must be an object.")
        for p in raw["planets"].values():
            if type(p) is not dict or set(p) != set(Planet.__dataclass_fields__) or type(p["buildings"]) is not list:
                raise GameError("Invalid planet fields.")
            for b in p["buildings"]:
                if type(b) is not dict or set(b) != set(Building.__dataclass_fields__):
                    raise GameError("Invalid building fields.")
        for key, cls in (("production", Job), ("fleets", Fleet)):
            if any(type(item) is not dict or set(item) != set(cls.__dataclass_fields__) for item in raw[key]):
                raise GameError(f"Invalid {key} fields.")
        data = dict(raw)
        data["planets"] = {key: Planet(**(p | {"buildings": [Building(**b) for b in p["buildings"]]}))
                           for key, p in raw["planets"].items()}
        data["production"] = [Job(**j) for j in raw["production"]]
        data["fleets"] = [Fleet(**f) for f in raw["fleets"]]
        state = State(**data)
        validate(state)
        return state
    except (TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise GameError(f"Malformed save: {exc}") from exc
