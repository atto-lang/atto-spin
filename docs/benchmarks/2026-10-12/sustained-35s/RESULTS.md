# Spin 35-second sustained load: fresh vs reusable HTTP actors

Date: 2026-10-12. Source: Java/GraalVM opt-in pooled handlers,
[oreslang-source.java PR #759](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/759);
Spin fixture: [Spin PR #8](https://github.com/ores-truffle-oreslang/oreslang-spin/pull/8).

**Status:** six paired fresh-versus-pooled comparisons with 100% validated
HTTP responses and no client retries. All server runs drained accepted
exchanges to zero active. These are individual runs, not replicated confidence
intervals.

## Measurements

Each strategy accepts closed-loop client requests for **35 seconds**.
The elapsed wall-clock time includes final response draining; reported successful
req/s divides validated successes by the actual wall-clock elapsed, rather than
the nominal 35 seconds. Persistent HTTP/1.1 connections are used for BOTH
strategies; new actors are spawned per request only in the fresh strategy.
Pooled actors are persistent; 100 workers are configured at 100 clients and
256 at 1,000/10,000 clients.

| Mode | Clients | Fresh successful req/s | Pooled successful req/s | Fresh mean ms | Pooled mean ms | Fresh p99 ms | Pooled p99 ms | Fresh successes | Pooled successes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| shared | 100 | 762.342 | 740.422 | 130.868 | 134.722 | 232.839 | 223.766 | 26,777 | 26,010 |
| shared | 1,000 | 740.352 | 729.080 | 1,319.938 | 1,340.339 | 2,171.858 | 1,969.445 | 26,843 | 26,437 |
| shared | 10,000 | 719.879 | 703.824 | 11,376.717 | 11,587.235 | 14,142.195 | 14,344.207 | 34,146 | 33,693 |
| isolated | 100 | 1,603.984 | 1,597.064 | 62.268 | 62.536 | 121.443 | 116.961 | 56,238 | 55,994 |
| isolated | 1,000 | 814.831 | 800.704 | 1,201.456 | 1,222.492 | 2,191.739 | 1,824.017 | 29,471 | 28,998 |
| isolated | 10,000 | 1,174.768 | 1,181.972 | 7,497.747 | 7,463.426 | 8,989.193 | 8,890.984 | 50,284 | 50,782 |

The 10,000-client isolated run uses longer JDK HTTP request, response and
keepalive timeouts (120 seconds) to prevent transport read truncation. Thus
different isolated-vs-shared rows should **not** be treated as a direct
actor-isolation performance comparison. Fresh and pooled within each row
share the same JVM options and runner.

## Reuse verification

The server-reported worker counters show that reuse happened, rather than
merely TCP connection reuse.

| Mode | Clients | Workers created | Successful worker reuses |
|---|---:|---:|---:|
| shared | 100 | 100 | 25,960 |
| shared | 1,000 | 256 | 26,231 |
| shared | 10,000 | 256 | 33,487 |
| isolated | 100 | 100 | 55,944 |
| isolated | 1,000 | 256 | 28,792 |
| isolated | 10,000 | 256 | 50,576 |

Worker reuse counters include warmup traffic and are not a one-to-one tally
of measured requests. Each case had 50 warmup requests before the measured
period. Server accepted/completed also include warmup and the stop endpoint.

## Provenance

- Exact Java source commit: `d9fefbcf0ae0e0f230607666d6d2347032eee2a0`.
- Exact Java source Git tree: `75fb901aad0216deeaf8293ed01706110629d13b`.
- Spin route fixture blob: `11d97682360e792d8df00f2ccf665e58b5fef3d9`.
- Spin module blob: `f690ea80aa05bd6f1e1651baf0046453eb66070d`.
- HTTP router module blob: `32ce8cca507470369d24207a887277dba0341f39`.
- Client driver blob: `eb234e58e54d54866270c3320c032948987a89e4`.
- GitHub-hosted Ubuntu runner, Temurin JDK 25, JVM interpreter,
  Java actor carriers, 2 GiB JVM heap maximum; client and server share runner CPU.
- 100/1,000-client completed jobs:
  [funded Actions run #38317408913](https://github.com/zed-pkg-test/java-app/actions/runs/38317408913)
  (overall run marked failed because 10,000-client cases deliberately failed
  the 100%-success gate; the four smaller individual jobs succeeded).
- Shared 10,000-client:
  [funded Actions run #38317696602](https://github.com/zed-pkg-test/java-app/actions/runs/38317696602)
  (overall run marked failed because isolated 10,000 hit HTTP read errors;
  shared 10,000 job succeeded).
- Isolated 10,000-client:
  [funded Actions run #38318011384](https://github.com/zed-pkg-test/java-app/actions/runs/38318011384)
  (full run passed).

The source organization lacked usable Actions capacity. An exact source Git
tree was constructed in `zed-pkg-test/java-app/oreslang-java-mirror`; the
tree SHA was checked by every funded job. Spin source files and router source
were mirrored separately and independently verified against their source
Git blob SHA. No private cross-organization checkout or credentials were used.

## Interpretation

Fresh actors won mean latency and successful throughput in **five of six**
individual pairs (around 0.4% to 2.9% throughput advantage). Isolated 10,000
was the one exception: the pooled version improved throughput around 0.6%.
Some pooled cases improved the p99 latency even while slightly worsening the
mean. Pooling slashed actor creation but did not provide a general
request/response performance speedup under these conditions.

This does not settle long-run capacity, memory efficiency, Native Image, or
whether persistent actors pay off for expensive initialization. The pair
order was always fresh then pooled, each had only one run, and both the
load generator and target ran on the same two-core runner. Results are
sensitive to scheduler contention, transport behavior, and warmup.
For statistical claims, run alternating order and at least 3-5 repeats per
pair, then measure allocation, CPU, RSS, and GC separately.
