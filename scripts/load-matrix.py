#!/usr/bin/env python3
"""Loopback burst overload matrix: fresh actors, bounded exchange admission, no retries."""
import argparse
import asyncio
from collections import Counter
import json
import hashlib
import math
import os
from pathlib import Path
import platform
import queue
import resource
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]

def percentile(values, p):
    if not values: return None
    values = sorted(values)
    return round(values[max(0, math.ceil(len(values)*p)-1)], 3)

def distribution(values):
    return {'mean_ms': round(sum(values)/len(values), 3) if values else None,
            **{f'p{int(p*100)}_ms': percentile(values,p) for p in (.5,.95,.99)}}

async def exchange(port, path, mode, timeout, metrics, gate=None, release=None):
    if gate: await gate.wait()
    start=time.perf_counter()
    writer=None
    connected=False
    sample={'status':None, 'error':None, 'queue_ms':(start-release[0])*1000 if release else 0}
    async def execute():
        nonlocal writer,connected
        reader,writer=await asyncio.open_connection('127.0.0.1',port)
        connected=True
        metrics['connected']+=1
        metrics['peak_connected']=max(metrics['peak_connected'],metrics['connected'])
        sample['connect_ms']=(time.perf_counter()-start)*1000
        writer.write(f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n'.encode())
        await writer.drain()
        head=await reader.readuntil(b'\r\n\r\n')
        sample['ttfb_ms']=(time.perf_counter()-start)*1000
        lines=head.decode('iso-8859-1').split('\r\n')
        sample['status']=int(lines[0].split()[1])
        headers={k.lower():v.strip() for k,v in (line.split(':',1) for line in lines[1:] if ':' in line)}
        # All requests explicitly ask for closure. EOF includes body completion.
        body=await reader.read()
        if sample['status']==200 and mode:
            if body!=b'ok\n' or headers.get('x-actor-mode')!=mode:
                raise ValueError('incorrect response body or actor mode')
            sample['timing']={part.strip().split(';dur=')[0]:float(part.split(';dur=')[1])
                              for part in headers.get('server-timing','').split(',') if ';dur=' in part}
    try:
        await asyncio.wait_for(execute(),timeout)
    except Exception as error:
        sample['error']=type(error).__name__+': '+str(error)[:160]
    finally:
        sample['latency_ms']=(time.perf_counter()-start)*1000
        sample['burst_latency_ms']=(time.perf_counter()-release[0])*1000 if release else sample['latency_ms']
        if writer:
            writer.close()
            try: await asyncio.wait_for(writer.wait_closed(),1)
            except Exception: pass
        if connected: metrics['connected']-=1
    return sample

async def burst(port, mode, concurrency, timeout):
    metrics={'connected':0,'peak_connected':0}
    gate=asyncio.Event();release=[0.0];lags=[];stop=False
    async def lag_probe():
        while not stop:
            start=time.perf_counter()
            await asyncio.sleep(.01)
            lags.append(max(0,(time.perf_counter()-start-.01)*1000))
    tasks=[asyncio.create_task(exchange(port,'/'+mode,mode,timeout,metrics,gate,release)) for _ in range(concurrency)]
    await asyncio.sleep(0)
    probe=asyncio.create_task(lag_probe())
    release[0]=time.perf_counter();gate.set()
    try:
        samples=await asyncio.gather(*tasks)
        elapsed=time.perf_counter()-release[0]
    finally:
        stop=True
        await probe
    good=[s for s in samples if s['status']==200 and not s['error']]
    result={'concurrency':concurrency,'attempts':len(samples),'seconds':round(elapsed,4),
            'successes':len(good),'status_counts':dict(Counter(str(s['status']) for s in samples)),
            'errors':dict(Counter(s['error'] for s in samples if s['error'])), 'retries':0,
            'success_rps':round(len(good)/elapsed,2),'attempts_rps':round(len(samples)/elapsed,2),
            'success_latency':distribution([s['latency_ms'] for s in good]),
            'all_latency':distribution([s['latency_ms'] for s in samples]),
            'success_burst_latency':distribution([s['burst_latency_ms'] for s in good]),
            'connect_latency':distribution([s['connect_ms'] for s in samples if 'connect_ms' in s]),
            'success_ttfb':distribution([s['ttfb_ms'] for s in good]),
            'client_launch_delay':distribution([s['queue_ms'] for s in samples]),
            'client_event_loop_lag_p99_ms':percentile(lags,.99),
            'peak_client_connected':metrics['peak_connected'],
            'actor_startup':distribution([s['timing']['actor-startup'] for s in good if 'actor-startup' in s.get('timing',{})]),
            'move_to_claim':distribution([s['timing']['move-to-claim'] for s in good if 'move-to-claim' in s.get('timing',{})])}
    return result,samples

def integers(value):
    result=[int(x) for x in value.split(',')]
    if not result or any(x<1 or x>10000 for x in result): raise argparse.ArgumentTypeError('use comma-separated integers 1..10000')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concurrency',type=integers,default=[100,1000,10000])
    parser.add_argument('--actors',type=integers,default=[5,20,50,300])
    parser.add_argument('--modes',nargs='+',choices=['shared','isolated'],default=['shared','isolated'])
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--timeout',type=float,default=20)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.repeats<1 or args.timeout<=0: parser.error('positive repeats and timeout required')
    args.output.mkdir(parents=True,exist_ok=False)
    source=Path(os.environ['ORESLANG_SOURCE_DIR']).resolve()
    # Reuse the pinned provenance validation, without pretending this is a full semantic check.
    import runpy
    checker=runpy.run_path(str(ROOT/'scripts/check-backend.py'))
    checker['require_source']('ORESLANG_SOURCE_DIR','SOURCE_REF')
    router=ROOT/'dependencies/http-routing'
    git=lambda p,*a: subprocess.check_output(['git','-C',str(p),*a],text=True).strip()
    if git(router,'status','--porcelain') or git(router,'rev-parse','HEAD')!=git(ROOT,'ls-files','--stage','dependencies/http-routing').split()[1]:
        raise RuntimeError('Router must be clean and match gitlink')
    env=dict(os.environ)
    env['JAVA_TOOL_OPTIONS']=env.get('JAVA_TOOL_OPTIONS','')+' -Xms256m -Xmx2g -Dores.runtime.carriers=java -Djdk.httpserver.maxConnections=20000'
    metadata={'spin_commit':git(ROOT,'rev-parse','HEAD'),'spin_dirty':bool(git(ROOT,'status','--porcelain')),
              'java_source_commit':git(source,'rev-parse','HEAD'),'router_commit':git(router,'rev-parse','HEAD'),
              'benchmark_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'fixture_sha256':hashlib.sha256((ROOT/'tests/load-server.ores').read_bytes()).hexdigest(),
              'platform':platform.platform(),'cpus':os.cpu_count(),'fd_limit':resource.getrlimit(resource.RLIMIT_NOFILE),
              'java_tool_options':env['JAVA_TOOL_OPTIONS'],'java_version':subprocess.run([env.get('ORES_JAVA','java'),'-version'],capture_output=True,text=True).stderr,
              'scope':'JVM interpreter; loopback single-client-process simultaneous one-request-per-task bursts; new TCP connections; no retries; actor limit is HTTP in-flight admission, not a reusable pool; backlog equals admission limit',
              'configuration':{k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()}}
    (args.output/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    for concurrency in args.concurrency:
        for actors in args.actors:
            for mode in args.modes:
                tag=f'c{concurrency}-a{actors}-{mode}'
                template=(ROOT/'tests/load-server.ores').read_text().replace('/* BENCHMARK_CAPACITY */ 300',str(actors))
                descriptor,filename=tempfile.mkstemp(prefix='load-generated-',suffix='.ores',dir=ROOT/'tests')
                os.close(descriptor);Path(filename).write_text(template)
                lines=queue.Queue();captured=[];resources=[];monitor_stop=threading.Event()
                stderr=(args.output/(tag+'.stderr.log')).open('w')
                server=None
                try:
                    server=subprocess.Popen([str(ROOT/'scripts/compiler.sh'),'--platform=server','--allow-net=127.0.0.1:0',filename],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=stderr,text=True)
                    def reader():
                        for line in server.stdout:
                            captured.append(line.strip());lines.put(line.strip())
                    thread=threading.Thread(target=reader,daemon=True);thread.start()
                    def monitor():
                        while not monitor_stop.wait(.25):
                            r=subprocess.run(['ps','-o','rss=,%cpu=','-p',str(server.pid)],capture_output=True,text=True)
                            if r.returncode==0 and r.stdout.strip():
                                rss,cpu=r.stdout.split();resources.append((int(rss),float(cpu)))
                    watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
                    port=int(lines.get(timeout=30))
                    async def run():
                        m={'connected':0,'peak_connected':0}
                        for _ in range(50):
                            s=await exchange(port,'/'+mode,mode,args.timeout,m)
                            if s['status']!=200 or s['error']:raise RuntimeError('Warm-up failed: '+str(s))
                        for repeat in range(args.repeats):
                            await asyncio.sleep(.5)
                            result,samples=await burst(port,mode,concurrency,args.timeout)
                            result.update(actor_limit=actors,mode=mode,repeat=repeat+1)
                            with (args.output/'results.jsonl').open('a') as out: out.write(json.dumps(result)+'\n')
                            (args.output/f'{tag}-r{repeat+1}.samples.json').write_text(json.dumps(samples)+'\n')
                            print(json.dumps(result),flush=True)
                        await asyncio.sleep(1)
                        stop=await exchange(port,'/__stop',None,args.timeout,m)
                        if stop['status']!=200 or stop['error']:raise RuntimeError('Shutdown request failed: '+str(stop))
                    asyncio.run(run())
                    server.wait(timeout=15);thread.join(timeout=2)
                    if server.returncode: raise RuntimeError(f'Server exited {server.returncode}')
                    index=captured.index('SERVER_COUNTERS')
                    counters=dict(zip(['accepted','rejected','completed','active_after_shutdown','peak_admitted_observed'],map(int,captured[index+1:index+6])))
                    counters['scope']='all repeats plus 50 warm-ups and one shutdown request'
                    (args.output/(tag+'.server.json')).write_text(json.dumps(counters,indent=2)+'\n')
                finally:
                    if server is not None and server.poll() is None:
                        server.terminate()
                        try:server.wait(timeout=5)
                        except subprocess.TimeoutExpired:server.kill();server.wait()
                    monitor_stop.set()
                    if server is not None: watcher.join(timeout=2)
                    stderr.close();Path(filename).unlink(missing_ok=True)
                    (args.output/(tag+'.stdout.log')).write_text('\n'.join(captured)+'\n')
                    (args.output/(tag+'.resources.json')).write_text(json.dumps({'peak_rss_kib':max((r[0] for r in resources),default=0),'peak_ps_cpu_percent':max((r[1] for r in resources),default=0),'samples':resources})+'\n')

if __name__=='__main__': main()
