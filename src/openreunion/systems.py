"""Deterministic prototype systems. Numeric rules are intentionally replaceable."""
from .core import Building, Fleet, GameError, Job, MAX_HOUR, MAX_VALUE, ORES, RULES, integer


def message(state, text):
    state.messages.append(f"Hour {state.hour}: {text}")
    state.messages[:] = state.messages[-500:]


def planet(state, key):
    if key not in state.planets:
        raise GameError(f"Unknown world: {key}.")
    return state.planets[key]


def product(key):
    if key not in RULES["products"]:
        raise GameError(f"Unknown product: {key}.")
    return RULES["products"][key]


def credit(state, amount):
    integer(state.credits + amount, "Resulting credits")
    state.credits += amount


def stock(store, key, amount):
    integer(store.get(key, 0) + amount, f"Resulting {key}")
    store[key] = store.get(key, 0) + amount


def spend(state, p, credits, ores=None):
    if state.credits < credits:
        raise GameError(f"Need {credits:,} credits; available {state.credits:,}.")
    for key, amount in (ores or {}).items():
        if p.ores[key] < amount:
            raise GameError(f"Need {amount:,} {key}; available {p.ores[key]:,}.")
    state.credits -= credits
    for key, amount in (ores or {}).items():
        p.ores[key] -= amount


def build(state, world, kind, x, y):
    p = planet(state, world)
    if not p.colony:
        raise GameError("Establish a colony first.")
    if kind not in RULES["buildings"] or kind == "command_centre":
        raise GameError("Choose a buildable structure; command centres use colonize.")
    integer(x, "X", maximum=11)
    integer(y, "Y", maximum=11)
    if any(b.x == x and b.y == y for b in p.buildings):
        raise GameError("That tile is occupied.")
    spec = RULES["buildings"][kind]
    spend(state, p, spec["credits"])
    p.buildings.append(Building(kind, x, y, spec["work"]))
    message(state, f"Construction ordered: {spec['name']} on {p.name}.")


def demolish(state, world, x, y):
    p = planet(state, world)
    integer(x, "X", maximum=11)
    integer(y, "Y", maximum=11)
    b = next((b for b in p.buildings if (b.x, b.y) == (x, y)), None)
    if b is None or b.kind == "command_centre":
        raise GameError("Select a removable building.")
    if b.active:
        stock(p.inventory, "miner_droid", 1)
    p.buildings.remove(b)
    message(state, "Building demolished; assigned droid returned, no credit refund.")


def assign_droid(state, world):
    p = planet(state, world)
    if sum(b.active for b in p.buildings) >= 9:
        raise GameError("Maximum nine active mines per world.")
    b = next((b for b in p.buildings if b.kind == "mine" and not b.work_left and not b.active), None)
    if b is None:
        raise GameError("No completed inactive mine.")
    if p.inventory["miner_droid"] < 1:
        raise GameError("Produce or deliver a miner droid first.")
    p.inventory["miner_droid"] -= 1
    b.active = True
    message(state, f"Miner droid assigned on {p.name}.")


def research(state, item):
    spec = product(item)
    if state.research:
        raise GameError("Research already in progress.")
    if item in state.researched:
        raise GameError("Already researched.")
    if not set(spec["requires"]) <= set(state.researched):
        raise GameError("Research prerequisites: " + ", ".join(spec["requires"]))
    state.research, state.research_left = item, spec["research_work"]
    message(state, f"Research started: {spec['name']}.")


def produce(state, item, quantity=1):
    spec = product(item)
    integer(quantity, "Quantity", 1, 1000)
    if item not in state.researched:
        raise GameError("Research this product first.")
    if len(state.production) >= 1000:
        raise GameError("Production queue is full.")
    spend(state, state.planets["new_earth"], spec["credits"] * quantity,
          {k: v * quantity for k, v in spec["ores"].items()})
    state.production.append(Job(item, quantity, spec["work"]))
    message(state, f"Ordered {quantity} {spec['name']}.")


def cancel(state, index):
    integer(index, "Order index", maximum=len(state.production)-1)
    job = state.production.pop(index)
    spec = product(job.item)
    # Prototype refund policy: all undelivered units, including partially worked unit.
    credit(state, spec["credits"] * job.remaining)
    p = state.planets["new_earth"]
    for key, amount in spec["ores"].items():
        stock(p.ores, key, amount * job.remaining)
    message(state, f"Cancelled order; refunded {job.remaining} undelivered units.")


def survey(state, world):
    p = planet(state, world)
    if p.surveyed:
        raise GameError("This world already has satellite coverage.")
    stock(state.planets["new_earth"].inventory, "satellite", -1)
    p.surveyed = True
    message(state, f"Satellite deployed to {p.name}. Survey available.")


def create_fleet(state, name):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
        raise GameError("Fleet name must contain 1-40 characters.")
    name = name.strip()
    if any(f.name == name for f in state.fleets):
        raise GameError("Fleet name is already in use.")
    if len(state.fleets) >= 100:
        raise GameError("Fleet limit reached.")
    stock(state.planets["new_earth"].inventory, "trade_ship", -1)
    state.fleets.append(Fleet(name))
    message(state, f"Trade fleet created: {name}.")


