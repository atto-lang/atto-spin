#!/usr/bin/env python3
"""Closed-loop shared/isolated load with pooled or fresh request actors."""
import argparse
import asyncio
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import random
import re
import runpy
import subprocess
import threading
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]

def configure_fixture(source, lifecycle, pool_size):
    if source.count('.pooled(32)') != 2:
        raise ValueError('Expected two handler pool declarations')
    if lifecycle == 'fresh':
        source = source.replace('.pooled(32)', '')
        marker = '    return;\n  }'
        actors = re.compile(r'(define (?:iso)?actor \w+ as\n)(.*?)(\nend)', re.S)
        def end_actor(match):
            body = match.group(2)
            if body.count(marker) != 1:
                raise ValueError('Expected one actor receive ending')
            return match.group(1) + body.replace(marker, '    self.end();\n'+marker) + match.group(3)
        source, count = actors.subn(end_actor, source)
        if count != 2:
            raise ValueError('Expected two actor receive endings')
        return source
    return source.replace('.pooled(32)', f'.pooled({pool_size})')

def percentile(values,p):
    import math
    return round(sorted(values)[max(0,math.ceil(len(values)*p)-1)],3) if values else None

async def response(reader,writer,port,mode,sampled=False):
    start=time.perf_counter()
    profile="X-Profile: yes\r\n" if sampled else ""
    writer.write(f'GET /{mode} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: keep-alive\r\n{profile}\r\n'.encode())
    await writer.drain()
    head=await reader.readuntil(b'\r\n\r\n')
    lines=head.decode('iso-8859-1').split('\r\n')
    status=int(lines[0].split()[1])
    headers={k.lower():v.strip() for k,v in (s.split(':',1) for s in lines[1:] if ':' in s)}
    if 'content-length' not in headers:raise RuntimeError(f'Expected fixed-length response, status={status}')
    body=await reader.readexactly(int(headers['content-length']))
    if status!=200 or body!=b'ok\n' or headers.get('x-actor-mode')!=mode:
        raise RuntimeError(f'Invalid response status={status} body={body!r}')
    identity=headers.get('x-worker')
    if not identity or headers.get('x-reused') not in ('yes','no'):raise RuntimeError('Missing worker reuse evidence')
    return (time.perf_counter()-start)*1000,identity,headers['x-reused']=='yes'

