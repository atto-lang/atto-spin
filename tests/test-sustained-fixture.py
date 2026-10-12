#!/usr/bin/env python3
"""Structural regression checks for exact per-request scheduling operations.

This enforces syntactic parity; real runtime behavior is checked by funded CI.
"""
from pathlib import Path
import re
import unittest

FIXTURE = Path(__file__).with_name('sustained-pool-server.ores')
NAMES = ('FreshShared', 'ReusedShared', 'FreshIsolated', 'ReusedIsolated')


def actor_body(source, name):
    kind = 'isoactor' if name.endswith('Isolated') else 'actor'
    pattern = r'define ' + kind + r' ' + name + r' as\n(.*?)\nend'
    match = re.search(pattern, source, re.S)
    if match is None:
        raise AssertionError(f'missing {name} actor fixture')
    return match.group(1)


class SustainedFixtureContractTest(unittest.TestCase):
    def test_exactly_one_suspends_call_cooperate_and_await_per_request(self):
        source = FIXTURE.read_text()
        for name in NAMES:
            with self.subTest(actor=name):
                body = actor_body(source, name)
                method = re.search(r'suspends checkpoint\(\): int \{(.*?)\n  \}', body, re.S)
                self.assertIsNotNone(method, 'missing explicitly suspends checkpoint')
                self.assertEqual(method.group(1).count('rt cooperate;'), 1)
                self.assertIn('return 1;', method.group(1))
                receive = re.search(
                    r'suspends receive\(ActorMail<String> mail\): void \{(.*?)\n  \}', body, re.S)
                self.assertIsNotNone(receive)
                request = receive.group(1)
                self.assertEqual(request.count('self.checkpoint();'), 1)
                self.assertEqual(request.count('await request.respond('), 1)
                self.assertEqual(len(re.findall(r'\bawait\b', request)), 1)
                self.assertEqual(len(re.findall(r'\brt cooperate\b', body)), 1)
                self.assertIn('request.set_header("X-Work-Verified", "1");', request)
                self.assertIn('request.set_header("X-Work-Verified", "0");', request)
                self.assertEqual(request.count('self.end();'), int(name.startswith('Fresh')))

    def test_fresh_and_reused_have_identical_non_lifecycle_work(self):
        source = FIXTURE.read_text()
        for mode in ('Shared', 'Isolated'):
            with self.subTest(mode=mode):
                fresh = actor_body(source, 'Fresh' + mode)
                reused = actor_body(source, 'Reused' + mode)
                self.assertEqual(fresh.replace('    self.end();\n', ''), reused)


if __name__ == '__main__':
    unittest.main()
