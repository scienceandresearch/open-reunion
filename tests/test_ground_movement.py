"""Ground movement progression, reservations and malformed-state regressions."""
from copy import deepcopy
import unittest
from test_ground_attacks import battle, target
from test_ground_geometry import unit, MOTION
from openreunion.dos.ground_movement import ground_movement_pass


RULES = {"waits": [7, 6, 4, 10]}


def state(friendly, hostile=None):
    result = battle(friendly, hostile);result["board"] = [[0]*9 for _ in range(16)]
    result["pending_direction"] = 0
    for side, key in enumerate(("friendly", "hostile")):
        for index, row in enumerate(result[key+"_groups"], 1):
            result["board"][row[4]][row[5]] = 100*side+index
            if row[9]:
                cx, cy = row[4]+MOTION["x"][row[8]], row[5]+MOTION["y"][row[8]]
                if 0 <= cx < 16 and 0 <= cy < 9:result["board"][cx][cy] = 100*side+index
    return result


class GroundMovementTests(unittest.TestCase):
    def test_wait_decrements_without_changing_position_or_reservations(self):
        row = unit(x=2);row[9:12] = [1, 8, 2];source = state([row]);before = deepcopy(source)
        result = ground_movement_pass(source, MOTION, RULES)
        self.assertEqual(result["friendly_groups"][0][9:12], [1, 8, 1])
        self.assertEqual(result["board"], source["board"]);self.assertEqual(source, before)

    def test_completed_pixel_step_releases_old_cell_and_reserves_next(self):
        row = unit(x=2);row[9:12] = [1, 15, 0];row[15:18] = [2, 5, 4]
        result = ground_movement_pass(state([row]), MOTION, RULES)
        self.assertEqual(result["friendly_groups"][0][4:6], [3, 4])
        self.assertEqual(result["friendly_groups"][0][8:12], [3, 1, 0, 7])
        self.assertEqual([result["board"][x][4] for x in (2, 3, 4)], [0, 1, 1])

    def test_queue_consumes_completed_direction_and_turns_to_next(self):
        row = unit(x=2);row[9:12] = [1, 15, 0];row[15] = 1;row[18:22] = [3, 3, 4, 1]
        result = ground_movement_pass(state([row]), MOTION, RULES);troop = result["friendly_groups"][0]
        self.assertEqual(troop[18:22], [2, 4, 1, 1]);self.assertEqual(troop[8:12], [4, 1, 0, 7])
        self.assertEqual(result["board"][3][5], 1);self.assertEqual(result["pending_direction"], 4)

    def test_idle_queued_unit_waits_when_next_cell_belongs_to_another_group(self):
        row = unit(x=2);row[9:12] = [1, 8, 0];row[15] = 1
        source = state([row]);source["board"][3][4] = 2
        self.assertEqual(ground_movement_pass(source, MOTION, RULES), source)

    def test_pursuit_stops_when_aircraft_is_already_in_attack_range(self):
        row = unit(kind=3, x=5);row[15:17] = [3, 1]
        enemy = target(x=7);enemy[11] = 1
        result = ground_movement_pass(state([row], [enemy]), MOTION, RULES)
        self.assertEqual(result["friendly_groups"][0][9], 0)
        self.assertEqual(result["board"][6][4], 0)

    def test_friendly_movement_reserves_contested_cell_before_hostile(self):
        first = unit(x=2);second = unit(x=4)
        for row in (first, second):row[15:18] = [2, 3, 4]
        result = ground_movement_pass(state([first], [second]), MOTION, RULES)
        self.assertEqual(result["board"][3][4], 1)
        self.assertEqual(result["friendly_groups"][0][9], 1)
        self.assertEqual(result["hostile_groups"][0][9], 0)

    def test_class_wait_controls_sixteen_pixel_cell_travel(self):
        for kind, wait in enumerate(RULES["waits"], 1):
            row = unit(kind=kind, x=2);row[9:12] = [1, 0, wait];row[15:18] = [2, 5, 4]
            current = state([row])
            for _ in range(16*(wait+1)-1):current = ground_movement_pass(current, MOTION, RULES)
            self.assertEqual(current["friendly_groups"][0][4], 2)
            current = ground_movement_pass(current, MOTION, RULES)
            self.assertEqual(current["friendly_groups"][0][4], 3)

    def test_missing_opponent_stops_pursuit_without_reading_a_phantom_group(self):
        row = unit(x=8);row[15:17] = [3, 0]
        result = ground_movement_pass(state([], [row]), MOTION, RULES)
        self.assertEqual(result["hostile_groups"][0][15], 1)
        self.assertEqual(result["hostile_groups"][0][9], 0)
        self.assertEqual(result["hostile_groups"][0][4:6], [8, 4])

    def test_malformed_edge_movement_cannot_wrap_or_write_outside_board(self):
        row = unit(x=15);row[9:12] = [1, 15, 0];row[15] = 1
        result = ground_movement_pass(state([row]), MOTION, RULES)
        self.assertEqual(result["friendly_groups"][0][4:6], [15, 4])
        self.assertEqual(result["friendly_groups"][0][9:11], [0, 0])
        self.assertEqual(result["board"][15][4], 1)


if __name__ == "__main__":unittest.main()
