#!/usr/bin/env python3
"""Run one 35s Spin comparison cell (fresh or reusable actor) with evidence.

Requires a built, clean Oreslang Java core at POOL_SOURCE_REF and a pinned
http-routing submodule. This tool does not disguise a failed workload as 100%.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import queue
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "sustained-client.py"
spec = importlib.util.spec_from_file_location("sustained_client", MODULE)
load = importlib.util.module_from_spec(spec)
spec.loader.exec_module(load)

def git(repo, *cmd):
    return subprocess.check_output(["git", "-C", str(repo), *cmd], text=True).strip()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, choices=(100,1000,10000), required=True)
    parser.add_argument("--strategy", choices=("fresh","pooled"), required=True)
    parser.add_argument("--mode", choices=("shared","isolated"), required=True)
    parser.add_argument("--duration", type=float, default=35)
    parser.add_argument("--pool-workers", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.duration <= 0 or args.timeout <= 0: parser.error("duration and timeout must be positive")
    args.pool_workers = args.pool_workers or args.concurrency
    if not 1 <= args.pool_workers <= 10000: parser.error("pool workers must be 1..10000")
    source = Path(os.environ["ORESLANG_SOURCE_DIR"]).resolve()
    pin = (ROOT/"POOL_SOURCE_REF").read_text().strip()
    if git(source, "rev-parse", "HEAD") != pin or git(source, "status", "--porcelain"):
        parser.error("Java core checkout must be clean and match POOL_SOURCE_REF")
    router = ROOT/"dependencies/http-routing"
    if git(router, "status", "--porcelain") or git(router,"rev-parse","HEAD") != git(ROOT, "ls-files", "--stage", "dependencies/http-routing").split()[1]:
        parser.error("HTTP router checkout must match Spin's pinned gitlink")
    if args.output.exists(): parser.error("output path must not already exist")
    args.output.mkdir(parents=True)
    body = (ROOT/"tests/sustained-pool-server.ores").read_text()
    body = body.replace("/* BENCHMARK_POOL */ 100",str(args.pool_workers))
    # Keep capacity independent of pool workers; 10,000 closed-loop clients
    # require at least 10,000 slots to avoid deliberate admission rejection.
    body = body.replace("/* BENCHMARK_ADMISSION */ 10000",str(max(10000,args.concurrency)))
    filename=None
    logs=[]
    initial_dirty=bool(git(ROOT,"status","--porcelain"))
    stderr=None
    server=None
    try:
        handle,filename=tempfile.mkstemp(prefix="spin-sustained-",suffix=".ores",dir=ROOT/"tests")
        os.close(handle)
        Path(filename).write_text(body)
        env=dict(os.environ)
        env["JAVA_TOOL_OPTIONS"]=env.get("JAVA_TOOL_OPTIONS","") + " -Xms256m -Xmx4g -Dores.runtime.carriers=java -Djdk.httpserver.maxConnections=25000"
        stderr=(args.output/"server.stderr.log").open("w")
        server=subprocess.Popen([str(ROOT/"scripts/compiler.sh"),"--platform=server","--allow-net=127.0.0.1:0",filename],
            cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=stderr,text=True)
        lines=queue.Queue()
        def read_lines():
            for line in server.stdout:
                logs.append(line.rstrip("\n"))
                lines.put(line.rstrip("\n"))
        thread=threading.Thread(target=read_lines,daemon=True)
        thread.start()
        port=int(lines.get(timeout=120))
        async def execute():
            path=f"/{args.strategy}/{args.mode}"
            async def single(route,mode):
                reader,writer=await asyncio.wait_for(asyncio.open_connection("127.0.0.1",port),args.timeout)
                try:
                    return await load.one(reader,writer,"127.0.0.1",route,mode,args.timeout)
                finally:
                    writer.close()
                    try: await writer.wait_closed()
                    except Exception: pass
            for index in range(100):
                sample=await single(path,args.mode)
                if sample[1] != 200 or not sample[2]:
                    raise RuntimeError(f"Warmup request {index} failed: {sample}")
            options=argparse.Namespace(host="127.0.0.1",port=port,path=path,mode=args.mode,
                                        concurrency=args.concurrency,duration=args.duration,timeout=args.timeout)
            result=await load.benchmark(options)
            # Stop is a separate request, excluded from measured attempts.
            stop=await single("/__stop",None)
            if stop[1]!=200:
                raise RuntimeError("server shutdown request failed: "+str(stop))
            return result
        result=asyncio.run(execute())
        server.wait(timeout=30)
        thread.join(timeout=2)
        if server.returncode: raise RuntimeError(f"server exited {server.returncode}")
        i=logs.index("POOL_COUNTERS")
        names=("shared_created","shared_reused","isolated_created","isolated_reused",
               "accepted","completed","rejected","active")
        counters=dict(zip(names,map(int,logs[i+1:i+9])))
        record=dict(result, strategy=args.strategy, pool_workers=args.pool_workers,
                    java_commit=pin, spin_head=git(ROOT,"rev-parse","HEAD"),
                    spin_dirty=initial_dirty,
                    router_commit=git(router,"rev-parse","HEAD"),
                    host=platform.platform(),cpu_count=os.cpu_count(),
                    fixture_sha256=hashlib.sha256(body.encode()).hexdigest(),
                    client_sha256=hashlib.sha256(MODULE.read_bytes()).hexdigest(),
                    server_counters=counters)
        args.output.joinpath("results.json").write_text(json.dumps(record,indent=2)+"\n")
        print(json.dumps(record,indent=2),flush=True)
        assert counters["active"] == 0, "server leaked active exchanges"
        assert counters["rejected"] == 0, "admission rejections are not successful requests"
        assert counters["accepted"] == counters["completed"], "server did not complete all accepted requests"
        assert result["attempts"] == result["successes"], "not all client requests succeeded"
        if args.strategy == "pooled":
            prefix="shared" if args.mode=="shared" else "isolated"
            assert counters[prefix+"_created"] > 0
            assert counters[prefix+"_created"] < result["successes"]
            assert counters[prefix+"_reused"] > 0, "no successful actor reuse observed"
    finally:
        if server and server.poll() is None:
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill();server.wait()
        if stderr: stderr.close()
        if filename: Path(filename).unlink(missing_ok=True)
        (args.output/"server.stdout.log").write_text("\n".join(logs)+"\n")

if __name__ == "__main__":
    main()
