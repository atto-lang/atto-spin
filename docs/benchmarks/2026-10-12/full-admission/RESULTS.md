# Spin response latency with full burst admission — 2026-10-12

**66,600 / 66,600 measured requests succeeded (100%).** No 503s, other HTTP
errors, client errors, or retries. Each of six configurations ran three bursts.
All six servers completed every admitted request and drained to zero active
exchanges. Capacity was set to 10,000, transport max connections to 20,000.
No production default or runtime implementation was changed.

| Concurrent requests | Shared mean | Isolated mean | Success |
| ---: | ---: | ---: | ---: |
| 100 | 45.49 ms | 49.33 ms | 100% |
| 1,000 | 266.69 ms | 285.62 ms | 100% |
| 10,000 | 2,357.37 ms | 2,410.15 ms | 100% |

Means are calculated from individual request durations, pooled across all three
repeats. Each duration starts when the client task runs and ends when its full
response is received, including a fresh TCP connection. This is not batch time
divided by request count. For example, the 10,000-request batches complete in
roughly four seconds: inverse throughput is about 0.4 ms/request, while the
average individual caller waits about 2.4 seconds. Requests overlap.

At 10,000 concurrency, p95 response time is 3.67 seconds shared and 3.75 seconds
isolated; successful burst rate is approximately 2,508–2,564 requests/s. Observed
peak admitted requests are 9,993 shared and 9,996 isolated. Peak sampled JVM RSS
is 1,187 MiB shared and 1,090 MiB isolated (includes startup/warm-up).

This retains one new actor per admitted request. Removing the small admission
limits removes overload rejection; it does not imply unbounded capacity. The
queueing visible at large bursts is now paid as latency rather than 503s.

## Scope

Local macOS ARM64, 18 logical CPUs, 48 GiB RAM; Temurin JDK 25, Java actor
carriers, JVM interpreter, 2 GiB heap ceiling. Identical three-byte responses for
both actor modes; 50 sequential warm-up requests per server. Client and server
share a host; the asyncio load generator and TCP connection establishment add
latency at 10,000 concurrency. This is a burst test, not sustained keep-alive
capacity or Graal native-image performance. Three repeats are not sufficient to
claim either actor mode is intrinsically faster.

Reproduce with the pinned clean compiler/router checkouts:

```sh
python3 scripts/load-matrix.py --actors 10000 --timeout 60 --output /absolute/path/to/new-results
python3 scripts/summarize-load.py /absolute/path/to/new-results
```

See [methodology](../../../LOAD_TESTING.md), [metadata](metadata.json), and
[extended statistics](summary.csv). Raw per-request samples and logs remain in
the local experiment output directory.
