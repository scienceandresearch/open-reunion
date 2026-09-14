"""Ground metrics, eligibility, formation and explicit special records."""
from copy import deepcopy
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.core import GameError
from openreunion.dos.ground_geometry import pixel_position, ground_distances, can_attack, nearest_ground_target
from openreunion.dos.ground_battle import initialize_ground_battle
from test_ground_setup import fixture, build, RULES
from openreunion.dos.ground_setup import edit_ground_groups


MOTION = {"x": [0, -1, 0, 1, 0], "y": [0, 0, -1, 0, 1]}


def unit(kind=1, quantity=1, x=5, y=4):
    row = [0]*39;row[0:3] = [kind, *struct.pack("<h", quantity)];row[4:6] = [x, y];row[8] = 3
    return row


class GroundGeometryTests(unittest.TestCase):
    def test_pixel_positions_include_direction_and_subcell_step(self):
        row = unit();row[10] = 7
        for direction, expected in ((1, (137, 67)), (2, (144, 60)), (3, (151, 67)), (4, (144, 74))):
            row[8] = direction;self.assertEqual(pixel_position(row, MOTION), expected)

    def test_three_metrics_preserve_different_rounding_and_diagonal_behavior(self):
        first = unit();second = unit(x=6, y=5)
        self.assertEqual(ground_distances(first, second, MOTION), (2, 1, 2))
        second[10] = 4
        self.assertEqual(ground_distances(first, second, MOTION), (2, 2, 3))

    def test_class_ranges_include_rocket_annulus_and_close_attack(self):
        origin = unit();diagonal = unit(x=7, y=6)
        expected = {1: False, 2: False, 3: True, 4: True}
        for kind in range(1, 5):
            origin[0] = kind;self.assertEqual(can_attack(origin, diagonal, MOTION), expected[kind])
        origin[0] = 4
        self.assertTrue(can_attack(origin, unit(x=9), MOTION))
        self.assertFalse(can_attack(origin, unit(x=10), MOTION))
        target = unit(x=6);target[10] = 4
        self.assertFalse(can_attack(origin, target, MOTION))

    def test_nearby_tank_range_cannot_underflow(self):
        origin = unit(kind=2)
        for step in range(5):
            target = unit();target[10] = step
            self.assertEqual(ground_distances(origin, target, MOTION)[0], 0)
            self.assertTrue(can_attack(origin, target, MOTION))

    def test_nearest_target_skips_dead_groups_and_breaks_ties_by_first_slot(self):
        own = [unit()];targets = [unit(quantity=0), unit(x=4), unit(x=6)]
        self.assertEqual(nearest_ground_target(own, targets, 1, MOTION), 2)
        targets[1][1:3] = [0, 0]
        self.assertEqual(nearest_ground_target(own, targets, 1, MOTION), 3)
        self.assertEqual(nearest_ground_target(own, [], 1, MOTION), 0)
        with self.assertRaises(GameError):nearest_ground_target(own, targets, 0, MOTION)

    def test_formations_stay_on_board_at_all_group_counts(self):
        for count in range(1, 21):
            setup = {"friendly_groups": [unit() for _ in range(count)], "hostile_groups": [unit() for _ in range(count)]}
            for row in setup["hostile_groups"]:row[10] = 1
            result = initialize_ground_battle(setup, MOTION, player_attacking=True)
            for side in ("friendly", "hostile"):
                positions = [tuple(row[4:6]) for row in result[side+"_groups"]]
                self.assertEqual(len(set(positions)), count)
                self.assertTrue(all(0 <= x < 16 and 0 <= y < 9 for x, y in positions))
            self.assertTrue(all(1 <= row[16] <= count for row in result["hostile_groups"]))

    def test_zero_player_groups_compact_before_placement_and_targeting(self):
        a, b = unit(quantity=0), unit(kind=3);b[25] = 77
        setup = {"friendly_groups": [a, a, b, a], "hostile_groups": [unit()]}
        result = initialize_ground_battle(setup, MOTION, player_attacking=False)
        self.assertEqual(len(result["friendly_groups"]), 1);self.assertEqual(result["friendly_groups"][0][25], 77)
        self.assertEqual(result["friendly_groups"][0][4:6], [2, 4]);self.assertEqual(result["hostile_groups"][0][16], 1)

    def test_special_records_are_separate_from_troop_counts_and_have_correct_edges(self):
        setup = {"friendly_groups": [], "hostile_groups": [unit()]}
        for attacking, x in ((False, 15), (True, 14)):
            result = initialize_ground_battle(setup, MOTION, player_attacking=attacking)
            self.assertEqual(result["hostile_special"][:6], [5, 1, 0, 100, x, 4])
            self.assertEqual(result["friendly_special"][:6], [5, 1, 0, 100, 0, 4])
            self.assertEqual(result["hostile_groups"][0][16], 0)
            self.assertEqual(len(result["friendly_groups"]), 0)

    def test_initialization_copies_setup_and_resets_combat_fields(self):
        setup = {"friendly_groups": [unit()], "hostile_groups": [unit()]};row = setup["friendly_groups"][0]
        row[6:15] = [99]*9;row[15] = 3;row[18] = 9;before = deepcopy(setup)
        result = initialize_ground_battle(setup, MOTION, player_attacking=True)
        self.assertEqual(setup, before);self.assertEqual(result["friendly_groups"][0][6:15], [0, 0, 3, 0, 0, 1, 0, 0, 0])
        self.assertEqual(result["board"], [[0]*9 for _ in range(16)])
        self.assertFalse(result["done"]);self.assertFalse(result["instant_kill"])

    def test_prepared_ground_selection_reaches_placement_with_reserves_intact(self):
        setup = build(fixture());setup = edit_ground_groups(setup, RULES, "decrease", 2)
        self.assertEqual(setup["friendly_reserve"], [1, 0, 0, 0])
        result = initialize_ground_battle(setup, MOTION, player_attacking=True)
        self.assertEqual(len(result["friendly_groups"]), 1);self.assertEqual(result["friendly_groups"][0][1:3], [30, 0])
        for key in ("friendly_totals", "friendly_primary", "friendly_secondary", "friendly_reserve"):
            self.assertEqual(result[key], setup[key])


if __name__ == "__main__":unittest.main()
