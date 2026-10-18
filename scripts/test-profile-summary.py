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

    def test_accept_timing_schema_requires_all_four_new_phases(self):
        names=['admission.to_claim','mailbox.move_to_claim','actor.prepare','response.await',
               'admission.to_response_continuation','admission.to_dispatch','routing.dispatch',
               'http.admission_to_queue','http.queue','accept.ready_to_resume','supervisor.prepare']
        rows=[dict(schema='oreslang-otel.v1',signal='metric',name=name,value=1000000,ores_trace_id='one') for name in names]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'stderr.log').write_text('')
            (root/'result.json').write_text(json.dumps({'sampled_requests':1,'profile_schema':2}))
            next(row for row in rows if row['name']=='admission.to_dispatch')['value']=4000000
            (root/'stdout.log').write_text('\n'.join(map(json.dumps,rows)))
            self.assertEqual(summary.summarize(root)['warm.http.queue']['mean_ms'],1)
            for name in names[-4:]:
                (root/'stdout.log').write_text('\n'.join(json.dumps(row) for row in rows if row['name']!=name))
                with self.assertRaisesRegex(ValueError,'Missing/incomplete'):summary.summarize(root)
            rows[-1]['value']+=1
            (root/'stdout.log').write_text('\n'.join(map(json.dumps,rows)))
            with self.assertRaisesRegex(ValueError,'Invalid pre-dispatch'):
                summary.summarize(root)

if __name__=='__main__':unittest.main()
