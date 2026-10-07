#!/usr/bin/env python3
"""Summarize JFR sampled allocation weights inside benchmark time windows.
Input: JSON from `jfr print --json --events jdk.ObjectAllocationSample recording.jfr`.
These are sample estimates, not exact per-request allocation counts.
"""
import argparse, datetime, json, re
parser = argparse.ArgumentParser()
parser.add_argument('benchmark_json')
parser.add_argument('jfr_json')
args = parser.parse_args()
with open(args.benchmark_json) as f: benchmark = json.load(f)
with open(args.jfr_json) as f: events = json.load(f)['recording']['events']
result = {}
for mode in ['shared', 'isolated']:
    selected = []
    for event in events:
        values = event['values']
        stamp = re.sub(r'(\.\d{6})\d+', r'\1', values['startTime']).replace('Z','+00:00')
        when = datetime.datetime.fromisoformat(stamp).timestamp()
        if benchmark[mode]['epoch_start'] <= when <= benchmark[mode]['epoch_end']:
            selected.append(values)
    weight = sum(e['weight'] for e in selected)
    result[mode] = {'samples':len(selected), 'sampled_weight_bytes':weight,
                    'estimated_bytes_per_request':round(weight/benchmark['requests_per_mode'])}
print(json.dumps({'warning':'JFR sampled allocation estimates; whole JVM, not actor heap accounting', 'modes':result}, indent=2))
