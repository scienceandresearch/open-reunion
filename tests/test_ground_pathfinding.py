"""Obstacle routing, occupied goals and deterministic movement decisions."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from openreunion.core import GameError
from openreunion.dos.ground_pathfinding import ground_path_direction


class GroundPathfindingTests(unittest.TestCase):
    def test_straight_routes_and_arrival(self):
        board = [[0]*9 for _ in range(16)]
        for goal, direction in (((0, 4), 1), ((5, 0), 2), ((15, 4), 3), ((5, 8), 4), ((5, 4), 0)):
            self.assertEqual(ground_path_direction(board, (5, 4), goal), direction)

    def test_equal_length_routes_keep_original_first_step(self):
        board = [[0]*9 for _ in range(16)]
        self.assertEqual(ground_path_direction(board, (2, 4), (4, 6)), 3)
        self.assertEqual(ground_path_direction(board, (0, 0), (15, 8)), 3)

    def test_route_through_edge_gap_reaches_goal_without_crossing_occupants(self):
        board = [[0]*9 for _ in range(16)];board[5] = [101]*8+[0]
        before = deepcopy(board);position = (2, 4);visited = {position}
        vectors = {1: (-1, 0), 2: (0, -1), 3: (1, 0), 4: (0, 1)}
        for _ in range(19):
            direction = ground_path_direction(board, position, (13, 4))
            self.assertIn(direction, vectors)
            dx, dy = vectors[direction];position = (position[0]+dx, position[1]+dy)
            self.assertEqual(board[position[0]][position[1]], 0)
            self.assertNotIn(position, visited);visited.add(position)
        self.assertEqual(position, (13, 4));self.assertIn((5, 8), visited)
        self.assertEqual(ground_path_direction(board, position, (13, 4)), 0)
        self.assertEqual(board, before)

    def test_unreachable_destination_approaches_wall_then_stops(self):
        board = [[0]*9 for _ in range(16)];board[5] = [1]*9
        self.assertEqual(ground_path_direction(board, (2, 4), (13, 4)), 3)
        self.assertEqual(ground_path_direction(board, (4, 4), (13, 4)), 0)

    def test_occupied_target_is_approached_without_entering_its_cell(self):
        board = [[0]*9 for _ in range(16)];board[5][4] = 101
        self.assertEqual(ground_path_direction(board, (2, 4), (5, 4)), 3)
        self.assertEqual(ground_path_direction(board, (4, 4), (5, 4)), 0)

    def test_enclosed_start_stays_and_own_occupied_cell_can_be_left(self):
        board = [[1]*9 for _ in range(16)]
        self.assertEqual(ground_path_direction(board, (0, 0), (15, 8)), 0)
        board = [[0]*9 for _ in range(16)];board[2][4] = 7
        self.assertEqual(ground_path_direction(board, (2, 4), (13, 4)), 3)

    def test_invalid_dimensions_and_endpoints_are_rejected(self):
        board = [[0]*9 for _ in range(16)]
        for start, goal in (((-1, 4), (5, 4)), ((2, 4), (16, 4)), ((2, 9), (5, 4))):
            with self.assertRaises(GameError):ground_path_direction(board, start, goal)
        for invalid in ([], [[0]*9 for _ in range(15)], [[0]*8 for _ in range(16)]):
            with self.assertRaises(GameError):ground_path_direction(invalid, (2, 4), (5, 4))


if __name__ == "__main__":unittest.main()
