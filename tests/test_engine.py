import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openreunion.core import Building, GameError, MAX_VALUE, RULES, from_dict
from openreunion.engine import Engine


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.e = Engine()

    def researched(self, item):
        self.e.apply("research", item=item)
        self.e.apply("advance", hours=100)

    def rejected(self, action, **kwargs):
        before = self.e.state.to_dict()
        with self.assertRaises(GameError):
            self.e.apply(action, **kwargs)
        self.assertEqual(before, self.e.state.to_dict())

    def test_research_production_mining_loop(self):
        self.e.apply("research", item="miner_droid")
        self.e.apply("advance", hours=3)
        self.e.apply("produce", item="miner_droid", quantity=2)
        self.e.apply("advance", hours=7)
        p = self.e.state.planets["new_earth"]
        self.assertEqual(p.inventory["miner_droid"], 1)
        self.assertEqual(self.e.state.production[0].remaining, 1)
        self.e.apply("assign_droid", world="new_earth")
        ore = self.e.state.planets["new_earth"].ores["energon"]
        self.e.apply("advance", hours=1)
        self.assertEqual(self.e.state.planets["new_earth"].ores["energon"], ore + 2)

    def test_insufficient_resources_roll_back(self):
        self.researched("miner_droid")
        self.rejected("produce", item="miner_droid", quantity=1000)

    def test_build_checks_occupancy_and_money(self):
        self.rejected("build", world="new_earth", kind="mine", x=1, y=1)
        self.rejected("build", world="new_earth", kind="mine", x=12, y=1)
        self.e.state.credits = 0
        self.rejected("build", world="new_earth", kind="mine", x=0, y=0)

    def test_build_work_is_shared_not_multiplied(self):
        for x in (0, 2):
            self.e.apply("build", world="new_earth", kind="mine", x=x, y=0)
        self.e.apply("advance", hours=6)
        buildings = self.e.state.planets["new_earth"].buildings[-2:]
        self.assertEqual([b.work_left for b in buildings], [0, 60])

    def test_nine_active_mine_limit(self):
        p = self.e.state.planets["new_earth"]
        p.buildings = [Building("mine", x, 0, active=x < 9) for x in range(10)]
        p.inventory["miner_droid"] = 2
        self.rejected("assign_droid", world="new_earth")

    def test_demolition_returns_assigned_droid(self):
        p = self.e.state.planets["new_earth"]
        p.inventory["miner_droid"] = 1
        self.e.apply("assign_droid", world="new_earth")
        self.e.apply("demolish", world="new_earth", x=1, y=3)
        self.assertEqual(self.e.state.planets["new_earth"].inventory["miner_droid"], 1)

    def test_no_power_no_mining(self):
        self.e.apply("demolish", world="new_earth", x=1, y=1)
        before = self.e.state.planets["new_earth"].ores.copy()
        self.e.apply("advance", hours=24)
        self.assertEqual(before, self.e.state.planets["new_earth"].ores)

    def test_one_satellite_per_world(self):
        self.e.state.planets["new_earth"].inventory["satellite"] = 2
        self.e.apply("survey", world="apollo")
        self.rejected("survey", world="apollo")
        self.assertEqual(self.e.state.planets["new_earth"].inventory["satellite"], 1)

    def test_research_prerequisites_and_double_orders(self):
        self.rejected("research", item="trade_ship")
        self.rejected("produce", item="miner_droid", quantity=1)
        self.e.apply("research", item="satellite")
        self.rejected("research", item="miner_droid")
        self.e.apply("advance", hours=4)
        self.rejected("research", item="satellite")

    def test_cancellation_refunds_only_undelivered_units(self):
        self.researched("miner_droid")
        credits = self.e.state.credits
        ores = self.e.state.planets["new_earth"].ores.copy()
        self.e.apply("produce", item="miner_droid", quantity=2)
        self.e.apply("advance", hours=8)
        self.e.apply("cancel", index=0)
        self.assertEqual(self.e.state.credits, credits - 200)
        self.assertEqual(self.e.state.planets["new_earth"].ores["energon"], ores["energon"] - 2)
        self.assertEqual(self.e.state.planets["new_earth"].inventory["miner_droid"], 1)
        self.assertEqual(self.e.state.production, [])

    def test_cargo_and_offworld_mining_end_to_end(self):
        for item in ("satellite", "trade_ship", "miner_station"):
            self.researched(item)
            self.e.apply("produce", item=item, quantity=1)
            self.e.apply("advance", hours=100)
        self.e.apply("survey", world="apollo")
        self.e.apply("create_fleet", name="Apollo transport")
        self.e.apply("transfer", index=0, item="miner_station", quantity=1)
        self.e.apply("travel", index=0, destination="apollo")
        self.rejected("transfer", index=0, item="energon", quantity=1)
        self.e.apply("advance", hours=6)
        self.e.apply("deploy_station", index=0)
        self.e.apply("advance", hours=10)
        self.assertEqual(self.e.state.planets["apollo"].ores["energon"], 10)
        self.e.apply("transfer", index=0, item="energon", quantity=10)
        self.e.apply("travel", index=0, destination="new_earth")
        self.e.apply("advance", hours=6)
        before = self.e.state.planets["new_earth"].ores["energon"]
        self.e.apply("transfer", index=0, item="energon", quantity=10, load=False)
        self.assertEqual(self.e.state.planets["new_earth"].ores["energon"], before + 10)

    def test_over_capacity_and_missing_cargo_rollback(self):
        self.e.state.planets["new_earth"].inventory["trade_ship"] = 1
        self.e.apply("create_fleet", name="Trade")
        self.e.state.planets["new_earth"].ores["energon"] = 2000
        self.e.apply("transfer", index=0, item="energon", quantity=1000)
        self.rejected("transfer", index=0, item="energon", quantity=1)
        self.rejected("transfer", index=0, item="kremir", quantity=1, load=False)

    def test_colony_requires_survey_habitability_and_completion(self):
        self.rejected("colonize", world="apollo")
        self.e.state.planets["klatoo"].surveyed = True
        self.rejected("colonize", world="klatoo")
        self.e.state.planets["apollo"].surveyed = True
        self.e.apply("colonize", world="apollo")
        self.assertEqual(self.e.state.planets["apollo"].population, 0)
        self.e.apply("advance", hours=100)
        self.assertEqual(self.e.state.planets["apollo"].population, 100)

    def test_tick_chunking_is_deterministic(self):
        other = Engine(self.e.state)
        self.e.apply("advance", hours=240)
        for _ in range(240):
            other.apply("advance", hours=1)
        self.assertEqual(self.e.state.to_dict(), other.state.to_dict())

    def test_save_reload_continuation_is_deterministic(self):
        self.e.apply("research", item="satellite")
        self.e.apply("advance", hours=1)
        other = Engine(from_dict(self.e.state.to_dict()))
        for engine in (self.e, other):
            engine.apply("advance", hours=100)
        self.assertEqual(self.e.state.to_dict(), other.state.to_dict())

    def test_bool_negative_fractional_and_huge_inputs(self):
        for value in (True, -1, 1.5, 10001, "1"):
            self.rejected("advance", hours=value)

    def test_storage_saturation_does_not_crash_clock(self):
        self.e.state.credits = MAX_VALUE
        self.e.state.planets["new_earth"].ores["detoxin"] = MAX_VALUE
        self.e.apply("advance", hours=24)
        self.assertEqual(self.e.state.credits, MAX_VALUE)
        self.assertEqual(self.e.state.planets["new_earth"].ores["detoxin"], MAX_VALUE)


