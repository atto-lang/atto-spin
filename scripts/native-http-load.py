#!/usr/bin/env python3
"""Exploratory native Oreslang HTTP/1.1 transport load, NOT actor-routing parity."""
import argparse
import asyncio
from array import array
from collections import Counter
import json
import math
import os
from pathlib import Path
import queue
import resource
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
CORE = Path(os.environ.get("ORESLANG_SOURCE_DIR", ROOT / "../oreslang-java-mirror")).resolve()
MAX_HEADER = 8192

def try_raise_nofile():
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(hard, 65535), hard))
    except (OSError, ValueError):
        pass
    return resource.getrlimit(resource.RLIMIT_NOFILE)[0]

def proc_cpu_ticks(pid):
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
        fields = text.rsplit(")", 1)[1].strip().split()
        return int(fields[11]) + int(fields[12])
    except (OSError, ValueError, IndexError):
        return None

def proc_rss_kb(pid):
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return None

class Hist:
    def __init__(self):
        self.buckets = array("I", [0]) * 300001
        self.count = 0
        self.sum_ms = 0.0
    def add(self, ms):
        self.buckets[min(300000, max(0, int(ms * 10)))] += 1
        self.count += 1
        self.sum_ms += ms
    def stats(self):
        thresholds = ((50,.50),(95,.95),(99,.99))
        found = {}
        n = 0
        for i, count in enumerate(self.buckets):
            n += count
            for label, fraction in thresholds:
                if label not in found and n >= math.ceil(self.count*fraction):
                    found[label] = round(i / 10, 2)
            if len(found) == 3:
                break
        return {"count":self.count,"mean_ms":round(self.sum_ms/self.count,3) if self.count else None,
                **{f"p{q}_ms":found.get(q) for q,_ in thresholds}}

async def response(reader):
    head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 20)
    if len(head) > MAX_HEADER:
        raise ValueError("oversized response head")
    lines = head[:-4].split(b"\r\n")
    status = int(lines[0].split()[1])
    headers = {}
    for line in lines[1:]:
        k,sep,v = line.partition(b":")
        if not sep: raise ValueError("invalid response header")
        key=k.lower().strip()
        if key in headers:raise ValueError("duplicate response header")
        headers[key]=v.strip()
    if b"content-length" not in headers: raise ValueError("missing body framing")
    length = int(headers[b"content-length"])
    if length < 0 or length > 4096: raise ValueError("invalid content length")
    body = await asyncio.wait_for(reader.readexactly(length),20)
    return status, headers, body

async def drive(port, count, warmup, duration, pid):
    histogram = Hist()
    errors = Counter()
    attempts = 0
    done = 0
    connected = 0
    gate = asyncio.Event()
    sem = asyncio.Semaphore(256)
    close_deadline = 0.0
    warm_end = 0.0
    last = 0.0
    request = b"GET /shared HTTP/1.1\r\nHost: localhost\r\nConnection: keep-alive\r\n\r\n"
    ending = b"GET /shared HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
    rss_peak = 0

    async def user():
        nonlocal attempts,done,connected
        reader=writer=None
        try:
            async with sem:
                reader,writer=await asyncio.wait_for(asyncio.open_connection("127.0.0.1",port),20)
                connected+=1
            await gate.wait()
            while time.perf_counter() < close_deadline:
                start = time.perf_counter()
                measured = start >= warm_end
                if measured: attempts+=1
                writer.write(request)
                await asyncio.wait_for(writer.drain(),20)
                status,headers,body=await response(reader)
                if status != 200 or body != b"ok\n":
                    errors["invalid_response"]+=1
                    break
                if measured:
                    histogram.add((time.perf_counter()-start)*1000)
                    done+=1
            writer.write(ending)
            await asyncio.wait_for(writer.drain(),20)
            status,headers,body=await response(reader)
            if status != 200 or body != b"ok\n":
                errors["invalid_close_response"]+=1
        except Exception as exc:
            errors[type(exc).__name__]+=1
        finally:
            if writer is not None:
                writer.close()
                try: await asyncio.wait_for(writer.wait_closed(),2)
                except Exception: pass

    tasks=[asyncio.create_task(user()) for _ in range(count)]
    connection_deadline=time.perf_counter()+max(90,count/60)
    while connected + sum(t.done() for t in tasks)<count and time.perf_counter()<connection_deadline:
        await asyncio.sleep(.2)
    ready=connected
    start_cpu=proc_cpu_ticks(pid)
    start=time.perf_counter()
    warm_end=start+warmup
    close_deadline=warm_end+duration
    gate.set()
    try:
        await asyncio.wait_for(asyncio.gather(*tasks),warmup+duration+70)
    except asyncio.TimeoutError:
        errors["unfinished_clients"]+=sum(not t.done() for t in tasks)
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
    end_cpu=proc_cpu_ticks(pid)
    rss=proc_rss_kb(pid)
    hz=os.sysconf("SC_CLK_TCK")
    return {"concurrency":count,"warmup_s":warmup,"duration_s":duration,
            "connections_at_start":ready,"connections_requested":count,
            "attempted_measured":attempts,"successful_measured":done,
            "success_percent":round(100*done/attempts,2) if attempts else None,
            "rps":round(done/duration,2),"errors":dict(errors),
            "latency":histogram.stats(),
            "server_cpu_core_equivalents":round((end_cpu-start_cpu)/hz/(time.perf_counter()-start),3)
                if start_cpu is not None and end_cpu is not None else None,
            "server_rss_kb_end":rss,
            "workload":"persistent HTTP/1.1 closed loop; GET /shared body ok\\n; no actor dispatch"}

