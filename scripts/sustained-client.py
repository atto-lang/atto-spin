#!/usr/bin/env python3
"""Closed-loop, sustained HTTP/1.1 benchmark. Each worker issues sequential requests.

No retries of failed requests. Connection re-establishment between *different*
requests is tracked separately and never counted as successful actor reuse.
"""
import argparse
import asyncio
from collections import Counter
import json
import math
import statistics
import time

def quantile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    return round(values[min(len(values)-1, math.ceil(len(values)*fraction)-1)], 3)

async def one(reader, writer, host, path, expected_mode, timeout):
    start = time.perf_counter()
    writer.write(('GET '+path+' HTTP/1.1\r\nHost: '+host+
                  '\r\nConnection: keep-alive\r\n\r\n').encode('ascii'))
    await asyncio.wait_for(writer.drain(), timeout)
    raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout)
    lines = raw.decode('iso-8859-1').split('\r\n')
    status = int(lines[0].split()[1])
    headers = {}
    for line in lines[1:]:
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.lower()] = value.strip()
    if 'transfer-encoding' in headers:
        raise ValueError('unsupported transfer encoding: '+headers['transfer-encoding'])
    if 'content-length' not in headers:
        raise ValueError('missing Content-Length; cannot delimit reusable HTTP connection')
    length = int(headers['content-length'])
    if length < 0 or length > 1048576:
        raise ValueError('invalid benchmark response length')
    body = await asyncio.wait_for(reader.readexactly(length), timeout)
    valid = (status == 200 and body == b'ok\n' and
             headers.get('x-actor-mode') == expected_mode)
    return (time.perf_counter()-start)*1000, status, valid, headers.get('connection','').lower()

async def benchmark(args):
    deadline = time.monotonic() + args.duration
    ready = asyncio.Event()
    results = {'attempts':0,'successes':0,'status':Counter(),'errors':Counter(),
               'connections':0,'reused_connections':0,'latencies_ms':[]}
    lock = asyncio.Lock()
    async def worker():
        await ready.wait()
        reader = writer = None
        served = 0
        while time.monotonic() < deadline:
            if writer is None:
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(args.host,args.port), args.timeout)
                    results['connections'] += 1
                    served = 0
                except Exception as exc:
                    results['attempts'] += 1
                    results['errors'][type(exc).__name__] += 1
                    await asyncio.sleep(.01)
                    continue
            results['attempts'] += 1
            try:
                elapsed, status, valid, connection = await one(
                    reader,writer,args.host,args.path,args.mode,args.timeout)
                results['status'][str(status)] += 1
                if valid:
                    results['successes'] += 1
                    results['latencies_ms'].append(elapsed)
                    if served: results['reused_connections'] += 1
                else:
                    results['errors']['invalid_response'] += 1
                served += 1
                if connection == 'close':
                    writer.close()
                    try: await writer.wait_closed()
                    except Exception: pass
                    reader = writer = None
            except Exception as exc:
                results['errors'][type(exc).__name__] += 1
                writer.close()
                try: await writer.wait_closed()
                except Exception: pass
                reader = writer = None
        if writer:
            writer.close()
            try: await writer.wait_closed()
            except Exception: pass
    workers = [asyncio.create_task(worker()) for _ in range(args.concurrency)]
    started = time.monotonic()
    ready.set()
    await asyncio.gather(*workers)
    elapsed = time.monotonic()-started
    values=results.pop('latencies_ms')
    results['status']=dict(results['status'])
    results['errors']=dict(results['errors'])
    results.update(duration_requested_s=args.duration,elapsed_s=round(elapsed,3),
                   concurrency=args.concurrency,mode=args.mode,
                   successful_rps=round(results['successes']/elapsed,3),
                   mean_ms=round(statistics.mean(values),3) if values else None,
                   p50_ms=quantile(values,.5),p95_ms=quantile(values,.95),
                   p99_ms=quantile(values,.99),
                   success_rate=round(results['successes']/results['attempts'],6) if results['attempts'] else 0,
                   semantics='closed-loop keepalive HTTP clients; fresh-request actors until runtime pooling is implemented')
    return results

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--path',default=None)
    parser.add_argument('--mode',choices=['shared','isolated'],required=True)
    parser.add_argument('--duration',type=float,default=180)
    parser.add_argument('--concurrency',type=int,required=True)
    parser.add_argument('--timeout',type=float,default=30)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.duration<=0 or args.concurrency<1 or args.timeout<=0:
        parser.error('duration, concurrency and timeout must be positive')
    if args.path is None: args.path='/'+args.mode
    result=asyncio.run(benchmark(args))
    with open(args.output,'w') as out: json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps(result))
    if result['success_rate'] != 1: raise SystemExit(1)

if __name__=='__main__':main()
