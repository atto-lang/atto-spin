# HTTP acceptance breakdown — 2026-10-18

100 persistent clients, 32 shared workers, one control worker, ten seconds warm-up
and 180 measured seconds. 2,393,012 measured requests succeeded, 13,293.96
completions/sec, 7.459 ms mean client latency. No failures, retries or admission
rejections; all server counters drained. JVM interpreter; exact revisions and
options are in metadata. One sequential run on a shared development machine.

All 2,378 sampled requests have eleven correlated metrics. The first four
components below are nonnegative and sum exactly, in nanoseconds, to the existing
admission.to_dispatch measurement for every trace.

| Interval | Mean ms | p95 ms |
|---|---:|---:|
| http.admission_to_queue | 0.000617 | 0.001292 |
| http.queue | 7.256096 | 8.160250 |
| accept.ready_to_resume | 0.000332 | 0.000458 |
| supervisor.prepare | 0.006030 | 0.007333 |
| admission.to_dispatch | 7.263075 | 8.166125 |
| routing.dispatch | 0.067404 | 0.090917 |
| mailbox.move_to_claim | 0.018223 | 0.019500 |

Nearly all measured pre-dispatch time is in the pending HTTP queue, not the
interval after accept becomes ready. Queue time can still reflect supervisor
scheduling before it calls accept; this does not prove all scheduler overhead
negligible. It points toward improving how quickly the supervisor drains the
queue. Actor mailbox handoff remains small. The total and subsequent rows overlap
other measurements and must not be added as disjoint components.

`accept.ready_to_resume` includes Future publication, scheduler waiting,
interpreter resumption and timestamp-call overhead; it is not pure executor queue
time. Direct delivery to an already-waiting accept records zero pending-queue
time. Core `http.accept.queue` events are cold/bounded; this table uses warm
sampled oreslang-otel metrics. No request headers or bodies were added to logs.

Reproduce using the pinned runtime and configured ORES_JAVA:

```sh
JAVA_TOOL_OPTIONS=-Dores.runtime.control.parallelism=1 \
python3 scripts/sustained-load.py --concurrency 100 --seconds 180 \
  --actor-mode shared --pool-size 32 --sample-every 1000 --core-perf \
  --output /tmp/spin-http-queue
python3 scripts/summarize-profile.py /tmp/spin-http-queue
```

See docs/PROFILING.md and runtime docs/HTTP_ACCEPT_TIMING.md for boundaries.
Instrumentation adds timestamp/property reads, so do not present this as a speed
improvement against older fixtures. Client event-loop lag p99 was 0.245 ms and
maximum 27.244 ms. Compressed raw logs, generated fixture, correlation summaries,
server counters, resource samples and numeric-latency hashes are preserved here.