async def measure(port,concurrency,duration,warmup,timeout,output,sample_every=0,actor_mode="mixed",actor_lifecycle="pooled",pool_size=32):
    connected=0;failures=[];start_gate=asyncio.Event();epoch=[0.0];deadline=[0.0]
    latencies={'shared':[],'isolated':[]};identities={'shared':set(),'isolated':set()}
    completed_in_window=Counter();cycle_total=Counter();reused=Counter();all_ids={'shared':set(),'isolated':set()}
    warm=Counter();connection_count=0;lag=[];stop=False;sampler=random.Random(0);sampled_count=0
    async def client(index):
        nonlocal connected,connection_count,sampled_count
        mode=('shared' if index%2==0 else 'isolated') if actor_mode=='mixed' else actor_mode
        writer=None
        try:
            reader,writer=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',port),timeout)
            connection_count+=1;connected+=1
            await start_gate.wait()
            while not stop and time.perf_counter()<deadline[0]:
                submitted=time.perf_counter()
                sampled=bool(sample_every and submitted>=epoch[0] and sampler.randrange(sample_every)==0)
                sampled_count+=sampled
                elapsed,identity,was_reused=await asyncio.wait_for(response(reader,writer,port,mode,sampled),timeout)
                if actor_lifecycle == 'fresh' and (was_reused or identity in all_ids[mode]):
                    raise RuntimeError('Fresh actor identity reused')
                all_ids[mode].add(identity)
                if submitted>=epoch[0]:
                    cycle_total[mode]+=(time.perf_counter()-submitted)*1000
                    latencies[mode].append(elapsed);identities[mode].add(identity)
                    reused[mode]+=was_reused
                    if time.perf_counter()<=deadline[0]:completed_in_window[mode]+=1
                else:warm[mode]+=1
        except Exception as error:
            failures.append({'client':index,'mode':mode,'error':type(error).__name__+': '+str(error)[:180]})
        finally:
            if writer:
                writer.close()
                try:await asyncio.wait_for(writer.wait_closed(),1)
                except Exception:pass
    clients=[asyncio.create_task(client(i)) for i in range(concurrency)]
    connect_start=time.perf_counter()
    while connected<concurrency and not failures:
        if time.perf_counter()-connect_start>timeout:raise TimeoutError('Client connection setup timed out')
        await asyncio.sleep(.01)
    if failures:
        start_gate.set();await asyncio.gather(*clients)
        raise RuntimeError('Connection setup failed: '+str(failures[:3]))
    epoch[0]=time.perf_counter()+warmup;deadline[0]=epoch[0]+duration;start_gate.set()
    async def observe():
        next_report=epoch[0]+30
        while time.perf_counter()<deadline[0] and not failures:
            before=time.perf_counter();await asyncio.sleep(.05)
            if before>=epoch[0]:lag.append(max(0,(time.perf_counter()-before-.05)*1000))
            if time.perf_counter()>=next_report:
                line={'elapsed_seconds':round(time.perf_counter()-epoch[0],1),'completed':sum(len(v) for v in latencies.values()),'errors':len(failures)}
                print(json.dumps(line),flush=True)
                with (output/'progress.jsonl').open('a') as f:f.write(json.dumps(line)+'\n')
                next_report+=30
    observer=asyncio.create_task(observe())
    try:
        await observer
        if failures:stop=True
        await asyncio.gather(*clients)
    finally:
        for task in clients:
            if not task.done():task.cancel()
        await asyncio.gather(*clients,return_exceptions=True)
    end=time.perf_counter();results={}
    for mode,values in latencies.items():
        if actor_mode != "mixed" and mode != actor_mode:continue
        results[mode]={'requests_started_in_window':len(values),'completed_in_window':completed_in_window[mode],
                       'mean_ms':round(sum(values)/len(values),3) if values else None,
                       'client_cycle_mean_ms':round(cycle_total[mode]/len(values),3) if values else None,
                       'p50_ms':percentile(values,.5),'p95_ms':percentile(values,.95),'p99_ms':percentile(values,.99),
                       'completed_rps':round(completed_in_window[mode]/duration,2),
                       'distinct_workers_observed':len(identities[mode]),'distinct_workers_with_warmup':len(all_ids[mode]),
                       'reused_responses':reused[mode],'warmup_requests':warm[mode]}
    # Keep numeric samples, rather than printing every request during measurement.
    (output/'latencies.json').write_text(json.dumps(latencies)+'\n')
    result={'concurrency':concurrency,'actor_mode':actor_mode,'actor_lifecycle':actor_lifecycle,'pool_size':pool_size if actor_lifecycle=='pooled' else None,'measurement_seconds':duration,'warmup_seconds':warmup,
            'drain_seconds':round(max(0,end-deadline[0]),3),'connections_opened':connection_count,
            'retries':0,'profile_schema':2,'sampled_requests':sampled_count,'failures':failures,'modes':results,
            'client_event_loop_lag_p99_ms':percentile(lag,.99),'client_event_loop_lag_max_ms':round(max(lag,default=0),3)}
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    if failures:raise RuntimeError('Sustained test had failures: '+str(failures[:3]))
    if any(not r['requests_started_in_window'] or (actor_lifecycle=='pooled' and (not r['reused_responses'] or r['distinct_workers_with_warmup']>pool_size)) for r in results.values()):
        raise RuntimeError('Missing or invalid actor reuse evidence')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concurrency',type=int,required=True)
    parser.add_argument('--seconds',type=float,default=180)
    parser.add_argument('--warmup',type=float,default=10)
    parser.add_argument('--timeout',type=float,default=60)
    parser.add_argument('--sample-every',type=int,default=0,help='Sample warm requests with probability 1/N (fixed random seed); enables Oreslang telemetry fixture')
    parser.add_argument('--actor-mode',choices=['mixed','shared','isolated'],default='mixed')
    parser.add_argument('--actor-lifecycle',choices=['pooled','fresh'],default='pooled')
    parser.add_argument('--pool-size',type=int,default=32)
    parser.add_argument('--dispatch-lanes',type=int,default=1)
    parser.add_argument('--core-perf',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 2<=args.concurrency<=10000 or args.seconds<=0 or args.warmup<0 or args.timeout<=0 or args.sample_every<0 or not 1<=args.pool_size<=4096 or not 1<=args.dispatch_lanes<=16:parser.error('invalid limits')
    check=runpy.run_path(str(ROOT/'scripts/check-backend.py'))
    source=check['require_source']('ORESLANG_SOURCE_DIR','SOURCE_REF')
    git=lambda p,*a:subprocess.check_output(['git','-C',str(p),*a],text=True).strip()
    router=ROOT/'dependencies/http-routing'
    otel=ROOT/'dependencies/otel'
    if git(otel,'status','--porcelain') or git(otel,'rev-parse','HEAD')!=git(ROOT,'ls-files','--stage','dependencies/otel').split()[1]:raise RuntimeError('Otel provenance differs')
    if git(router,'status','--porcelain') or git(router,'rev-parse','HEAD')!=git(ROOT,'ls-files','--stage','dependencies/http-routing').split()[1]:raise RuntimeError('Router provenance differs')
    fixture=ROOT/('tests/profiled-pooled-server.atto' if args.sample_every else 'tests/pooled-server.atto')
    if args.dispatch_lanes>1:
        fixture=ROOT/'tests/profiled-concurrent-server.atto'
    args.output.mkdir(parents=True,exist_ok=False)
    source_fixture = fixture
    source_dirty = bool(git(ROOT,'status','--porcelain'))
    generated = configure_fixture(fixture.read_text(),args.actor_lifecycle,args.pool_size).replace('dispatcher.serve(4)',f'dispatcher.serve({args.dispatch_lanes})')
    with tempfile.NamedTemporaryFile(mode='w',suffix='.atto',prefix='.sustained-',dir=ROOT/'tests',delete=False) as temp:
        temp.write(generated)
        fixture=Path(temp.name)
    (args.output/'fixture.atto').write_text(generated)
    env=dict(os.environ);env['JAVA_TOOL_OPTIONS']=env.get('JAVA_TOOL_OPTIONS','')+' -Xms256m -Xmx2g -Dores.runtime.carriers=java'
    meta={'spin_commit':git(ROOT,'rev-parse','HEAD'),'spin_dirty':source_dirty,
          'runtime_commit':git(source,'rev-parse','HEAD'),'router_commit':git(router,'rev-parse','HEAD'),'otel_commit':git(ROOT/'dependencies/otel','rev-parse','HEAD'),
          'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
          'platform':platform.platform(),'cpus':os.cpu_count(),'java_options':env['JAVA_TOOL_OPTIONS'],
          'java_version':subprocess.run([env.get('ORES_JAVA','java'),'-version'],capture_output=True,text=True).stderr,
          'source_fixture':str(source_fixture.relative_to(ROOT)),'actor_lifecycle':args.actor_lifecycle,'application_instances':1,'dispatch_lanes':args.dispatch_lanes,'pool_workers_per_mode':args.pool_size if args.actor_lifecycle=='pooled' else None,'mix':args.actor_mode+'; fixed per connection; no retry',
          'configuration':{k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()}}
    (args.output/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    lines=queue.Queue();captured=[];resource_samples=[];monitor_stop=threading.Event()
    with (args.output/'stderr.log').open('w') as error:
        server=subprocess.Popen([str(ROOT/'scripts/compiler.sh'),*(['--core-perf','--core-debug'] if args.core_perf else []),'--platform=server','--allow-net=127.0.0.1:0',str(fixture)],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=error,text=True)
        def reader():
            for line in server.stdout:captured.append(line.strip());lines.put(line.strip())
        reader_thread=threading.Thread(target=reader,daemon=True);reader_thread.start()
        def monitor():
            while not monitor_stop.wait(1):
                stat=subprocess.run(['ps','-o','rss=,%cpu=','-p',str(server.pid)],capture_output=True,text=True)
                if stat.returncode==0 and stat.stdout.strip():
                    rss,cpu=stat.stdout.split();resource_samples.append({'epoch':time.time(),'rss_kib':int(rss),'cpu_percent':float(cpu)})
        monitor_thread=threading.Thread(target=monitor,daemon=True);monitor_thread.start()
        try:
            startup_deadline=time.monotonic()+30
            while True:
                line=lines.get(timeout=max(.001,startup_deadline-time.monotonic()))
                if line.isdigit() and 0<int(line)<65536:
                    port=int(line);break
                if time.monotonic()>=startup_deadline:raise TimeoutError('No server port within 30 seconds')
            result=asyncio.run(measure(port,args.concurrency,args.seconds,args.warmup,args.timeout,args.output,args.sample_every,args.actor_mode,args.actor_lifecycle,args.pool_size))
            import http.client
            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
            try:
                conn.request('GET','/__stop');reply=conn.getresponse();reply.read()
                if reply.status!=200:raise RuntimeError('Shutdown failed')
            finally:conn.close()
            server.wait(timeout=15);reader_thread.join(timeout=2)
            if server.returncode:raise RuntimeError(f'Server exit {server.returncode}')
            index=captured.index('SERVER_COUNTERS')
            keys=['accepted','rejected','completed','active','peak_admitted']
            counters=dict(zip(keys,map(int,captured[index+1:index+6])))
            (args.output/'server.json').write_text(json.dumps(counters,indent=2)+'\n')
            if len(counters)!=5 or counters['rejected'] or counters['active'] or counters['accepted']!=counters['completed']:raise RuntimeError('Invalid server counters: '+str(counters))
            if args.actor_lifecycle=='pooled' and any(r['distinct_workers_with_warmup']!=args.pool_size for r in result['modes'].values()):raise RuntimeError('Missing full-pool reuse evidence')
            print(json.dumps(result),flush=True)
        finally:
            if server.poll() is None:
                server.terminate()
                try:server.wait(timeout=5)
                except subprocess.TimeoutExpired:server.kill();server.wait()
            monitor_stop.set();monitor_thread.join(timeout=3)
            (args.output/'stdout.log').write_text('\n'.join(captured)+'\n')
            (args.output/'resources.json').write_text(json.dumps(resource_samples)+'\n')
            fixture.unlink(missing_ok=True)

if __name__=='__main__':main()
