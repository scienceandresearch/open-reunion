"""Projectiles, bases, death animation ordering and complete ground frames."""
from copy import deepcopy
import json
import struct
import unittest
from test_ground_geometry import unit, MOTION
from test_ground_attacks import RULES as ATTACK_RULES, target
from test_ground_movement import RULES as MOVEMENT_RULES, state as movement_state
from openreunion.dos.ground_attacks import ground_attack_pass
from openreunion.dos.ground_movement import ground_movement_pass
from openreunion.dos.ground_battle import initialize_ground_battle
from openreunion.dos.ground_frame import ground_projectile_pass, ground_completion_pass, ground_animation_pass, ground_frame


RULES = dict(ATTACK_RULES, target_coefficients=ATTACK_RULES["target_coefficients"]+[30])


def state(friendly=None, hostile=None):
    battle = movement_state(friendly or [], hostile or [])
    battle.update(done=False, player_won=False, instant_kill=False, player_attacking=True,
                  selected_group=0, selected_friendly=True, friendly_projectiles=[], hostile_projectiles=[])
    for side, cx in (("friendly", 0), ("hostile", 14)):
        special = unit(kind=5, x=cx);special[3] = 100;battle[side+"_special"] = special
    return battle


def rocket(x=6, y=4, power=9, step=8, duration=8):
    return list(struct.pack("<7hI", 144, 67, 64+16*x, 3+16*y, step, duration, 12, power))


