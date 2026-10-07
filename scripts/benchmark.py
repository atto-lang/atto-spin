#!/usr/bin/env python3
"""Local HTTP baseline; includes transport, routing, actor startup, and transfer."""
import argparse, concurrent.futures, http.client, json, os, pathlib, queue, statistics, subprocess, threading, time
root = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--requests', type=int, default=200)
parser.add_argument('--concurrency', type=int, default=8)
args = parser.parse_args()
if args.requests < 1 or args.concurrency < 1 or args.concurrency > 16: parser.error('positive requests and concurrency 1..16 required')
compiler = os.environ.get('ORESLANG_COMPILER', str(root/'scripts/compiler.sh'))
with subprocess.Popen([compiler, '--platform=server', '--allow-net=127.0.0.1:0', str(root/'tests/server.ores')], cwd=root,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as server:
    lines, errors = queue.Queue(), []
    threading.Thread(target=lambda: [lines.put(x.strip()) for x in server.stdout], daemon=True).start()
    threading.Thread(target=lambda: [errors.append(x) for x in server.stderr], daemon=True).start()
    try:
        assert lines.get(timeout=15) == 'true'
        port = int(lines.get(timeout=5))
        def request(path):
            started = time.perf_counter_ns()
            conn = http.client.HTTPConnection('127.0.0.1',port, timeout=10)
            try:
                conn.request('GET',path)
                response = conn.getresponse(); response.read()
                assert response.status == 200, response.status
                timing = {piece.strip().split(';dur=')[0]:float(piece.split(';dur=')[1]) for piece in (response.getheader('Server-Timing') or '').split(',') if ';dur=' in piece}
            finally: conn.close()
            return ((time.perf_counter_ns()-started)/1e6, timing)
        result = {'requests_per_mode':args.requests,'concurrency':args.concurrency,'connection':'new HTTP/1.1 connection per request',
                  'scope':'local end-to-end baseline; startup and move-to-claim timings overlap and include scheduler delay'}
        for mode,path in [('shared','/shared'),('isolated','/private')]:
            for _ in range(30): request(path)
            start_epoch = time.time()
            start = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                samples = list(pool.map(lambda _:request(path),range(args.requests)))
            latencies = sorted(sample[0] for sample in samples)
            elapsed = time.perf_counter()-start
            result[mode] = {'epoch_start':start_epoch, 'epoch_end':time.time(),
                            'actor_startup_p50_ms':round(statistics.median(s[1]['actor-startup'] for s in samples),4),
                            'move_to_claim_p50_ms':round(statistics.median(s[1]['move-to-claim'] for s in samples),4),
                            'requests_per_second':round(args.requests/elapsed,2),
                            'p50_ms':round(statistics.median(latencies),3),
                            'p95_ms':round(latencies[min(len(latencies)-1,int(len(latencies)*.95))],3),
                            'p99_ms':round(latencies[min(len(latencies)-1,int(len(latencies)*.99))],3)}
        request('/__stop'); server.wait(timeout=10)
        assert server.returncode == 0, ''.join(errors[-20:])
        print(json.dumps(result,indent=2))
    finally:
        if server.poll() is None:
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill(); server.wait()
