#!/usr/bin/env python3
"""Self-tests for Linux process resource measurement."""
import os
import time
import unittest
from process_resources import ProcessSampler, _aggregate, process_snapshot

class ProcessSamplerTests(unittest.TestCase):
    def test_current_process_and_missing_process(self):
        snap = process_snapshot(os.getpid())
        self.assertIsNotNone(snap)
        self.assertGreater(snap["rss_bytes"], 0)
        self.assertGreaterEqual(snap["threads"], 1)
        self.assertIsNone(process_snapshot(999999999))

    def test_sample_cpu_and_memory_with_real_process(self):
        sample = ProcessSampler(os.getpid(), interval_s=.01)
        sample.start()
        time.sleep(.045)
        result = sample.finish()
        for role in ("server", "client"):
            row = result["summary"][role]
            self.assertGreaterEqual(row["samples"], 2)
            self.assertGreater(row["peak_rss_bytes"], 0)
            self.assertIsNotNone(row["process_cpu_percent"])
            self.assertGreaterEqual(row["process_cpu_percent"], 0)

    def test_reject_pid_reuse_and_empty_samples(self):
        self.assertIsNone(_aggregate([])["process_cpu_percent"])
        before = {"t_monotonic":1.0, "start_ticks":100, "cpu_seconds":1, "rss_bytes":512, "threads":1}
        after = dict(before, t_monotonic=2.0, start_ticks=200)
        self.assertIsNone(_aggregate([before, after])["process_cpu_percent"])

if __name__=="__main__":
    unittest.main()