class GroundFrameTests(unittest.TestCase):
    def test_impact_damage_uses_current_occupant_and_divisor_180(self):
        battle = state([unit(quantity=20)], [unit(quantity=30, x=6)])
        battle["friendly_projectiles"] = [rocket()]
        result, sound = ground_projectile_pass(battle, RULES)
        self.assertEqual(result["hostile_groups"][0][1], 28)
        self.assertEqual(result["hostile_groups"][0][12:15], [8, 4, 3])
        self.assertEqual(result["friendly_projectiles"], []);self.assertEqual(sound, 7)

    def test_impacts_miss_empty_cells_and_never_damage_own_side(self):
        battle = state([unit(quantity=20)], [unit(quantity=30, x=6)])
        battle["friendly_projectiles"] = [rocket(x=5), rocket(x=9)]
        before = deepcopy(battle);result, sound = ground_projectile_pass(battle, RULES, 4)
        self.assertEqual(result["friendly_groups"], battle["friendly_groups"])
        self.assertEqual(result["hostile_groups"], battle["hostile_groups"])
        self.assertEqual(sound, 4);self.assertEqual(result["friendly_projectiles"], [])
        self.assertEqual(battle, before)

    def test_compaction_processes_consecutive_impacts_and_advances_remaining_once(self):
        battle = state([], [unit(quantity=30, x=6)])
        battle["friendly_projectiles"] = [rocket(), rocket(), rocket(step=1, duration=8)]
        result, _ = ground_projectile_pass(battle, RULES)
        self.assertEqual(result["hostile_groups"][0][1], 26)
        self.assertEqual(len(result["friendly_projectiles"]), 1)
        self.assertEqual(result["friendly_projectiles"][0][8:10], [2, 0])

    def test_damage_floor_cap_and_death(self):
        for power, count, expected in ((0, 30, 29), (100000, 30, 15), (100000, 3, 0)):
            battle = state([], [unit(quantity=count, x=6)]);battle["friendly_projectiles"] = [rocket(power=power)]
            result, sound = ground_projectile_pass(battle, RULES)
            self.assertEqual(result["hostile_groups"][0][1], expected)
            self.assertEqual(result["hostile_groups"][0][12], 7 if expected == 0 else 8)
            self.assertEqual(sound, 6 if expected == 0 else 7)

    def test_expired_zero_duration_and_off_board_rockets_cannot_stall_or_crash(self):
        battle = state([], [unit(quantity=30, x=6)])
        battle["friendly_projectiles"] = [rocket(step=9), rocket(step=1, duration=0), rocket(x=40)]
        result, _ = ground_projectile_pass(battle, RULES)
        self.assertEqual(result["friendly_projectiles"], [])
        self.assertEqual(result["hostile_groups"][0][1], 26)

    def test_base_footprints_match_attack_and_defense_layout(self):
        for attacking in (False, True):
            battle = state();battle["player_attacking"] = attacking
            result = ground_animation_pass(battle)
            friendly = {(cx, cy) for cx in range(16) for cy in range(9) if result["board"][cx][cy] == 21}
            hostile = {(cx, cy) for cx in range(16) for cy in range(9) if result["board"][cx][cy] == 121}
            self.assertEqual(friendly, {(0, 4)} if attacking else {(0, 4), (0, 5), (1, 4), (1, 5)})
            self.assertEqual(hostile, {(14, 4), (14, 5), (15, 4), (15, 5)} if attacking else {(15, 4)})

    def test_explicit_base_target_and_base_projectile_use_special_record(self):
        battle = state([unit(quantity=10)], [target(x=12)])
        battle["friendly_groups"][0][15:17] = [3, 21];battle["hostile_special"][4] = 6
        result, sound = ground_attack_pass(battle, MOTION, RULES)
        self.assertEqual(result["hostile_special"][1], 0);self.assertEqual(result["hostile_special"][12], 7)
        self.assertEqual(result["hostile_groups"][0][1], 30);self.assertEqual(sound, 10)
        battle["board"][6][4] = 121;battle["friendly_projectiles"] = [rocket()]
        result, sound = ground_projectile_pass(battle, RULES)
        self.assertEqual(result["hostile_special"][1], 0);self.assertEqual(sound, 10)

    def test_base_pursuit_keeps_valid_slot_21_order(self):
        battle = state([unit()], [target(x=12)])
        battle["friendly_groups"][0][15:17] = [3, 21]
        result = ground_movement_pass(battle, MOTION, MOVEMENT_RULES)
        self.assertEqual(result["friendly_groups"][0][15:17], [3, 21])
        self.assertEqual(result["friendly_groups"][0][9], 1)

    def test_cleanup_releases_dead_and_invalid_reservations_including_special(self):
        battle = state([unit(quantity=0)], [unit(quantity=2, x=6)])
        battle["board"][4][4] = 1;battle["board"][7][4] = 101;battle["board"][8][4] = 20
        battle["board"][14][4] = 121;battle["hostile_special"][1] = 0
        result = ground_completion_pass(battle)
        self.assertEqual([result["board"][cx][4] for cx in (4, 5, 6, 7, 8, 14)], [0, 0, 101, 101, 0, 0])
        self.assertTrue(result["done"]);self.assertFalse(result["player_won"])

    def test_both_sides_dead_and_instant_win_priority_follow_original(self):
        result = ground_completion_pass(state());self.assertTrue(result["done"]);self.assertTrue(result["player_won"])
        battle = state([unit()], [unit(x=6)]);battle["instant_kill"] = True
        result = ground_completion_pass(battle);self.assertTrue(result["done"]);self.assertTrue(result["player_won"])
        battle["friendly_groups"] = []
        result = ground_completion_pass(battle);self.assertFalse(result["player_won"])

    def test_remaining_rockets_and_death_frames_delay_completion(self):
        battle = state([unit()], []);battle["friendly_projectiles"] = [rocket(step=1)]
        self.assertFalse(ground_completion_pass(battle)["done"])
        battle["friendly_projectiles"] = [];dead = unit(quantity=0, x=6);dead[12:15] = [7, 1, 0]
        battle["hostile_groups"] = [dead]
        self.assertFalse(ground_completion_pass(battle)["done"])
        dead[13] = 0;self.assertTrue(ground_completion_pass(battle)["done"])

    def test_animation_waits_and_selected_dead_group_clear_on_correct_side(self):
        first = unit(quantity=0);first[12:15] = [7, 2, 1]
        second = unit(quantity=0);second[12:15] = [7, 1, 0]
        battle = state([first], [second]);battle.update(selected_group=1, selected_friendly=False)
        battle["friendly_special"][12:15] = [8, 2, 1]
        result = ground_animation_pass(battle)
        self.assertEqual(result["friendly_groups"][0][12:15], [7, 2, 0])
        self.assertEqual(result["hostile_groups"][0][12:15], [0, 0, 0])
        self.assertEqual(result["friendly_special"][12:15], [8, 2, 0]);self.assertEqual(result["selected_group"], 0)
        result = ground_animation_pass(result)
        self.assertEqual(result["friendly_groups"][0][12:15], [7, 1, 1])

    def test_full_frame_checks_completion_before_animation_and_emits_pause_once(self):
        dead = unit(quantity=0, x=6);dead[12:15] = [7, 1, 0]
        battle = state([unit()], [dead]);battle["friendly_groups"][0][15] = 1
        first, events = ground_frame(battle, MOTION, RULES, MOVEMENT_RULES)
        self.assertFalse(first["done"]);self.assertEqual(first["hostile_groups"][0][13], 0);self.assertEqual(events, [])
        resumed = json.loads(json.dumps(first))
        second, events = ground_frame(resumed, MOTION, RULES, MOVEMENT_RULES)
        self.assertEqual((second, events), ground_frame(first, MOTION, RULES, MOVEMENT_RULES))
        self.assertTrue(second["done"]);self.assertTrue(second["player_won"])
        self.assertEqual(events, [{"kind": "control_layout", "id": 30}])
        self.assertEqual(ground_frame(second, MOTION, RULES, MOVEMENT_RULES)[1], [])

    def test_formation_to_rocket_victory_and_saved_midflight_continuation(self):
        setup = state([unit(kind=4, quantity=10)], [unit(quantity=30)])
        setup["friendly_totals"] = [0, 0, 0, 10];setup["hostile_totals"] = [30, 0, 0, 0]
        setup["friendly_primary"] = [1000]*4;setup["friendly_secondary"] = [1000]*4
        setup["hostile_primary"] = [30]*4;setup["hostile_groups"][0][10:12] = [1, 1]
        current = initialize_ground_battle(setup, MOTION, player_attacking=True);current["rng"] = 1994
        resumed = None;had_rocket = False
        for frame in range(1500):
            current, events = ground_frame(current, MOTION, RULES, MOVEMENT_RULES)
            if resumed is not None:
                resumed, resumed_events = ground_frame(resumed, MOTION, RULES, MOVEMENT_RULES)
                self.assertEqual((current, events), (resumed, resumed_events))
            if not had_rocket and current["friendly_projectiles"]:
                resumed = json.loads(json.dumps(current));had_rocket = True
            if current["done"]:break
        self.assertTrue(had_rocket);self.assertTrue(current["done"]);self.assertTrue(current["player_won"])
        self.assertEqual(frame+1, 1012);self.assertEqual(current["rng"], 3429995094)
        self.assertEqual(current["friendly_groups"][0][1], 10);self.assertEqual(current["hostile_groups"][0][1], 0)
        self.assertEqual(current["friendly_projectiles"], [])


if __name__ == "__main__":unittest.main()
