"""Original-free attack scenarios and confirmed same-cell rocket regression."""
from copy import deepcopy
import struct
import unittest
from test_ground_geometry import unit, MOTION
from openreunion.core import GameError
from openreunion.dos.campaign import random_bounded
from openreunion.dos.ground_attacks import ground_attack_pass, projectile_heading


RULES = {"cooldowns": [30, 20, 10, 60], "target_coefficients": [40, 20, 5, 10],
         "animation_lengths": [10, 4, 4, 4, 4, 9, 9, 10, 4]}


def battle(friendly=None, hostile=None):
    result = {"rng": 0}
    for side, rows in (("friendly", friendly), ("hostile", hostile)):
        result[side+"_groups"] = rows if rows is not None else []
        result[side+"_totals"] = [100]*4
        result[side+"_primary"] = [500]*4
        result[side+"_secondary"] = [2000]*4
    return result


def target(kind=1, count=30, x=6, y=4):
    row = unit(kind, count, x, y);row[6] = 10
    return row


class GroundAttackTests(unittest.TestCase):
    def test_direct_power_uses_original_class_total_and_target_coefficient(self):
        for kind, expected in ((1, 8), (2, 4), (3, 1), (4, 2)):
            source = battle([unit(quantity=20)], [target(kind)])
            result, sound = ground_attack_pass(source, MOTION, RULES)
            attacker, victim = result["friendly_groups"][0], result["hostile_groups"][0]
            self.assertEqual(victim[1], 30-expected)
            self.assertEqual(attacker[6], 29)
            self.assertEqual(attacker[12:15], [1, 4, 3])
            self.assertEqual(victim[12:15], [8, 4, 3])
            self.assertEqual(sound, 1)

    def test_damage_has_one_casualty_floor_fifteen_cap_and_death_animation(self):
        for pool, count, left in ((0, 30, 29), (100000, 30, 15), (100000, 4, 0)):
            source = battle([unit(quantity=20)], [target(count=count)])
            source["friendly_primary"][0] = pool
            result, sound = ground_attack_pass(source, MOTION, RULES)
            victim = result["hostile_groups"][0]
            self.assertEqual(victim[1], left)
            self.assertEqual(victim[12], 7 if left == 0 else 8)
            self.assertEqual(sound, 6 if left == 0 else 1)

    def test_explicit_target_wins_otherwise_last_eligible_living_group(self):
        source = battle([unit(quantity=20)], [target(), target(x=4), target(count=0)])
        result, _ = ground_attack_pass(source, MOTION, RULES)
        self.assertEqual([r[1] for r in result["hostile_groups"]], [30, 22, 0])
        source["friendly_groups"][0][15:17] = [3, 1]
        result, _ = ground_attack_pass(source, MOTION, RULES)
        self.assertEqual([r[1] for r in result["hostile_groups"]], [22, 30, 0])

    def test_invalid_pursuit_target_cancels_player_and_retargets_hostile(self):
        source = battle([target(x=1), target(x=10)], [target(x=9)])
        source["friendly_groups"][0][15:17] = [3, 255]
        source["hostile_groups"][0][15:17] = [3, 0]
        result, _ = ground_attack_pass(source, MOTION, RULES)
        self.assertEqual(result["friendly_groups"][0][15], 1)
        self.assertEqual(result["hostile_groups"][0][15:17], [3, 2])
        source["friendly_groups"] = []
        result, _ = ground_attack_pass(source, MOTION, RULES)
        self.assertEqual(result["hostile_groups"][0][16], 0)

    def test_animation_and_cooldown_block_attacks_but_living_cooldowns_tick(self):
        source = battle([unit(quantity=20), unit(quantity=0), unit(quantity=20)], [target()])
        source["friendly_groups"][0][6] = 1
        source["friendly_groups"][1][6] = 7
        source["friendly_groups"][2][12:15] = [8, 4, 3]
        result, sound = ground_attack_pass(source, MOTION, RULES)
        self.assertEqual(result["hostile_groups"][0][1], 30)
        self.assertEqual([r[6] for r in result["friendly_groups"]], [0, 7, 0])
        self.assertEqual(result["friendly_groups"][2][12:15], [8, 4, 3])
        self.assertEqual(sound, 0)

    def test_rng_side_order_changes_who_fires_and_hit_animation_prevents_reply(self):
        seeds = {random_bounded(seed, 2)[1]: seed for seed in range(100)}
        self.assertEqual(set(seeds), {0, 1})
        for order, seed in seeds.items():
            source = battle([unit(quantity=20)], [unit(quantity=20, x=6)])
            source["rng"] = seed
            result, _ = ground_attack_pass(source, MOTION, RULES)
            self.assertEqual([result[s+"_groups"][0][1] for s in ("friendly", "hostile")],
                             [20, 12] if order == 0 else [12, 20])
            self.assertEqual(result["rng"], random_bounded(seed, 2)[0])

    def test_rocket_preserves_existing_projectiles_and_defers_secondary_damage(self):
        source = battle([unit(kind=4, quantity=10)], [target(x=8)])
        source["friendly_projectiles"] = [[77]*18]
        before = deepcopy(source)
        result, sound = ground_attack_pass(source, MOTION, RULES)
        self.assertEqual(source, before)
        self.assertEqual(result["hostile_groups"][0][1], 30)
        self.assertEqual(result["friendly_projectiles"][0], [77]*18)
        projectile = struct.unpack("<7hI", bytes(result["friendly_projectiles"][1]))
        self.assertEqual(projectile, (144, 67, 192, 67, 1, 24, projectile_heading((5, 4), (8, 4)), 200))
        self.assertEqual(result["friendly_groups"][0][6], 59)
        self.assertEqual(result["friendly_groups"][0][12:15], [5, 9, 3])
        self.assertEqual(sound, 5)

    def test_close_rocket_launcher_uses_primary_pool_and_moving_direction_stays(self):
        source = battle([unit(kind=4, quantity=10)], [target(x=4)])
        source["friendly_groups"][0][9] = 1
        result, sound = ground_attack_pass(source, MOTION, RULES)
        self.assertEqual(result["friendly_groups"][0][8], 3)
        self.assertEqual(result["hostile_groups"][0][1], 26)
        self.assertEqual(result["friendly_projectiles"], [])
        self.assertEqual(sound, 4)
        source["friendly_groups"][0][9] = 0
        result, _ = ground_attack_pass(source, MOTION, RULES)
        self.assertEqual(result["friendly_groups"][0][8], 1)

    def test_same_grid_cell_opposite_offsets_launch_without_original_divide_fault(self):
        source = battle([unit(kind=4, quantity=10)], [target(x=5)])
        source["friendly_groups"][0][8:11] = [1, 1, 15]
        source["hostile_groups"][0][8:11] = [3, 1, 15]
        result, _ = ground_attack_pass(source, MOTION, RULES)
        projectile = struct.unpack("<7hI", bytes(result["friendly_projectiles"][0]))
        self.assertEqual(projectile[:6], (129, 67, 159, 67, 1, 16))
        self.assertEqual(projectile[6], projectile_heading((129, 67), (159, 67)))
        self.assertEqual(projectile_heading((5, 4), (5, 4)), 0)

    def test_invalid_power_pool_rejects_without_mutating_source(self):
        for field, value in (("friendly_totals", 0), ("friendly_primary", -1)):
            source = battle([unit(quantity=20)], [target()]);source[field][0] = value
            before = deepcopy(source)
            with self.assertRaises(GameError):ground_attack_pass(source, MOTION, RULES)
            self.assertEqual(source, before)

    def test_aircraft_missiles_add_fitted_power_for_both_sides(self):
        for side,opponent in (("friendly","hostile"),("hostile","friendly")):
            for missiles,expected in ((0,19),(90,16)):
                source=battle()
                source[side+"_groups"]=[unit(kind=3,quantity=10)]
                source[opponent+"_groups"]=[target(kind=2)]
                source[side+"_totals"][2]=10
                source[side+"_primary"][2]=280
                source[side+"_secondary"][2]=missiles
                before=deepcopy(source)
                result,sound=ground_attack_pass(source,MOTION,RULES)
                self.assertEqual(result[opponent+"_groups"][0][1],expected)
                self.assertEqual(result[side+"_groups"][0][6],9)
                self.assertEqual(result[side+"_groups"][0][12:15],[3,4,3])
                self.assertEqual(result[side+"_projectiles"],[])
                self.assertEqual(result["rng"],random_bounded(source["rng"],2)[0])
                self.assertEqual(sound,3)
                self.assertEqual(source,before)

    def test_aircraft_missile_only_loadout_and_depleted_group_use_class_pools(self):
        for count,total,primary,secondary,left in ((10,10,0,90,27),(5,20,560,180,23)):
            source=battle([unit(kind=3,quantity=count)],[target(kind=2)])
            source["friendly_totals"][2]=total
            source["friendly_primary"][2]=primary
            source["friendly_secondary"][2]=secondary
            result,_=ground_attack_pass(source,MOTION,RULES)
            self.assertEqual(result["hostile_groups"][0][1],left)

    def test_aircraft_missiles_respect_range_and_attack_barriers(self):
        for barrier in ("range","cooldown","animation"):
            source=battle([unit(kind=3,quantity=10)],[target(kind=2,x=8 if barrier=="range" else 6)])
            source["friendly_totals"][2]=10
            source["friendly_primary"][2]=280
            source["friendly_secondary"][2]=90
            if barrier=="cooldown":source["friendly_groups"][0][6]=1
            if barrier=="animation":source["friendly_groups"][0][12:15]=[8,4,3]
            result,sound=ground_attack_pass(source,MOTION,RULES)
            self.assertEqual(result["hostile_groups"][0][1],30)
            self.assertEqual(sound,0)

    def test_aircraft_rejects_negative_either_pool_before_combining(self):
        for field in ("friendly_primary","friendly_secondary"):
            source=battle([unit(kind=3,quantity=10)],[target(kind=2)])
            source[field][2]=-1;before=deepcopy(source)
            with self.assertRaises(GameError):ground_attack_pass(source,MOTION,RULES)
            self.assertEqual(source,before)


if __name__ == "__main__":unittest.main()
