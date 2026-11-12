#!/usr/bin/env python3
"""Fail-closed parser and guest-receipt checks; not a substitute for live load."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

bench = SourceFileLoader("spin_matrix", str(Path(__file__).with_name("sustained-matrix.py"))).load_module()

class BenchContracts(unittest.TestCase):
    def test_canonical_fixture_has_two_pools_and_one_admission(self):
        self.assertEqual(bench.declared_limits(bench.FIXTURE.read_text()), (100, 10000))

    def test_reject_missing_or_unequal_pool_settings(self):
        with self.assertRaises(ValueError):
            bench.declared_limits("/* BENCHMARK_POOL */ 100")
        with self.assertRaises(ValueError):
            bench.declared_limits("/* BENCHMARK_POOL */ 100 /* BENCHMARK_POOL */ 128 /* BENCHMARK_ADMISSION */ 10000")

    def test_guest_counter_decoding(self):
        lines = ["9182", "POOL_COUNTERS", "2", "100", "101", "101", "0", "0"]
        self.assertEqual(bench.read_runtime_counters(lines), dict(
            pooled_created=2, pooled_reused=100, accepted=101,
            completed=101, rejected=0, active_after_shutdown=0))
        with self.assertRaisesRegex(ValueError, "truncated"):
            bench.read_runtime_counters(lines[:-1])
        with self.assertRaisesRegex(ValueError, "duplicated"):
            bench.read_runtime_counters(lines + ["POOL_COUNTERS"])

    def test_accept_exact_success_and_reuse(self):
        result = dict(attempts=100, successes=100, status={"200": 100},
                      errors={}, reused_connections=95)
        runtime = dict(pooled_created=2, pooled_reused=98, accepted=101,
                       completed=101, rejected=0, active_after_shutdown=0)
        self.assertEqual(bench.violations(result, runtime, 100), [])
        self.assertTrue(bench.violations({**result, "successes": 99}, runtime, 100))
        self.assertTrue(bench.violations({**result, "status": {"503": 100}}, runtime, 100))
        self.assertTrue(bench.violations({**result, "reused_connections": 0}, runtime, 100))
        for issue in ("pooled_reused", "rejected", "active_after_shutdown"):
            changed = {**runtime, issue: 1 if issue != "pooled_reused" else 0}
            self.assertTrue(bench.violations(result, changed, 100), issue)
        self.assertTrue(bench.violations(result, {**runtime, "pooled_created": 201}, 100))

if __name__ == "__main__":
    unittest.main()
