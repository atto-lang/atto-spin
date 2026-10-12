#!/usr/bin/env python3
"""Closed-loop sustained HTTP/1.1 load client. No application-level retries."""
import argparse
import asyncio
from array import array
from collections import Counter
import json
import math
import time

class Latencies:
    def __init__(self):
        self.hist = array("I", [0]) * 300001
        self.sum_ms = 0.0
        self.n = 0
        self.over = 0
    def add(self, elapsed_ms):
        self.n += 1
        self.sum_ms += elapsed_ms
        bucket = min(300000, max(0, int(round(elapsed_ms * 10))))
        self.hist[bucket] += 1
        if elapsed_ms > 30000: self.over += 1
    def report(self):
        if not self.n: return dict(count=0, mean_ms=None, p50_ms=None, p95_ms=None, p99_ms=None)
        quantiles = {}
        checkpoints = [(q,math.ceil(self.n*q)) for q in (.5,.95,.99)]
        running = 0
        for idx,count in enumerate(self.hist):
            running += count
            for q,target in checkpoints:
                key = "p"+str(int(q*100))+"_ms"
                if key not in quantiles and running >= target: quantiles[key] = round(idx/10,1)
            if len(quantiles)==3: break
        return dict(count=self.n, mean_ms=round(self.sum_ms/self.n,3), overflow_gt_30s=self.over, **quantiles)

async def read_response(reader):
    head = await reader.readuntil(b"\r\n\r\n")
    status_line,*header_lines = head.decode("iso-8859-1").split("\r\n")
    status = int(status_line.split()[1])
    headers = dict(line.split(":",1) for line in header_lines if ":" in line)
    headers = {k.lower().strip():v.strip() for k,v in headers.items()}
    if "content-length" in headers:
        body = await reader.readexactly(int(headers["content-length"]))
    elif "chunked" in headers.get("transfer-encoding","").lower():
        parts = []
        while True:
            chunk_line = await reader.readline()
            amount = int(chunk_line.split(b";",1)[0],16)
            if amount == 0:
                while await reader.readline() != b"\r\n": pass
                break
            parts.append(await reader.readexactly(amount))
            if await reader.readexactly(2) != b"\r\n": raise ValueError("invalid chunk terminator")
        body = b"".join(parts)
    else:
        raise ValueError("missing HTTP body framing")
    return status,headers,body

async def sustained(host, port, path, mode, concurrency, seconds, timeout=30):
    latencies = Latencies()
    errors = Counter()
    status_counts = Counter()
    start_gate = asyncio.Event()
    ready = 0
    connections = 0
    completed = 0
    started = 0
    deadline = 0.0
    connect_limit = asyncio.Semaphore(256)
    async def worker():
        nonlocal ready,connections,completed,started
        reader = writer = None
        try:
            async with connect_limit:
                reader,writer = await asyncio.wait_for(asyncio.open_connection(host,port),timeout)
                connections += 1
            ready += 1
            await start_gate.wait()
            while time.perf_counter() < deadline:
                since = time.perf_counter()
                started += 1
                try:
                    writer.write(("GET "+path+" HTTP/1.1\r\nHost: "+host+"\r\nConnection: keep-alive\r\n\r\n").encode())
                    await asyncio.wait_for(writer.drain(),timeout)
                    status,headers,body = await asyncio.wait_for(read_response(reader),timeout)
                    elapsed = (time.perf_counter()-since)*1000
                    status_counts[status] += 1
                    if status==200 and body==b"ok\n" and headers.get("x-actor-mode")==mode:
                        latencies.add(elapsed)
                    else:
                        errors["invalid_http_response"] += 1
                    completed += 1
                except Exception as failure:
                    errors[type(failure).__name__] += 1
                    break
        except Exception as failure:
            errors["connection_"+type(failure).__name__] += 1
        finally:
            if writer:
                writer.close()
                try: await asyncio.wait_for(writer.wait_closed(),1)
                except Exception: pass

    tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
    # Warm all connections before starting the measurement window.
    connect_deadline = time.perf_counter() + max(60,concurrency/25)
    while ready + sum(t.done() for t in tasks) < concurrency and time.perf_counter() < connect_deadline:
        await asyncio.sleep(.1)
    launched = ready
    began = time.perf_counter()
    deadline = began + seconds
    start_gate.set()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter()-began
    result = dict(mode=mode, concurrency=concurrency, requested_duration_s=seconds,
        measured_elapsed_s=round(elapsed,3), connections_established=connections,
        connections_at_start=launched, attempted_requests=started, complete_responses=completed,
        responses_per_s=round(completed/elapsed,2), success_responses=latencies.n,
        success_percent=round(100*latencies.n/started,4) if started else None,
        http_statuses=dict(status_counts), failures=dict(errors), retries=0,
        elapsed_ms=latencies.report(), observation="successful HTTP request/response time on persistent TCP connections; connection establishment excluded")
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port",type=int,required=True)
    p.add_argument("--concurrency",type=int,required=True)
    p.add_argument("--mode",choices=["shared","isolated"],required=True)
    p.add_argument("--duration",type=int,default=180)
    args=p.parse_args()
    if not 1<=args.concurrency<=10000 or args.duration<1: p.error("invalid concurrency or duration")
    print(json.dumps(asyncio.run(sustained("127.0.0.1",args.port,"/"+args.mode,args.mode,args.concurrency,args.duration)),sort_keys=True),flush=True)
if __name__=="__main__": main()
