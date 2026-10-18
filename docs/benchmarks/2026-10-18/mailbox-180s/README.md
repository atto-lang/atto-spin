# Sustained mailbox/NIO HTTP results — 2026-10-18

Both modes meet the **mean HTTP pending queue below 3 ms** and **at least
10,000 requests/sec** targets. Each run used 100 persistent closed-loop clients,
180 measured seconds after 10 seconds of warmup, one Spin application, one
immutable route table, four CONTROL/supervisor dispatch lanes and 128 reusable
actors of the selected mode. Every actor executes source code exclusively;
no experimental multiple-thread actor execution is enabled.

| Mode | Measured requests (including final drain) | Responses/sec within window | Mean HTTP queue ms | Mean HTTP exchange ms | Mean client cycle ms | Client HTTP p99 ms |
|---|---:|---:|---:|---:|---:|---:|
| shared | 7,829,252 | 43,495.29 | 0.138 | 1.227 | 2.298 | 2.090 |
| isolated | 7,380,155 | 41,000.31 | 0.120 | 1.290 | 2.438 | 2.160 |

Both runs had **zero failed requests, retries and admission rejections**. All
accepted exchanges completed, active count returned to zero, peak admission was
100, and all 128 workers were observed and reused. The response Future is awaited
inside each actor; the actor cannot execute another receive concurrently.

HTTP exchange latency runs from request write to response body receipt inside
the client coroutine. Client cycle latency also includes scheduling of that
coroutine and completion delivery. The cycle figure is the more conservative
client-side average; both are below the earlier approximately 4 ms goal. Python
client loop lag p99 was approximately 2 ms, so these runs may be client limited.
This is a JVM/Temurin 25 measurement, not a Graal Native Image or LLVM AOT result.

The queue target is an average, **not an every-request latency guarantee**.
The sampled queue tails, including maxima and counts over 3 ms, are retained in
`queue-tail.json`. Correlated randomly sampled native Oreslang-OTel records are
in each `metrics.jsonl.gz`, with exact decomposition checks performed by
`scripts/summarize-profile.py`. Shared has 7,845 complete sampled traces;
isolated has 7,424. Metadata records clean source commits, generated fixture and
driver hashes, JVM options and machine details.

“Isolated” means private actors in the current JVM runtime. These results do not
prove OS-process or physically separate-heap isolation. Each exchange still uses
the existing single-owner transfer/claim capability protocol.

## Cause and fix

The original baseline measured approximately 7.26 ms mean HTTP queue wait.
Parallel route matching alone did not remove the bottleneck: a thread dump
showed most CONTROL threads blocked in `ActorRuntime.send`, with the owning sender
waiting on the global fair multi-channel select coordinator. This serialized
unrelated actor mailboxes and created a lock convoy.

Inbox and continuation channels now use runtime-private bounded channel storage
and per-mailbox synchronization. They reject guest `select` descriptors, so they
cannot undermine general multi-channel select atomicity. General guest channels
and actor output streams retain the existing select substrate. Actor execution
leases, mailbox quotas, lifecycle synchronization and ownership transfer remain
in force. A regression test holds the general select coordinator and proves
mailbox progress on another thread; concurrent producer tests check bounded FIFO
and close/drain semantics.

The matched four-lane exploratory run immediately before the mailbox change
measured 7.864 ms queue wait and 11,506 responses/sec; the first mailbox pilot
measured 0.135 ms and 39,494 responses/sec. These pilot configurations are not
identical to the original 32-worker baseline; the final sustained results above
measure the complete combined change with 128 workers.

The HTTP transport now uses Netty NIO instead of JDK HttpServer stream reads and
writes on virtual threads. Additional changes correct Future boundaries and
reduce interpreter metadata/guard-scanning overhead. The earlier pilot report
has reproduction commands and describes the remaining legacy stdlib I/O scope.

## Exact-source CI

Private destination visibility was verified before transfer. The GitHub connector
mirrored exact Git trees into a temporary branch of `led-dynamo/leddy-e2e`, without
cross-organization credentials. Its own GITHUB_TOKEN checked out local snapshots.
The restore step reconstructed the source commits and verified all tree hashes.

[Executed validation run](https://github.com/led-dynamo/leddy-e2e/actions/runs/39155323092)
passed **242 runtime tests**, router semantics, **102 integration checks**, eight
driver tests and two telemetry tests. `ci-receipt.json` records the exact source
commits/trees and private mirror. This is supplementary evidence; origin repository
merge checks were not changed or bypassed. Origin run 39154680797 failed before
executing any steps.

This report is a documentation-only follow-up to tested Spin commit
`82f9368f40a6cfe6644c5ac28b7b2267bba7095f`. Both benchmark runs and CI tested that
same executable source tree.
