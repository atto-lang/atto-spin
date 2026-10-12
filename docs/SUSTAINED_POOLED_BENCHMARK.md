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
A GitHub runner may be CPU/memory/FD-limited at 10,000 open connections, and
100% success is an *acceptance metric*, not an assumed result. Keep malformed
responses, 503s, aborted connections, and timeouts visible. `--duration 180`
means 180s of request production after connection ramp-up; tail requests can
take additional time. One sustained run per configuration avoids conflating
actor creation with transport admission. CPU and server allocations need
separate instrumented runs.