class AdminTests(unittest.TestCase):
    def test_admin_is_explicit_and_readonly_commands_work(self):
        e = Engine()
        self.assertIn("give credits", e.console("help"))
        self.assertIn("Credits", e.console("status"))
        with self.assertRaises(GameError):
            e.console("give credits 100000")
        self.assertFalse(e.state.assisted)

    def test_all_resources_items_and_audit(self):
        e = Engine(admin_enabled=True)
        e.console("give credits 100000")
        e.console("give toxon 1000 apollo")
        e.console("set lepitium 123")
        e.console("item miner_droid 10")
        self.assertEqual(e.state.credits, 250000)
        self.assertEqual(e.state.planets["apollo"].ores["toxon"], 1000)
        self.assertEqual(e.state.planets["new_earth"].ores["lepitium"], 123)
        self.assertTrue(e.state.assisted)
        self.assertEqual(len(e.state.admin_log), 4)

    def test_invalid_and_injection_commands_leave_no_changes(self):
        e = Engine(admin_enabled=True)
        for command in ("give credits -1", "set credits 2147483648", "give credits 1e9", "give credits True",
                        "give credits 10; quit", "__import__('os')", "item unknown 10", 'give credits "', "finish extra"):
            before = e.state.to_dict()
            with self.subTest(command=command), self.assertRaises(GameError):
                e.console(command)
            self.assertEqual(before, e.state.to_dict())

    def test_finish_completes_work_without_advancing_time(self):
        e = Engine(admin_enabled=True)
        e.apply("research", item="miner_droid")
        e.console("finish")
        e.apply("produce", item="miner_droid", quantity=10)
        e.console("finish")
        self.assertEqual(e.state.hour, 0)
        self.assertEqual(e.state.planets["new_earth"].inventory["miner_droid"], 10)
        self.assertFalse(e.state.production)

    def test_finish_overflow_rolls_back_everything(self):
        e = Engine(admin_enabled=True)
        e.apply("research", item="miner_droid")
        e.console("finish")
        e.apply("produce", item="miner_droid", quantity=1)
        e.state.planets["new_earth"].inventory["miner_droid"] = MAX_VALUE
        before = copy.deepcopy(e.state.to_dict())
        with self.assertRaises(GameError):
            e.console("finish")
        self.assertEqual(before, e.state.to_dict())
