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
from unittest.mock import patch

import integration
import transport_security


class IntegrationReceiptContract(unittest.TestCase):
    def test_full_contract_accepts_exact_functional_and_wire_counts(self):
        self.assertEqual(
            integration.verify_guest_receipt(141, 25),
            {'checks': 141, 'functional_checks': 116, 'raw_wire_checks': 25})

    def test_rejects_short_raw_wire_matrix(self):
        with self.assertRaisesRegex(AssertionError, 'raw-wire checks'):
            integration.verify_guest_receipt(140, 24)

    def test_rejects_short_functional_suite(self):
        with self.assertRaisesRegex(AssertionError, 'functional checks'):
            integration.verify_guest_receipt(140, 25)

    def test_rejects_unexpected_extra_count(self):
        with self.assertRaises(AssertionError):
            integration.verify_guest_receipt(142, 25)

    def test_raw_wire_manifest_includes_seven_malformed_authority_cases(self):
        good_shared = (b'HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nshared', True)
        good_chunked = (b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabc', True)
        with patch.object(transport_security, 'assert_rejected', return_value=1) as rejected:
            with patch.object(transport_security, '_exchange',
                              side_effect=[good_shared, good_chunked]) as exchanges:
                self.assertEqual(transport_security.run(0), 25)
        self.assertEqual(rejected.call_count, 23)
        self.assertEqual(exchanges.call_count, 2)
        names = [call.args[1] for call in rejected.call_args_list]
        for name in ('host_nonnumeric_port', 'host_empty_authority',
                     'host_out_of_range_port', 'host_invalid_ipv6',
                     'host_empty_port', 'host_unbracketed_ipv6',
                     'host_percent_encoded_space'):
            self.assertIn(name, names)

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
