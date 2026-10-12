# Sustained HTTP actors: scheduling workload V2

**Historical V2 measurement note:** These published values predate the
[benchmark-client timer hardening](https://github.com/ores-truffle-oreslang/oreslang-spin/pull/8)
that starts the 35-second clock *after* all concurrent client tasks have been
constructed. They remain auditable snapshots, but must not be mixed into
statistical comparisons with runs using the corrected timer. They also predate
the pooled-exchange cancellation and graceful-shutdown hardening in
[Java PR #759](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/759).


Test date: 2026-10-12. Workload includes **one `suspends` checkpoint
invocation, one `rt cooperate`, and one explicit awaited HTTP response**
per actor request. The suspended receiver contract and checkpoint response
header are required in both shared and isolated fresh and reused actors.

These are **new measurements**, not a reinterpretation of the historical
HTTP-only V1 table. Keep the comparisons paired by actor kind and concurrency.
The driver and server share a GitHub-hosted Actions runner.

## Verified 100-, 1,000-, and 10,000-client samples

| Mode | Concurrency | Strategy | Validated requests | Success | Throughput (req/s) | Mean (ms) | p95 (ms) | p99 (ms) |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| shared | 100 | fresh | 26,485 | 100% | 754.006 | 132.307 | 154.822 | 282.565 |
| shared | 100 | pooled | 25,998 | 100% | 739.967 | 134.811 | 158.284 | 251.924 |
| isolated | 100 | fresh | 36,094 | 100% | 1,028.379 | 97.069 | 116.272 | 187.693 |
| isolated | 100 | pooled | 36,057 | 100% | 1,027.046 | 97.175 | 113.357 | 195.919 |
| shared | 1,000 | fresh | 33,576 | 100% | 932.624 | 1,053.812 | 1,197.387 | 1,825.217 |
| shared | 1,000 | pooled | 32,611 | 100% | 903.571 | 1,086.931 | 1,445.393 | 1,920.398 |
| isolated | 1,000 | fresh | 26,981 | 100% | 744.033 | 1,312.895 | 1,595.994 | 2,170.969 |
| isolated | 1,000 | pooled | 26,311 | 100% | 723.892 | 1,348.053 | 1,546.591 | 2,194.172 |
| shared | 10,000 | fresh | 32,686 | 100% | 687.390 | 11,899.335 | 14,914.159 | 15,668.475 |
| shared | 10,000 | pooled | 33,714 | 100% | 704.195 | 11,560.817 | 13,558.201 | 14,325.676 |
| isolated | 10,000 | fresh | 32,173 | 100% | 669.499 | 12,114.211 | 14,441.802 | 15,297.185 |
| isolated | 10,000 | pooled | 32,426 | 100% | 669.429 | 12,007.348 | 13,986.611 | 14,710.513 |

Evidence: [100-client exact-source funded run #38320484258](https://github.com/zed-pkg-test/java-app/actions/runs/38320484258)
(fully successful) and the independently successful 1,000-client jobs in
[run #38320761273](https://github.com/zed-pkg-test/java-app/actions/runs/38320761273)
(the overall matrix was failed by separately run 10,000-client cases).
The **fully successful** 10,000-client shared and isolated pairs were collected
independently in [run #38320991426](https://github.com/zed-pkg-test/java-app/actions/runs/38320991426).
Earlier 10,000-client attempts with incomplete HTTP reads are excluded from
this comparison and remain visible in their failed workflow runs.

Server admission rejections, client errors, and active exchange leaks were zero
for every *included* sample. Pooled actors were
demonstrably reused (100 workers, 25,948 successful reuses for shared;
100 workers, 36,007 successful reuses for isolated including warmup).
The 10,000-client runs used 256 actors in each pool (33,508 successful shared
reuses and 32,220 successful isolated reuses, including warmup).

## Reproducibility

- Java runtime source commit:
  `d9fefbcf0ae0e0f230607666d6d2347032eee2a0`.
- Exact Java subtree: `75fb901aad0216deeaf8293ed01706110629d13b`.
- Workload V2 source fixture blob:
  `ced7b7280989aaeaa6c619ba8b1b3d25b353a6df`.
- Workload-aware HTTP load client blob:
  `ab4111e9241493052bd5078563af65c6116213ee`.
- Source fixture equivalence checked in
  `tests/test-sustained-fixture.py`, response acceptance checked in
  `tests/test-sustained-client.py`, and real guest execution checked
  by the funded Actions workflow.
- No retries. Duration: 35 seconds of closed-loop client admission for
  each strategy; wall-clock throughput includes final inflight response
  draining. The 100-client pool uses 100 long-lived actors; the 1,000- and
10,000-client configurations each use 256.

Do not generalize sub-3% differences from a single paired sample. Randomized/alternating-order repetitions are needed
before claims about statistical significance, resource usage, or native-image
behavior.
