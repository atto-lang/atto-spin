# Native HTTP actor transport baseline — 2026-10-18

One OS process, 100 persistent closed-loop connections, 128 reused actors and
4 native scheduler carriers. 10 seconds warmup, then 180 measured seconds on
arm64 macOS. Every valid request executes the compiled Oreslang actor, including
an actor-heap request-counter check inside its exclusive admitted turn.

| Measurement | Result |
|---|---:|
| Responses started in measured window, including drain | 12,281,799 |
| Responses completed within measured window | 12,281,699 |
| Measured throughput | 68,231.66 requests/sec |
| Mean HTTP exchange at client | 0.742556 ms |
| Mean full client cycle, including task scheduling | 1.465321 ms |
| HTTP p50 / p95 / p99 | 0.732542 / 0.809916 / 0.919708 ms |
| Mean parsed-request → actor-start queue, including warmup | 0.00731714 ms |
| Mean actor callback, including warmup | 0.00043947 ms |
| Mean completion-publication → reactor-consumption, including warmup | 0.0232143 ms |
| Mean server exchange, including warmup | 0.032464 ms |
| Failures / retries / mailbox retries | 0 / 0 / 0 |
| Valid HTTP accepted / completed / scheduler completed, including warmup | 12,965,700 each |
| Actors observed / peak connections | 128 / 100 |

Source commit `5df5750134a980854e8fb10ac203b66b3b158431`, tree
`4925e62bcd64b39e392597442828c60f4232da38`. Binary/source hashes and toolchain
versions are in [the build receipt](build-receipt.json); raw summaries are in
[result.json](result.json), [metadata.json](metadata.json) and [server.log](server.log).
The client does not retry or reconnect failed requests. Exact count gates verify
that every successful request traversed the scheduler and completed its response.

**This is a lighter native integration workload, not a full Spin backend speedup
comparison.** Native adapter code parses/routes/formats HTTP; the LLVM-compiled
guest actor counts requests and returns status. Spin modules, source-level
shared/private placement, guest await/cooperate checkpoints and the Oreslang OTel
module are not lowered here. The report makes no shared-versus-private benchmark
claim or hardware memory-protection claim. See [scope and next gates](../README.md).

Server aggregate timings include warmup; client latency/throughput exclude it.
Averages are not tail guarantees. HTTP latency excludes part of client-side task
scheduling, so use the full client cycle when estimating 100-client throughput.
No build, test suite or second load generator ran alongside the measurement.
Source/mirror preparation and GitHub delivery ran during the measurement; no
claim of a dedicated idle benchmark machine is made.
