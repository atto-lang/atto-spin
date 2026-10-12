#!/usr/bin/env python3
"""Spawn real Oreslang Spin, then perform sustained full-response measurements."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from importlib.machinery import SourceFileLoader
client=SourceFileLoader("sustained_client",str(ROOT/"scripts/sustained-client.py")).load_module()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--concurrency",default="100,1000,10000")
    p.add_argument("--modes",nargs="+",choices=["shared","isolated"],default=["shared","isolated"])
    p.add_argument("--duration",type=int,default=180)
    p.add_argument("--pool-size",type=int,default=128)
    p.add_argument("--capacity",type=int,default=10000)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    concurrency=[int(x) for x in a.concurrency.split(",")]
    if a.duration<1 or any(n<1 or n>10000 for n in concurrency) or not 1<=a.pool_size<=4096 or not 1<=a.capacity<=65536:
        p.error("invalid duration, concurrency, pool-size, or capacity")
    a.out.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ)
    env["JAVA_TOOL_OPTIONS"]=env.get("JAVA_TOOL_OPTIONS","")+" -Xms256m -Xmx3g -Dores.runtime.carriers=java -Djdk.httpserver.maxConnections=20000"
    source=Path(env["ORESLANG_SOURCE_DIR"])
    expected=(ROOT/"SOURCE_REF").read_text().strip()
    sha=lambda path:subprocess.check_output(["git","-C",str(path),"rev-parse","HEAD"],text=True).strip()
    assert sha(source)==expected, "compiler pin mismatch"
    assert not subprocess.check_output(["git","-C",str(source),"status","--porcelain"],text=True).strip(), "dirty compiler source"
    router=ROOT/"dependencies/http-routing"
    expected_router=subprocess.check_output(["git","-C",str(ROOT),"ls-files","--stage","dependencies/http-routing"],text=True).split()[1]
    assert sha(router)==expected_router, "router pin mismatch"
    assert not subprocess.check_output(["git","-C",str(router),"status","--porcelain"],text=True).strip(), "dirty router"
    metadata=dict(spin_commit=sha(ROOT),java_source_commit=sha(source),router_commit=sha(router),
        client_sha256=hashlib.sha256((ROOT/"scripts/sustained-client.py").read_bytes()).hexdigest(),
        fixture_sha256=hashlib.sha256((ROOT/"tests/pooled-load-server.ores").read_bytes()).hexdigest(),
        options=vars(a)|{"out":str(a.out)},java_options=env["JAVA_TOOL_OPTIONS"],
        note="JVM loopback single host; persistent HTTP/1.1; closed-loop; no retries; no claims of native/LLVM throughput")
    (a.out/"metadata.json").write_text(json.dumps(metadata,indent=2)+"\n")
    lines=queue.Queue()
    stdout=[]
    for conc in concurrency:
        for mode in a.modes:
            fixture=(ROOT/"tests/pooled-load-server.ores").read_text()
            fixture=fixture.replace("/* BENCHMARK_CAPACITY */ 300",str(a.capacity)).replace("/* POOL_SIZE */ 128",str(a.pool_size))
            with tempfile.NamedTemporaryFile(mode="w",prefix="sustained-",suffix=".ores",dir=ROOT/"tests",delete=False) as tmp:
                tmp.write(fixture)
                generated=Path(tmp.name)
            proc=None
            tag=f"c{conc}-{mode}-w{a.pool_size}"
            try:
                with (a.out/(tag+".stderr.log")).open("w") as stderr:
                    proc=subprocess.Popen([str(ROOT/"scripts/compiler.sh"),"--platform=server","--allow-net=127.0.0.1:0",str(generated)],cwd=ROOT,env=env,
                                          stdout=subprocess.PIPE,stderr=stderr,text=True,bufsize=1)
                    output=[]
                    def read_stdout():
                        for line in proc.stdout:
                            output.append(line.strip())
                            lines.put(line.strip())
                    thread=threading.Thread(target=read_stdout,daemon=True)
                    thread.start()
                    port=int(lines.get(timeout=90))
                    async def run():
                        import asyncio
                        # Small warmup on an independent keep-alive connection.
                        result=await client.sustained("127.0.0.1",port,"/"+mode,mode,conc,a.duration)
                        (a.out/(tag+".json")).write_text(json.dumps(result,indent=2)+"\n")
                        print(json.dumps(result),flush=True)
                        reader,writer=await asyncio.open_connection("127.0.0.1",port)
                        writer.write(b"GET /__stop HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
                        await writer.drain()
                        await reader.read()
                        writer.close()
                        await writer.wait_closed()
                    asyncio.run(run())
                    proc.wait(timeout=30);thread.join(timeout=2)
                    (a.out/(tag+".stdout.log")).write_text("\n".join(output)+"\n")
                    if proc.returncode: raise RuntimeError(f"server {tag} exited {proc.returncode}")
                    ix=output.index("POOLED_ACTOR_COUNTERS")
                    actor_numbers=[int(v) for v in output[ix+1:ix+5]]
                    jx=output.index("SERVER_COUNTERS")
                    server_numbers=[int(v) for v in output[jx+1:jx+6]]
                    runtime=dict(actors_created_shared=actor_numbers[0],dispatches_shared=actor_numbers[1],
                        actors_created_isolated=actor_numbers[2],dispatches_isolated=actor_numbers[3],
                        accepted=server_numbers[0],rejected=server_numbers[1],completed=server_numbers[2],
                        active_after_shutdown=server_numbers[3],peak_active=server_numbers[4])
                    (a.out/(tag+".runtime.json")).write_text(json.dumps(runtime,indent=2)+"\n")
                    print(json.dumps(dict(tag=tag,runtime=runtime)),flush=True)
                    assert runtime["active_after_shutdown"]==0 and runtime["rejected"]==0, "admission rejection/drain failure"
                    assert runtime["actors_created_"+mode] <= a.pool_size, "pool unexpectedly grew"
                    assert runtime["dispatches_"+mode]>runtime["actors_created_"+mode], "no actor reuse proved"
            finally:
                generated.unlink(missing_ok=True)
                if proc and proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
if __name__=="__main__":main()
