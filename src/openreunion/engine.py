"""Application boundary: validated transactions shared by UI, console and tests."""
from copy import deepcopy
import shlex

from .core import GameError, ORES, RULES, integer, new_game, validate
from . import systems

ADMIN_HELP = """help                          Show commands
status                        Show resources on every world
give credits 100000            Add credits
set credits 500000             Set credits
give energon 1000 [world]      Add ore (default: new_earth)
set detoxin 1000 [world]       Set ore
item miner_droid 10 [world]    Add finished items
finish                        Complete queued work and research
Worlds: new_earth, apollo, klatoo, zeus
Ores: detoxin, energon, raenium, kremir, toxon, lepitium
Items: miner_droid, satellite, miner_station, trade_ship"""


class Engine:
    def __init__(self, state=None, admin_enabled=False):
        self.state = deepcopy(state) if state is not None else new_game()
        validate(self.state)
        self.admin_enabled = admin_enabled

    def apply(self, action, **args):
        if action not in systems.ACTIONS:
            raise GameError(f"Unknown action: {action}.")
        candidate = deepcopy(self.state)
        try:
            systems.ACTIONS[action](candidate, **args)
        except TypeError as exc:
            raise GameError(f"Invalid arguments for {action}: {exc}") from exc
        validate(candidate)
        self.state = candidate

    def console(self, command):
        if not isinstance(command, str) or len(command) > 500:
            raise GameError("Command must contain at most 500 characters.")
        try:
            words = shlex.split(command)
        except ValueError as exc:
            raise GameError(str(exc)) from exc
        if words == ["help"]:
            return ADMIN_HELP
        if words == ["status"]:
            s = self.state
            return f"Hour {s.hour}; Credits {s.credits:,}\n" + "\n".join(
                f"{key}: " + ", ".join(f"{k}={v:,}" for k, v in p.ores.items())
                for key, p in s.planets.items())
        if not self.admin_enabled:
            raise GameError("Enable the admin console to change resources.")
        s = deepcopy(self.state)
        if words == ["finish"]:
            if s.research:
                s.researched.append(s.research)
                s.research, s.research_left = None, 0
            for job in s.production:
                systems.stock(s.planets["new_earth"].inventory, job.item, job.remaining)
            s.production.clear()
            for p in s.planets.values():
                for b in p.buildings:
                    if b.work_left and b.kind == "command_centre":
                        p.population = 100
                    b.work_left = 0
        elif len(words) in (3, 4) and words[0] in ("give", "set", "item"):
            op, key, raw = words[:3]
            try:
                amount = int(raw)
            except ValueError as exc:
                raise GameError("Amount must be an integer.") from exc
            integer(amount, "Amount")
            world = words[3] if len(words) == 4 else "new_earth"
            p = systems.planet(s, world)
            if key == "credits" and op != "item" and len(words) == 3:
                s.credits = amount if op == "set" else s.credits + amount
            elif key in ORES and op != "item":
                p.ores[key] = amount if op == "set" else p.ores[key] + amount
            elif key in RULES["products"] and op == "item":
                systems.stock(p.inventory, key, amount)
            else:
                raise GameError("Unknown resource or command. Type help.")
        else:
            raise GameError("Unknown command or wrong arguments. Type help.")
        s.assisted = True
        s.admin_log.append({"hour": s.hour, "command": command})
        s.admin_log[:] = s.admin_log[-1000:]
        systems.message(s, "Admin: " + command)
        validate(s)
        self.state = s
        return "Applied: " + command