def run(count, duration, warmup):
    template=(ROOT/"tests/native-http-load.ores").read_text()
    fixed="/* CLIENTS */ 100"
    if fixed not in template:raise ValueError("missing source concurrency marker")
    guest=ROOT/"tests/native-http-load.generated.ores"
    guest.write_text(template.replace(fixed,str(count)))
    cp=(CORE/"target/classpath.txt").read_text().strip()
    cmd=["java","--enable-native-access=ALL-UNNAMED",
         "-Dpolyglot.engine.WarnInterpreterOnly=false",
         "-Xms256m","-Xmx3g","-cp",str(CORE/"target/classes")+":"+cp,
         "dev.oreslang.launcher.OresMain","--platform=server",
         "--allow-net=127.0.0.1:0",str(guest)]
    outputs=queue.Queue()
    all_stdout=[]
    p=None
    try:
        with (ROOT/f"native-http-load-c{count}.stderr.log").open("w") as stderr:
            p=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,
                               stderr=stderr,text=True,bufsize=1)
            def drain():
                for line in p.stdout:
                    all_stdout.append(line.strip())
                    outputs.put(line.strip())
            thread=threading.Thread(target=drain,daemon=True)
            thread.start()
            deadline=time.monotonic()+60
            port=None
            while time.monotonic()<deadline:
                try:
                    line=outputs.get(timeout=.5)
                    if line.isdigit(): port=int(line);break
                except queue.Empty:
                    if p.poll() is not None:break
            if port is None:raise RuntimeError("server failed to announce TCP port; stderr log saved")
            result=asyncio.run(drive(port,count,warmup,duration,p.pid))
            try: p.wait(timeout=90)
            except subprocess.TimeoutExpired:
                result["server_shutdown_timeout"]=True
            if p.poll() is None:
                p.kill();p.wait(timeout=5)
            thread.join(timeout=2)
            result["server_exit_code"]=p.returncode
            if "NATIVE_IO_METRICS" in all_stdout:
                ix=all_stdout.index("NATIVE_IO_METRICS")
                try:
                    result["peak_outstanding_futures"]=int(all_stdout[ix+1])
                    result["max_nio_command_queue_wait_ns"]=int(all_stdout[ix+2])
                except (IndexError,ValueError):pass
            return result
    finally:
        guest.unlink(missing_ok=True)
        if p is not None and p.poll() is None:
            p.kill();p.wait(timeout=5)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--concurrency",default="100,1000,10000")
    p.add_argument("--duration",type=int,default=10)
    p.add_argument("--warmup",type=int,default=2)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    nums=[int(v) for v in args.concurrency.split(",")]
    if not nums or any(n<1 or n>10000 for n in nums):p.error("invalid concurrency")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    limits=try_raise_nofile()
    results=[]
    for n in nums:
        result=run(n,args.duration,args.warmup)
        result["nofile_soft_limit"]=limits
        results.append(result)
        print(json.dumps(result),flush=True)
        args.output.write_text(json.dumps({"source":"Spin opt-in Oreslang native transport", "results":results},indent=2)+"\n")
    if any(x["connections_at_start"]<x["concurrency"] or x["errors"] or x.get("server_exit_code")!=0 for x in results):
        raise RuntimeError("native transport benchmark had incomplete admissions, errors or shutdown")
if __name__=="__main__":main()
