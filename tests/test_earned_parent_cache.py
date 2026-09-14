"""Headless checks for process-local accepted-parent materialization."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT/'tools'))

from earned_parent_cache import EarnedParentCache, ParentCacheError, inspect_accepted_chain
from openreunion.dos.effect_control import initial_effects
from openreunion.dos.music_control import initial_audio
from openreunion.dos.session import RecoveredSession
from test_recovered import fixture
from test_result_animation import defeat


class FakeContent:
    def __init__(self, catalog, state, *, hero=1):
        self.catalog = deepcopy(catalog)
        self.state = deepcopy(state)
        self.hero = hero

    def new_game(self):
        return RecoveredSession(self.catalog, self.state, hero=self.hero)


def apply_journal(content, journals):
    session = content.new_game()
    for journal in journals:
        for command in journal:
            session.apply(command['action'], **command['arguments'])
    return session


def accepted_row(state, journal):
    return {
        'passed': True, 'prepared_state': False, 'admin_used': False,
        'journal': deepcopy(journal), 'final_state': deepcopy(state),
    }


def write_chain(directory, content):
    first_journal = [{'action': 'pause_research', 'arguments': {'paused': True}}]
    first = apply_journal(content, [first_journal])
    first_report = {
        'passed': True, 'prepared_state': False,
        'adapters': [accepted_row(first.state, first_journal) for _ in range(2)],
    }
    base = directory/'base.json'
    base.write_text(json.dumps(first_report))

    second_journal = [{'action': 'pause_research', 'arguments': {'paused': False}}]
    endpoint = apply_journal(content, [first_journal, second_journal])
    second_report = {
        'passed': True, 'prepared_state': False, 'parent': 'base.json',
        'parent_sha256': hashlib.sha256(base.read_bytes()).hexdigest(),
        'adapters': [accepted_row(endpoint.state, second_journal) for _ in range(2)],
    }
    tip = directory/'tip.json'
    tip.write_text(json.dumps(second_report))
    return base, tip, endpoint, [first_journal, second_journal]


class EarnedParentCacheTests(unittest.TestCase):
    def setUp(self):
        catalog, state = fixture()
        self.content = FakeContent(catalog, state)

    def test_replays_once_then_returns_independent_fresh_validated_sessions(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            _, tip, endpoint, journals = write_chain(project, self.content)
            cache = EarnedParentCache(project)
            calls = []

            def replay():
                calls.append(1)
                session = apply_journal(self.content, journals)
                session.audio = initial_audio()
                session.audio.update(scene='talk', track='TALK', automatic=False,
                                     frames=456789, paused=True)
                session.effects = initial_effects()
                session.effects.update(sample='TRACTOR', frames=71, paused=True)
                return session

            first, initial = cache.load_or_replay(self.content, tip, 0, replay)
            self.assertEqual(initial['mode'], 'replayed')
            self.assertEqual(initial['replay_adapter'], 0)
            self.assertEqual(first.state, endpoint.state)
            self.assertEqual(first.hero, 1)
            self.assertEqual(first.audio['frames'], 456789)
            self.assertEqual(first.effects['frames'], 71)
            self.assertEqual(first.result_animation, endpoint.result_animation)
            first.state['research_paused'] = True
            first.audio['frames'] = 1
            first.effects['frames'] = 1

            second, reused = cache.load_or_replay(self.content, tip, 1, replay)
            self.assertEqual(reused['mode'], 'cache_verified')
            self.assertEqual(reused['replay_adapter'], 0)
            self.assertEqual(second.state, endpoint.state)
            self.assertFalse(second.state['research_paused'])
            self.assertEqual(second.hero, 1)
            self.assertEqual(second.audio['frames'], 456789)
            self.assertEqual(second.effects['frames'], 71)
            self.assertEqual(second.result_animation, endpoint.result_animation)
            self.assertIsNot(first, second)
            self.assertEqual(len(calls), 1)
            self.assertEqual(initial['endpoint_save_sha256'], reused['endpoint_save_sha256'])
            self.assertEqual(initial['chain_sha256'], reused['chain_sha256'])

    def test_new_game_or_catalog_difference_gets_a_distinct_replay_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            _, tip, endpoint, journals = write_chain(project, self.content)
            cache = EarnedParentCache(project)
            calls = []

            def accepted_replay(content):
                def run():
                    calls.append(1)
                    # A replay callback still has to produce the exact accepted
                    # endpoint; key changes merely prohibit unsafe reuse.
                    return RecoveredSession(content.catalog, endpoint.state, hero=1)
                return run

            cache.load_or_replay(self.content, tip, 0, accepted_replay(self.content))
            changed_initial = FakeContent(self.content.catalog, self.content.state)
            changed_initial.state['log'].append('Different deterministic New Game')
            _, initial_result = cache.load_or_replay(
                changed_initial, tip, 1, accepted_replay(changed_initial))
            self.assertEqual(initial_result['mode'], 'replayed')

            changed_catalog = deepcopy(self.content.catalog)
            changed_catalog['cache_test_marker'] = 1
            changed_content = FakeContent(changed_catalog, self.content.state)
            _, catalog_result = cache.load_or_replay(
                changed_content, tip, 1, accepted_replay(changed_content))
            self.assertEqual(catalog_result['mode'], 'replayed')
            self.assertEqual(len(calls), 3)

    def test_active_result_cursor_survives_cache_as_a_fresh_paused_load(self):
        replayed = defeat()
        replayed.hero = 1
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            journal = []
            report = {
                'passed': True, 'prepared_state': False,
                'adapters': [accepted_row(replayed.state, journal) for _ in range(2)],
            }
            tip = project/'result.json'
            tip.write_text(json.dumps(report))
            content = FakeContent(replayed.catalog, replayed.state, hero=1)
            cache = EarnedParentCache(project)

            first, _ = cache.load_or_replay(content, tip, 0, lambda: replayed)
            expected = dict(replayed.result_animation, paused=True)
            self.assertEqual(first.result_animation, expected)
            first.result_animation['counter'] = 13
            second, provenance = cache.load_or_replay(
                content, tip, 1,
                lambda: self.fail('a verified cache hit must not replay'))
            self.assertEqual(second.result_animation, expected)
            self.assertEqual(second.hero, 1)
            self.assertEqual(provenance['mode'], 'cache_verified')

    def test_legacy_reports_may_omit_only_the_prepared_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            base, tip, endpoint, _ = write_chain(project, self.content)
            base_report = json.loads(base.read_text())
            base_report.pop('prepared_state')
            for row in base_report['adapters']:
                row.pop('prepared_state')
            base.write_text(json.dumps(base_report))
            tip_report = json.loads(tip.read_text())
            tip_report.pop('prepared_state')
            tip_report['parent_sha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
            for row in tip_report['adapters']:
                row.pop('prepared_state')
            tip.write_text(json.dumps(tip_report))

            chain = inspect_accepted_chain(project, tip)
            self.assertEqual(chain.endpoint_state, endpoint.state)
            self.assertEqual(chain.paths, ('base.json', 'tip.json'))

    def test_chain_validation_fails_closed(self):
        mutations = ('prepared', 'adapter_prepared', 'adapter_failed', 'assisted',
                     'admin', 'journal_difference', 'parent_hash', 'parent_escape')
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                base, tip, _, _ = write_chain(project, self.content)
                report = json.loads(tip.read_text())
                if mutation == 'prepared':
                    report['prepared_state'] = True
                elif mutation == 'adapter_prepared':
                    report['adapters'][0]['prepared_state'] = True
                elif mutation == 'adapter_failed':
                    report['adapters'][0]['passed'] = False
                elif mutation == 'assisted':
                    report['adapters'][0]['final_state']['assisted'] = True
                    report['adapters'][1]['final_state']['assisted'] = True
                elif mutation == 'admin':
                    command = {'action': 'admin', 'arguments': {'command': 'give credits 1'}}
                    report['adapters'][0]['journal'].append(command)
                    report['adapters'][1]['journal'].append(command)
                elif mutation == 'journal_difference':
                    report['adapters'][1]['journal'][0]['arguments']['paused'] = True
                elif mutation == 'parent_hash':
                    base.write_text(base.read_text()+' ')
                elif mutation == 'parent_escape':
                    report['parent'] = '../outside.json'
                if mutation != 'parent_hash':
                    tip.write_text(json.dumps(report))
                with self.assertRaises(ParentCacheError):
                    inspect_accepted_chain(project, tip)

    def test_chain_change_during_replay_is_never_cached(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            base, tip, _, journals = write_chain(project, self.content)
            cache = EarnedParentCache(project)

            def replay_then_replace_parent():
                session = apply_journal(self.content, journals)
                # Replace the complete chain with another internally valid one.
                _, replacement, _, _ = write_chain(project/'replacement', self.content)
                replacement_report = json.loads(replacement.read_text())
                replacement_base = project/'replacement'/'base.json'
                base.write_bytes(replacement_base.read_bytes())
                replacement_report['parent'] = 'base.json'
                replacement_report['parent_sha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
                replacement_report['replacement_marker'] = True
                tip.write_text(json.dumps(replacement_report))
                return session

            (project/'replacement').mkdir()
            with self.assertRaisesRegex(ParentCacheError, 'changed during replay'):
                cache.load_or_replay(self.content, tip, 0, replay_then_replace_parent)
            self.assertEqual(cache._entries, {})

    def test_real_conquests_accepted_chain_is_inspectable(self):
        tip = PROJECT/'reports'/'graphical-league-conquests-r1.json'
        if not tip.exists():
            self.skipTest('Accepted Conquests report is not present in this checkout')
        chain = inspect_accepted_chain(PROJECT, tip)
        self.assertEqual(len(chain.paths), 29)
        self.assertEqual(chain.paths[-1], 'reports/graphical-league-conquests-r1.json')
        self.assertFalse(chain.endpoint_state['assisted'])


if __name__ == '__main__':
    unittest.main()
