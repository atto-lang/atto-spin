#!/usr/bin/env python3
"""Summarize warm sampled Oreslang metrics separately from cold core events."""
import argparse
from collections import defaultdict, Counter
import json
from pathlib import Path
import statistics

def summarize(directory):
    groups=defaultdict(list);traces=defaultdict(Counter);values_by_trace=defaultdict(dict)
    for filename in ('stdout.log','stderr.log'):
        for line in (directory/filename).read_text().splitlines():
            if not line.startswith('{'):continue
            row=json.loads(line)
            if row.get('schema')=='oreslang-otel.v1' and row.get('signal')=='metric':
                key='warm.'+row['name'];groups[key].append(row['value']/1e6)
                traces[row['ores_trace_id']][row['name']]+=1
                values_by_trace[row['ores_trace_id']][row['name']]=row['value']
            elif row.get('schema')=='ores-core-perf.v1' and row.get('kind')=='phase':
                groups['cold.core.'+row['phase']].append(row['duration_ns']/1e6)
    result=json.loads((directory/'result.json').read_text())
    expected={'admission.to_claim','mailbox.move_to_claim','actor.prepare','response.await',
              'admission.to_response_continuation','admission.to_dispatch','routing.dispatch'}
    if result.get('profile_schema',1)==2:
        expected |= {'http.admission_to_queue','http.queue','accept.ready_to_resume','supervisor.prepare'}
    if len(traces)!=result.get('sampled_requests',0) or any(names!=dict.fromkeys(expected,1) for names in traces.values()):
        raise ValueError('Missing/incomplete sampled request telemetry')
    if result.get('profile_schema',1)==2:
        parts=('http.admission_to_queue','http.queue','accept.ready_to_resume','supervisor.prepare')
        for values in values_by_trace.values():
            if any(values[name]<0 for name in parts) or sum(values[name] for name in parts)!=values['admission.to_dispatch']:
                raise ValueError('Invalid pre-dispatch timing decomposition')
    return {name:{'count':len(values),'mean_ms':round(statistics.mean(values),6),
                  'p50_ms':round(statistics.median(values),6),
                  'p95_ms':round(sorted(values)[max(0,__import__('math').ceil(.95*len(values))-1)],6)}
            for name,values in sorted(groups.items())}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    args=parser.parse_args();summary=summarize(args.directory)
    (args.directory/'phases.json').write_text(json.dumps(summary,indent=2)+'\n')
    for name,row in summary.items():print(f"{name:48} n={row['count']:6} mean={row['mean_ms']:10.4f} ms p95={row['p95_ms']:10.4f} ms")
