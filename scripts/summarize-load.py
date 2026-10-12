#!/usr/bin/env python3
"""Summarize matrix samples without counting overload rejection as successful throughput."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path


def quantile(values,p):
    if not values:return None
    a=sorted(values)
    return round(a[max(0,math.ceil(len(a)*p)-1)],2)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args();directory=args.directory
    results=[json.loads(s) for s in (directory/'results.jsonl').read_text().splitlines()]
    groups={}
    for result in results:
        key=(result['concurrency'],result['actor_limit'],result['mode'])
        groups.setdefault(key,[]).append(result)
    rows=[]
    for (concurrency,actors,mode),runs in groups.items():
        tag=f'c{concurrency}-a{actors}-{mode}'
        samples=[]
        for run in runs:samples.extend(json.loads((directory/f'{tag}-r{run["repeat"]}.samples.json').read_text()))
        good=[s for s in samples if s['status']==200 and not s['error']]
        status=Counter(s['status'] for s in samples)
        resources=json.loads((directory/(tag+'.resources.json')).read_text())
        counters=json.loads((directory/(tag+'.server.json')).read_text())
        if counters['active_after_shutdown']!=0 or counters['accepted']!=counters['completed']:
            raise RuntimeError('Server failed to drain: '+tag)
        if counters['peak_admitted_observed']>actors:raise RuntimeError('Admission limit exceeded: '+tag)
        row={'concurrency':concurrency,'actor_limit':actors,'mode':mode,'repeats':len(runs),
             'attempts':len(samples),'successes':len(good),'success_percent':round(100*len(good)/len(samples),2),
             'http_503':status[503],'other_http_errors':sum(v for k,v in status.items() if k is not None and k>=400 and k!=503),
             'client_errors':sum(bool(s['error']) for s in samples),
             'successful_burst_rps':round(len(good)/sum(r['seconds'] for r in runs),2),
             'success_p50_ms':quantile([s['latency_ms'] for s in good],.5),
             'success_p95_ms':quantile([s['latency_ms'] for s in good],.95),
             'success_p99_ms':quantile([s['latency_ms'] for s in good],.99),
             'connect_p95_ms':quantile([s['connect_ms'] for s in samples if 'connect_ms' in s],.95),
             'success_ttfb_p95_ms':quantile([s['ttfb_ms'] for s in good],.95),
             'client_peak_connected':max(r['peak_client_connected'] for r in runs),
             'client_launch_p95_ms':quantile([s['queue_ms'] for s in samples],.95),
             'max_run_client_lag_p99_ms':max(r['client_event_loop_lag_p99_ms'] or 0 for r in runs),
             'server_peak_rss_mib':round(resources['peak_rss_kib']/1024,1),
             'server_peak_admitted_observed':counters['peak_admitted_observed']}
        rows.append(row)
    with (directory/'summary.csv').open('w') as output:
        writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (directory/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    lines=['# Spin burst-load results','',
           'Each row pools three bursts unless the repeats column in summary.csv says otherwise. Latency percentiles contain successful, validated 200 responses only. Successful burst requests/s divides total successes by total burst wall time; it is not a sustained throughput measurement.','',
           '| Concurrent attempts | Actor limit | Mode | Success % | 503 | Client errors | Success req/s | p50 ms | p95 ms | p99 ms | Peak RSS MiB |',
           '| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append('| '+' | '.join(str(r[k]) for k in ['concurrency','actor_limit','mode','success_percent','http_503','client_errors','successful_burst_rps','success_p50_ms','success_p95_ms','success_p99_ms','server_peak_rss_mib'])+' |')
    lines+=['','See metadata.json for compiler pins, platform, JVM options, and harness hashes. See summary.csv for connection timing, event-loop lag, and observed simultaneous client connections. Per-request samples, server counters, stderr, and memory samples are retained alongside this report.','']
    (directory/'REPORT.md').write_text('\n'.join(lines))

if __name__=='__main__':main()
