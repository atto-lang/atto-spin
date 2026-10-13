#!/usr/bin/env python3
"""Summarize warm sampled Oreslang metrics separately from cold core events."""
import argparse
from collections import defaultdict, Counter
import json
from pathlib import Path
import statistics

def summarize(directory):
    groups=defaultdict(list);traces=defaultdict(Counter)
    for filename in ('stdout.log','stderr.log'):
        for line in (directory/filename).read_text().splitlines():
            if not line.startswith('{'):continue
            row=json.loads(line)
            if row.get('schema')=='oreslang-otel.v1' and row.get('signal')=='metric':
                key='warm.'+row['name'];groups[key].append(row['value']/1e6)
                traces[row['ores_trace_id']][row['name']]+=1
            elif row.get('schema')=='ores-core-perf.v1' and row.get('kind')=='phase':
                groups['cold.core.'+row['phase']].append(row['duration_ns']/1e6)
    result=json.loads((directory/'result.json').read_text())
    expected={'admission.to_claim','mailbox.move_to_claim','actor.prepare','response.await',
              'admission.to_response_continuation','admission.to_dispatch','routing.dispatch'}
    if len(traces)!=result.get('sampled_requests',0) or any(names!=dict.fromkeys(expected,1) for names in traces.values()):
        raise ValueError('Missing/incomplete sampled request telemetry')
    return {name:{'count':len(values),'mean_ms':round(statistics.mean(values),6),
                  'p50_ms':round(statistics.median(values),6),
                  'p95_ms':round(sorted(values)[max(0,__import__('math').ceil(.95*len(values))-1)],6)}
            for name,values in sorted(groups.items())}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    args=parser.parse_args();summary=summarize(args.directory)
    (args.directory/'phases.json').write_text(json.dumps(summary,indent=2)+'\n')
    for name,row in summary.items():print(f"{name:48} n={row['count']:6} mean={row['mean_ms']:10.4f} ms p95={row['p95_ms']:10.4f} ms")
