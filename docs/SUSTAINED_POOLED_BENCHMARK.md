# Sustained pooled Spin actor benchmark

This is a **proposed, opt-in Java/GraalVM runtime path** based on `http.pooled_handler(type, pool_size)`.
Each route owns up to `pool_size` persistent request actors, shared or private.
Each actor handles multiple HTTP exchanges sequentially; do not call `self.end()`
after each request. Fresh actor routes still use `http.handler`.

The benchmark keeps 100, 1,000, or 10,000 HTTP/1.1 connections active,
and sends a continuous closed-loop stream of requests for **180 seconds per
mode and concurrency** (six independent trials = 18 minutes minimum).
It reports the mean and p50/p95/p99 response time per request, completed
responses/second, response validation failures, and real actor-created vs
dispatch counters. Socket setup is excluded from response latency; burst
benchmark comparisons therefore measure a different thing. The client
uses an approximate 0.1ms-bucket histogram. No retries are hidden.

```bash
python3 scripts/test-sustained-client.py
python3 scripts/sustained-matrix.py --duration 180 --concurrency 100,1000,10000 \
  --pool-size 128 --capacity 10000 --out /tmp/spin-sustained-run
```

Requires the clean pinned Java source and HTTP router, JDK 25, Maven, and
`ORESLANG_SOURCE_DIR`. Read the JSON metadata for exact source/compiler pins.
For large persistent-connection tests the runner supplies both
`-Djdk.httpserver.maxConnections=20000` and
`-Dsun.net.httpserver.maxIdleConnections=20000`. The latter avoids the JDK
HTTP server's default 200-idle-connection cache evicting keep-alive sockets;
without it an apparent failed request can instead be a closed idle socket.
That transport property is independent of bounded HTTP exchange admission and
is recorded in the benchmark metadata.
A GitHub runner may be CPU/memory/FD-limited at 10,000 open connections, and
100% success is an *acceptance metric*, not an assumed result. Keep malformed
responses, 503s, aborted connections, and timeouts visible. `--duration 180`
means 180s of request production after connection ramp-up; tail requests can
take additional time. One sustained run per configuration avoids conflating
actor creation with transport admission. CPU and server allocations need
separate instrumented runs.

## Client/server CPU attribution

`scripts/process_resources.py` samples the Java HTTP server PID and Python
load-generator PID independently using Linux `/proc` process CPU ticks, RSS,
and thread counts. Each trial emits `<tag>.resources.json` containing the
sampled aggregate CPU percentage (100% equals one logical CPU), peak RSS,
peak thread count, the cgroup CPU quota and CPU affinity.

This distinguishes gross CPU contention on the same GitHub-hosted runner,
but it is not a JVM profiler and does not isolate the machines. Socket-setup
warmup is included in the process-resource sampling interval but excluded from
HTTP response latency. Cross-run differences between independently provisioned
runners must not be attributed to actor kind without repeated matched trials.
