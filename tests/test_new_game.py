"""Original-free bounds and initialization regressions for startup definitions."""
from copy import deepcopy
import hashlib
import struct
import unittest
from unittest.mock import patch

from openreunion.core import GameError
from openreunion.dos import new_game
from openreunion.dos.savefile import SaveBlocks


class NewGameTests(unittest.TestCase):
    def setUp(self):
        # Synthetic startup data only; no copyrighted binary test fixture.
        self.init = bytes(14002)
        self.digest = hashlib.sha256(self.init).hexdigest()
        self.catalog = {'sha256': 'a'*64, 'fleet_rules': [{}]*4+[{'default_name': 'Home defense'}]}
        self.definition = {'profile': new_game.PROFILE, 'executable_sha256': 'a'*64,
                           'static_blocks': ['00'*b['length'] for b in new_game.STATIC_BLOCKS],
                           'init': self.init.hex()}
        self.profile = patch.object(new_game, 'INIT_SHA256', self.digest)
        self.profile.start()
        self.addCleanup(self.profile.stop)

    def test_fresh_state_resets_runtime_fields_and_is_independent(self):
        before = deepcopy(self.definition)
        data, seed = new_game.startup_bytes(self.definition, self.catalog, 1994)
        blocks = SaveBlocks(data)
        self.assertEqual(blocks.number(0x95BE, 'I'), 120000)
        self.assertEqual(blocks.read(0x95C6, 24), bytes(24))
        self.assertEqual(blocks.number(0x95B4), 10)
        self.assertEqual([blocks.number(at) for at in (0x95DE, 0x95E0, 0x95E2, 0x95E4)], [2927, 8, 13, 23])
        self.assertEqual(blocks.read(0x91A0, 70), b'\xff'*70)
        self.assertEqual(blocks.number(0xA2C4), 0)
        self.assertEqual(blocks.number(0xA2C6), 1)
        local = blocks.read(0xA2D0, 10304, pointer=True)[5152:5313]
        self.assertEqual(local[19:23], bytes([1, 5, 0, 7]))
        self.assertEqual(local[29:], bytes(132))
        self.assertEqual(seed, 2454998771)
        self.assertEqual(self.definition, before)
        self.assertEqual(new_game.startup_bytes(self.definition, self.catalog, 1994), (data, seed))

    def test_changed_startup_asset_is_rejected(self):
        self.definition['init'] = '0100'+self.definition['init'][4:]
        with self.assertRaises(GameError):
            new_game.startup_bytes(self.definition, self.catalog, 1994)

    def test_truncated_and_malformed_blocks_are_rejected(self):
        for replacement in ([], [None]*len(new_game.STATIC_BLOCKS), ['zz'*b['length'] for b in new_game.STATIC_BLOCKS]):
            with self.subTest(replacement=str(replacement)[:40]):
                definition = deepcopy(self.definition)
                definition['static_blocks'] = replacement
                with self.assertRaises(GameError):
                    new_game.startup_bytes(definition, self.catalog, 1994)

    def test_wrong_profile_and_seed_are_rejected(self):
        for seed in (-1, 2**32, True, '1994'):
            with self.subTest(seed=seed), self.assertRaises(GameError):
                new_game.startup_bytes(self.definition, self.catalog, seed)
        self.definition['executable_sha256'] = 'b'*64
        with self.assertRaises(GameError):
            new_game.startup_bytes(self.definition, self.catalog, 1994)


if __name__ == '__main__':
    unittest.main()
