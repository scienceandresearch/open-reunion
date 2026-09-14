"""Ground pointer selection, two-stage orders and input corruption guards."""
from copy import deepcopy
import unittest
from test_ground_geometry import unit, MOTION
from test_ground_frame import state as frame_state
from openreunion.core import GameError
from openreunion.dos.ground_controls import nearest_ground_selection, ground_input

RULES = {"base_offsets": [[8, 0], [0, 8]]}


def fixture():
    battle = frame_state([unit(quantity=10)], [unit(quantity=20, x=8)])
    battle.update(control_mode=1, retreated=False)
    return battle


def send(battle, action, **args):return ground_input(battle, MOTION, RULES, action, **args)


class GroundControlTests(unittest.TestCase):
    def test_selection_ties_favor_first_troop_and_threshold_is_inclusive(self):
        battle = fixture();battle["hostile_groups"] = deepcopy(battle["friendly_groups"])
        battle["friendly_special"][1] = battle["hostile_special"][1] = 0
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 146, 118), 1)
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 146, 118, "hostile"), 1)
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 166, 128), 1)
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 167, 128), 0)

    def test_selection_tracks_moving_pixels_and_skips_dead_records(self):
        battle = fixture();battle["friendly_groups"][0][10] = 7
        battle["hostile_groups"][0][1] = 0;battle["hostile_groups"][0][8] = 255
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 153, 118), 1)
        battle["friendly_groups"][0][1] = 0
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 153, 118), 0)

    def test_base_centers_depend_on_attacking_side_and_use_slot_21(self):
        battle = fixture();battle["friendly_groups"] = [];battle["hostile_groups"] = []
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 64, 116), 21)
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 296, 124), 121)
        battle["player_attacking"] = False;battle["hostile_special"][4] = 15
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 72, 124), 21)
        self.assertEqual(nearest_ground_selection(battle, MOTION, RULES, 304, 116, "hostile"), 21)

    def test_click_selects_hostile_with_hotspot_offset_and_repeated_selection_is_quiet(self):
        battle = fixture();before = deepcopy(battle)
        result, events = send(battle, "click", x=200, y=124)
        self.assertEqual((result["selected_group"], result["selected_friendly"]), (1, False))
        self.assertEqual(events, [("ground_cursor", 0), ("ground_notice", 20)])
        again, events = send(result, "click", x=200, y=124)
        self.assertEqual(again, result);self.assertEqual(events, [("ground_cursor", 0)])
        self.assertEqual(battle, before)

    def test_move_mode_commits_destination_and_clears_queue_without_teleporting(self):
        battle = fixture();battle["selected_group"] = 1;battle["friendly_groups"][0][18] = 4
        result, events = send(battle, "move")
        self.assertEqual(result["control_mode"], 3);self.assertEqual(events, [("ground_cursor", 5), ("ground_notice", 30)])
        result, events = send(result, "click", x=125, y=77)
        self.assertEqual(result["friendly_groups"][0][15:19], [2, 4, 1, 0])
        self.assertEqual(result["friendly_groups"][0][4:6], [5, 4])
        self.assertEqual(result["control_mode"], 1);self.assertEqual(events[-1], ("ground_notice", 21))

    def test_move_clamps_every_edge_and_rejects_stale_dead_or_hostile_selection(self):
        for x, y, cell in ((319, 100, [15, 3]), (0, 0, [0, 0]), (100, 250, [2, 8])):
            battle = fixture();battle.update(control_mode=3, selected_group=1)
            result, _ = send(battle, "click", x=x, y=y)
            self.assertEqual(result["friendly_groups"][0][16:18], cell)
        for index, friendly, alive in ((0, True, True), (2, True, True), (1, False, True), (1, True, False)):
            battle = fixture();battle.update(control_mode=3, selected_group=index, selected_friendly=friendly)
            if not alive:battle["friendly_groups"][0][1] = 0
            result, events = send(battle, "click", x=100, y=100)
            self.assertEqual(result["friendly_groups"], battle["friendly_groups"])
            self.assertEqual(events[-1], ("ground_notice", 22))

    def test_attack_targets_enemy_troop_or_base_and_miss_preserves_previous_order(self):
        battle = fixture();battle["selected_group"] = 1
        result, _ = send(battle, "attack");result, _ = send(result, "click", x=194, y=118)
        self.assertEqual(result["friendly_groups"][0][15:17], [3, 1])
        result, _ = send(result, "attack");result, _ = send(result, "click", x=296, y=124)
        self.assertEqual(result["friendly_groups"][0][15:17], [3, 21])
        result, _ = send(result, "attack");before = deepcopy(result["friendly_groups"])
        result, events = send(result, "click", x=0, y=0)
        self.assertEqual(result["friendly_groups"], before);self.assertEqual(events[-1], ("ground_notice", 22))

    def test_base_cannot_move_and_requires_attacking_context_and_available_structure_for_attack(self):
        for attacking in (False, True):
            for available in (False, True):
                battle = fixture();battle.update(player_attacking=attacking, selected_group=21)
                _, events = send(battle, "move");self.assertEqual(events, [("ground_notice", 22)])
                result, events = send(battle, "attack", base_attack_available=available)
                self.assertEqual(result["control_mode"], 4 if attacking and available else 1)
                if attacking and available:
                    result, _ = send(result, "click", x=194, y=118, base_attack_available=True)
                    self.assertEqual(result["friendly_special"][15:17], [3, 1])

    def test_cancel_and_paused_click_preserve_existing_unit_orders(self):
        battle = fixture();battle["friendly_groups"][0][15:19] = [2, 8, 4, 0]
        battle["control_mode"] = 2
        result, events = send(battle, "click", x=100, y=100)
        self.assertEqual(result, battle);self.assertEqual(events, [])
        result, events = send(battle, "context_cancel")
        self.assertEqual(result["control_mode"], 1);self.assertEqual(result["friendly_groups"], battle["friendly_groups"])
        self.assertEqual(events, [("ground_notice", 22), ("ground_cursor", 0)])
        _, events = send(result, "context_cancel");self.assertEqual(events, [("ground_cursor", 0)])

    def test_retreat_requests_result_once_and_does_not_invent_casualties(self):
        battle = fixture();battle["player_won"] = True
        result, events = send(battle, "retreat")
        self.assertTrue(result["done"]);self.assertTrue(result["retreated"])
        self.assertTrue(result["player_won"])  # Result entry subsequently suppresses it.
        self.assertEqual(result["friendly_groups"], battle["friendly_groups"])
        self.assertEqual(events, [("control_layout", 30), ("ground_result_requested", 0)])
        with self.assertRaises(GameError):send(result, "retreat")

    def test_invalid_command_coordinates_and_mode_leave_input_unchanged(self):
        battle = fixture();before = deepcopy(battle)
        for action, args in (("bad", {}), ("click", {"x": True, "y": 100}), ("attack", {"base_attack_available": 1})):
            with self.assertRaises(GameError):send(battle, action, **args)
        self.assertEqual(battle, before)
        battle["control_mode"] = 99
        with self.assertRaises(GameError):send(battle, "cancel")


if __name__ == "__main__":unittest.main()
