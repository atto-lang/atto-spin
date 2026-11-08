#!/usr/bin/env python3
"""Host-only tests for fail-closed native guest integration receipt checks.

Importing integration.py does not start the compiler or guest. The complete
server.atto integration must still execute separately on an admitted runner.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest

import integration


class IntegrationReceiptContract(unittest.TestCase):
    def test_full_contract_accepts_exact_functional_and_wire_counts(self):
        self.assertEqual(
            integration.verify_guest_receipt(120, 18),
            {'checks': 120, 'functional_checks': 102, 'raw_wire_checks': 18})

    def test_rejects_short_raw_wire_matrix(self):
        with self.assertRaisesRegex(AssertionError, 'raw-wire checks'):
            integration.verify_guest_receipt(119, 17)

    def test_rejects_short_functional_suite(self):
        with self.assertRaisesRegex(AssertionError, 'functional checks'):
            integration.verify_guest_receipt(119, 18)

    def test_rejects_unexpected_extra_count(self):
        with self.assertRaises(AssertionError):
            integration.verify_guest_receipt(121, 18)

    def test_condition_requires_success_at_normal_optimization(self):
        integration.require_condition(True, 'accepted')
        with self.assertRaisesRegex(AssertionError, 'expected denial'):
            integration.require_condition(False, 'expected denial')

    def test_condition_remains_fail_closed_under_python_optimization(self):
        env = dict(os.environ)
        test_dir = str(Path(__file__).resolve().parent)
        env['PYTHONPATH'] = test_dir + os.pathsep + env.get('PYTHONPATH', '')
        run = subprocess.run(
            [sys.executable, '-B', '-O', '-c',
             "import integration; integration.require_condition(False, 'optimized-denial')"],
            env=env, capture_output=True, text=True, timeout=10, check=False)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('optimized-denial', run.stderr)


if __name__ == '__main__':
    unittest.main()