def get_fleet(state, index):
    integer(index, "Fleet index", maximum=len(state.fleets)-1)
    f = state.fleets[index]
    if f.destination is not None:
        raise GameError("Fleet is in transit.")
    return f


def travel(state, index, destination):
    f = get_fleet(state, index)
    p = planet(state, destination)
    if f.planet == destination:
        raise GameError("Already at destination.")
    if not p.surveyed:
        raise GameError("Survey the destination first.")
    f.destination = destination
    f.eta = state.hour + RULES["travel_hours"]
    integer(f.eta, "Arrival time", maximum=MAX_HOUR)
    message(state, f"{f.name} departing for {p.name}; arrival hour {f.eta}.")


def transfer(state, index, item, quantity, load=True):
    f = get_fleet(state, index)
    integer(quantity, "Quantity", 1, 1000)
    if type(load) is not bool:
        raise GameError("Load must be true or false.")
    p = state.planets[f.planet]
    if not (p.colony or p.station):
        raise GameError("Cargo transfer needs a colony or miner station.")
    if item not in ORES and item not in RULES["products"]:
        raise GameError("Unknown cargo type.")
    store = p.ores if item in ORES else p.inventory
    if load:
        if sum(f.cargo.values()) + quantity > RULES["cargo_capacity"]:
            raise GameError("Cargo capacity exceeded.")
        stock(store, item, -quantity)
        stock(f.cargo, item, quantity)
    else:
        stock(f.cargo, item, -quantity)
        stock(store, item, quantity)
    message(state, f"{'Loaded' if load else 'Unloaded'} {quantity} {item} at {p.name}.")


def deploy_station(state, index):
    f = get_fleet(state, index)
    p = state.planets[f.planet]
    if not p.surveyed or p.station or p.colony:
        raise GameError("Choose a surveyed world without a colony or miner station.")
    stock(f.cargo, "miner_station", -1)
    p.station = True
    message(state, f"Miner station deployed on {p.name}.")


def colonize(state, world):
    p = planet(state, world)
    if not p.surveyed or not p.habitable or p.colony:
        raise GameError("Choose a surveyed, habitable world without a colony.")
    spec = RULES["buildings"]["command_centre"]
    spend(state, p, spec["credits"])
    p.colony = True
    p.buildings.append(Building("command_centre", 5, 5, spec["work"]))
    message(state, f"Colony construction started on {p.name}.")


def set_tax(state, world, rate):
    p = planet(state, world)
    if not p.colony:
        raise GameError("No colony on this world.")
    p.tax = integer(rate, "Tax", maximum=30)


def power(p):
    values = [RULES["buildings"][b.kind]["power"] for b in p.buildings if not b.work_left]
    supply = sum(v for v in values if v > 0)
    demand = -sum(v for v in values if v < 0)
    return supply, demand, 100 if not demand else min(100, supply * 100 // demand)


def advance(state, hours=1):
    integer(hours, "Hours", 1, 10000)
    integer(state.hour + hours, "Resulting hour", maximum=MAX_HOUR)
    for _ in range(hours):
        state.hour += 1
        for p in state.planets.values():
            budget = RULES["builders"]
            for b in p.buildings:
                if not b.work_left:
                    continue
                work = min(budget, b.work_left)
                b.work_left -= work
                budget -= work
                if not b.work_left:
                    message(state, f"{RULES['buildings'][b.kind]['name']} completed on {p.name}.")
                    if b.kind == "command_centre":
                        p.population = 100
                if not budget:
                    break
            efficiency = power(p)[2]
            mines = sum(b.active for b in p.buildings)
            derricks = sum(b.kind == "derrick" and not b.work_left for b in p.buildings)
            for ore in ORES:
                count = derricks if ore == "detoxin" else mines
                amount = count * RULES["mining_per_hour"] * efficiency // 100
                amount += RULES["station_per_hour"] if p.station else 0
                # Passive production saturates storage; never wraps or stops the clock.
                p.ores[ore] = min(MAX_VALUE, p.ores[ore] + amount)
            if state.hour % 24 == 0 and p.colony:
                state.credits = min(MAX_VALUE, state.credits + p.population * p.tax // 100)
        if state.research:
            state.research_left = max(0, state.research_left - RULES["research_work_per_hour"])
            if state.research_left == 0:
                state.researched.append(state.research)
                message(state, f"Research completed: {product(state.research)['name']}.")
                state.research = None
        budget = RULES["builders"]
        while budget and state.production:
            job = state.production[0]
            store = state.planets["new_earth"].inventory
            if store[job.item] == MAX_VALUE:
                break
            work = min(budget, job.work_left)
            budget -= work
            job.work_left -= work
            if not job.work_left:
                stock(store, job.item, 1)
                job.remaining -= 1
                message(state, f"Produced: {product(job.item)['name']}.")
                if job.remaining:
                    job.work_left = product(job.item)["work"]
                else:
                    state.production.pop(0)
        for fleet in state.fleets:
            if fleet.destination is not None and fleet.eta <= state.hour:
                fleet.planet, fleet.destination, fleet.eta = fleet.destination, None, 0
                message(state, f"{fleet.name} arrived at {state.planets[fleet.planet].name}.")


ACTIONS = {fn.__name__: fn for fn in (build, demolish, assign_droid, research, produce,
           cancel, survey, create_fleet, travel, transfer, deploy_station, colonize, set_tax, advance)}
