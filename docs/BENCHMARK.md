# Local baseline — 2026-10-07

Measured on the development machine (macOS arm64, Homebrew OpenJDK 25.0.4.1)
using the interpreter fallback, not optimizing Graal or native-image. The client
runs locally, opens a new HTTP/1.1 connection per request, and uses eight worker
threads. There are 30 warm-up requests and 200 measured requests per actor mode.
The two handlers return small text bodies; shared uses the imported response
helper while isolated uses the direct primitive, so this is not an apples-to-
apples claim that either actor mode is intrinsically faster.

| Measurement | Shared | Isolated |
| --- | ---: | ---: |
| Requests/s | 168.61 | 193.01 |
| End-to-end p50 (ms) | 46.791 | 39.934 |
| End-to-end p95 (ms) | 50.260 | 45.408 |
| End-to-end p99 (ms) | 51.353 | 45.880 |
| Actor spawn-to-ready p50 (ms) | 0.0498 | 0.0365 |
| Exchange move-to-claim p50 (ms) | 0.0981 | 0.0533 |

Startup includes scheduler/admission delay. Move-to-claim includes transport of
the token and actor startup when it overlaps; these intervals must not be added
together. Timings are exposed only when the test handler opts into Server-Timing.
End-to-end latency includes routing, conservative imported-call continuation
lowering, transport, interpreter execution, and client overhead. This is a
functional baseline, not a production throughput claim.

A separate JFR profile used 1,000 measured requests per mode at concurrency eight.
`jdk.ObjectAllocationSample` weights inside each mode's measured time window
estimated **1,442,435 bytes/request for shared** (1,202 samples) and
**1,353,382 bytes/request for isolated** (1,192 samples). These are sampled
whole-JVM allocations, not exact allocation counts or isolated-heap accounting.
They exclude the recorded startup/warm-up windows but include runtime/transport
allocations during traffic. The cost warrants investigation before performance
claims; the draft has not optimized the interpreter's routing/continuation path.

Reproduce timings:

```sh
ORESLANG_COMPILER="$PWD/scripts/compiler.sh" python3 scripts/benchmark.py
```

Reproduce allocation sampling (JDK `jfr` must be on PATH):

```sh
mkdir -p work
JAVA_TOOL_OPTIONS="-XX:StartFlightRecording=filename=$PWD/work/spin.jfr,settings=profile,dumponexit=true -Xlog:jfr*=off" \
  ORESLANG_COMPILER="$PWD/scripts/compiler.sh" \
  python3 scripts/benchmark.py --requests 1000 > work/profile.json
jfr print --json --events jdk.ObjectAllocationSample work/spin.jfr > work/allocations.json
python3 scripts/summarize-allocations.py work/profile.json work/allocations.json
```

This snapshot measures the initial implementation and establishes reproducible
checks. A follow-up optimization should use identical handler paths, longer
warm-up, repeated trials, an optimizing runtime, and per-stage allocation
profiling before drawing comparisons between actor policies.

## Larger concurrency matrix

See the [2026-10-12 burst-load experiment](benchmarks/2026-10-12/RESULTS.md) for
100/1,000/10,000 concurrent attempts at 5/20/50/300 request-actor admission slots.
It records overload rejection separately from successful work and exposes client
and TCP backlog limitations.

See the [full-admission latency follow-up](benchmarks/2026-10-12/full-admission/RESULTS.md)
for 66,600 successful requests with no rejections or retries, including mean
response time at 100, 1,000, and 10,000 concurrency.
