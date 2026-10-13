#!/usr/bin/env python3
"""Combine sustained pooled-worker runs; validate success, drain, and worker reuse."""
import argparse
import csv
import json
from pathlib import Path
import statistics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    rows=[];total=0
    for directory in args.runs:
        result=json.loads((directory/'result.json').read_text())
        counters=json.loads((directory/'server.json').read_text())
        resources=json.loads((directory/'resources.json').read_text())
        if result['failures'] or result['retries'] or counters['rejected'] or counters['active'] or counters['accepted']!=counters['completed']:
            raise RuntimeError('Failure/drain validation failed: '+str(directory))
        expected=counters['accepted']-1
        actual=sum(m['warmup_requests']+m['requests_started_in_window'] for m in result['modes'].values())
        if expected!=actual:raise RuntimeError('Client/server count mismatch: '+str(directory))
        for mode,data in result['modes'].items():
            if data['distinct_workers_with_warmup']!=32 or data['reused_responses']!=data['requests_started_in_window']:
                raise RuntimeError('Worker reuse verification failed: '+str(directory))
            total+=data['requests_started_in_window']
            rows.append({'total_concurrency':result['concurrency'],'clients_per_mode':result['concurrency']//2,
                         'mode':mode,'seconds':result['measurement_seconds'],'requests':data['requests_started_in_window'],
                         'mean_ms':data['mean_ms'],'p50_ms':data['p50_ms'],'p95_ms':data['p95_ms'],'p99_ms':data['p99_ms'],
                         'completed_rps':data['completed_rps'],'workers':data['distinct_workers_observed'],
                         'reused_responses':data['reused_responses'],
                         'server_peak_rss_mib':round(max(r['rss_kib'] for r in resources)/1024,1),
                         'server_first30_median_rss_mib':round(statistics.median(r['rss_kib'] for r in resources[10:40])/1024,1),
                         'server_last30_median_rss_mib':round(statistics.median(r['rss_kib'] for r in resources[-30:])/1024,1),
                         'client_lag_p99_ms':result['client_event_loop_lag_p99_ms'],'drain_seconds':result['drain_seconds']})
    (args.output/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    with (args.output/'summary.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# Reusable actors: sustained HTTP load','',f'**{total:,} measured responses succeeded.** Zero errors, admission rejections, or retries. Each run used 32 shared and 32 isolated workers; stable worker IDs and reuse headers verified reuse for every measured response. All servers completed every admitted request and drained to zero active exchanges.','',
           '| Total concurrent clients | Mode | Seconds | Responses | Mean ms | p95 ms | p99 ms | Completed req/s |',
           '| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:lines.append('| '+' | '.join(str(r[k]) for k in ['total_concurrency','mode','seconds','requests','mean_ms','p95_ms','p99_ms','completed_rps'])+' |')
    lines+=['','Each concurrency is a **mixed run**: half the keep-alive connections target each mode. Rates in the table are per mode; sum them for total throughput. Ten-second warm-up and TCP setup are excluded. Latencies cover requests started within the 180-second window, including their final drain; rate counts only measured requests completed inside the window.','',
            'The workload continually replaces each completed request on the same connection. This is closed-loop load, not an open-loop arrival-rate/SLA experiment. Client and server share the local macOS host; the server uses the JVM interpreter and Java carriers. No LLVM/native-image or physical isolation claim is made.','',
            'Do not attribute differences from the earlier short bursts solely to actor reuse: connection reuse, warm-up, and workload shape also changed. See summary.csv for RSS, client scheduling lag, and drain time. Raw result/metadata, numeric latency samples, progress logs, resource samples, and server counters remain in the individual run directories.','']
    (args.output/'REPORT.md').write_text('\n'.join(lines))
    print('\n'.join(lines))

if __name__=='__main__':main()
