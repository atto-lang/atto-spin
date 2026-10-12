# Spin persistent request actors: funded sustained-load evidence

Date: 2026-10-12. All tests were GitHub Actions on Ubuntu / GraalVM Community JDK 25,
using a private funded mirror with byte-identical Git blob locks (Java, Spin, router).
The runner reported CPU affinity of **2 logical CPUs**. Runs used the Python
closed-loop HTTP/1.1 keep-alive client, validated status/body/mode, zero retries,
and a pool of **128 reusable actor workers** per mode.

## Completed 180-second runs

The original 20k-admission six-way run
[38308288260](https://github.com/zed-pkg-test/formal-methods-cross-check/actions/runs/38308288260)
completed four 100/1k cases with 100% success and identified two remaining
transport problems: default JDK max idle cache 200 at 10k and an admission
capacity matching concurrency in the preceding 10k experiment.

| Clients | Actor kind | Correct HTTP 200 | Mean successful HTTP response | p95 | Correct response % |
| ---: | --- | ---: | ---: | ---: | ---: |
| 100 | SHARED | 202,309 | 88.993 ms | 102.9 ms | 100% |
| 100 | PRIVATE | 289,211 | 62.247 ms | 70.3 ms | 100% |
| 1,000 | SHARED | 139,455 | 1,294.926 ms | 1,509.3 ms | 100% |
| 1,000 | PRIVATE | 136,555 | 1,322.860 ms | 1,517.6 ms | 100% |

The separate final 10k run
[38309026285](https://github.com/zed-pkg-test/formal-methods-cross-check/actions/runs/38309026285)
PASSED both the SHARED and PRIVATE jobs after explicit server properties:
`jdk.httpserver.maxConnections=20000` and
`sun.net.httpserver.maxIdleConnections=20000`.
The Oreslang listener used **TCP backlog 4096**, **HTTP exchange admission
capacity 20000**, and the same 128-worker pool.

| Clients | Actor kind | Correct HTTP 200 | Mean successful response | p95 | Complete RPS | Errors/503/retries |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 10,000 | SHARED | 155,621 | 11,914.438 ms | 14,411.7 ms | 810.09 | 0 / 0 / 0 |
| 10,000 | PRIVATE | 134,178 | 13,895.588 ms | 16,425.9 ms | 691.18 | 0 / 0 / 0 |

Both servers finished with zero active exchanges. Each created precisely
128 actors and dispatched all correct responses through those persistent
actors. These are *response* latencies excluding socket setup, not burst
completion duration. The two 10k trials produced **289,799 / 289,799
successful complete HTTP responses**.

## Independent Java/Python process CPU profile

[Funded CPU/RSS run 38309774398](https://github.com/zed-pkg-test/formal-methods-cross-check/actions/runs/38309774398)
PASSED smoke plus four 60-second workloads. Every HTTP response was correct,
with zero 503s, retries and failures.

| Clients | Kind | Correct responses | Mean response | Completed RPS | Java process CPU | Python client CPU | Java peak RSS |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | SHARED | 41,547 | 1,459.328 ms | 676.97 | 142.81% | 14.14% | 419.0 MB |
| 1,000 | PRIVATE | 39,403 | 1,539.318 ms | 641.49 | 144.82% | 14.04% | 404.2 MB |
| 10,000 | SHARED | 54,512 | 12,022.895 ms | 757.13 | 143.10% | 15.49% | 1,101.9 MB |
| 10,000 | PRIVATE | 46,793 | 14,214.840 ms | 630.38 | 145.14% | 14.76% | 1,007.7 MB |

CPU percentages are per process, with **100% = one logical CPU**; thus
143-145% is ~1.43-1.45 CPU-equivalents. The load generator consumed only
~0.14-0.15 CPU-equivalents. This is evidence that the **Java server process
rather than Python client CPU** consumes most execution time on this 2-vCPU
runner, but does not establish whether transport dispatch, supervisor,
actor scheduling, synchronization, allocation/GC, or another server component
is the dominant CPU cost. CPU samples include TCP setup ramp-up; measured
response latency excludes it. Separate hosted machines vary, so rows are
**not** controlled A/B estimates of SHARED vs PRIVATE performance.

## Contract and release gates

- Runtime adds `http.listen_with_limits(host, port, backlog,
  admission_capacity, body_limit, deadline_ms)`; prior
  `http.listen(host, port, capacity, body_limit, deadline_ms)` remains valid.
  Both limits are bounded (1..65536).
- Guest integration test exercises backlog 32 alongside 20,000 admission slots.
- Real Spin pooled actors release admission after each exchange while retaining
  their worker; fresh actors keep finalization-tied admission.
- Exact-blob private CI mirror builds Java on JDK 25 without cross-org secrets.
- JDK idle keep-alive cache is a distinct JVM-wide limit. Its documented
  default of 200 coincided with 670 aborted 10k PRIVATE connections in an
  earlier run; making it 20,000 eliminated failures on the subsequent run.
  This supports, but does not conclusively prove, the idle-eviction hypothesis.
- Zero error at 10k **does not** establish production readiness, actor
  safety under cancellation races, or a throughput ceiling.

Next: JFR/async-profiler hotspot capture for Java and pure JDK HTTP transport
control on matched runner hardware; ABBA worker-pool sizes (32/128/512/1024),
graceful close and timeout/cancellation fault injection, GC/heap growth slope,
and repeatable multi-run confidence intervals before either PR merges.
