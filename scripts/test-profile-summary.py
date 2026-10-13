#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('summary',Path(__file__).with_name('summarize-profile.py'))
summary=importlib.util.module_from_spec(spec);spec.loader.exec_module(summary)

class ProfileSummaryTests(unittest.TestCase):
    def test_rejects_missing_and_duplicate_metrics(self):
        names=['admission.to_claim','mailbox.move_to_claim','actor.prepare','response.await',
               'admission.to_response_continuation','admission.to_dispatch','routing.dispatch']
        rows=[dict(schema='oreslang-otel.v1',signal='metric',name=name,value=1000000,ores_trace_id='one') for name in names]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'stderr.log').write_text('')
            (root/'result.json').write_text(json.dumps({'sampled_requests':1}))
            def write(data):(root/'stdout.log').write_text('\n'.join(map(json.dumps,data)))
            write(rows)
            self.assertEqual(summary.summarize(root)['warm.routing.dispatch']['mean_ms'],1)
            for invalid in (rows[:-1],rows+[rows[0]]):
                write(invalid)
                with self.assertRaisesRegex(ValueError,'Missing/incomplete'):summary.summarize(root)

if __name__=='__main__':unittest.main()
