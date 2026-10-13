# Spin actor-reuse benchmark and HTTP pooling: hardening audit

Date: 2026-10-12. Draft work:
[Spin PR #8](https://github.com/ores-truffle-oreslang/oreslang-spin/pull/8)
and [Java/GraalVM PR #759](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/759).

## Findings and implemented safeguards

1. **Per-request abort could kill a pooled worker.** `NativeHttp.State.abort`
   previously canceled its assigned actor even when that actor belonged to a
   persistent pool. This made an unrelated concurrent request vulnerable to
   another request's timeout or I/O failure. Request-local aborts no longer
   cancel pooled actors; explicit pool shutdown still does. Also, a
   pooled-dispatch failure now leaves an existing, live worker alone rather
   than canceling it as though it had just been spawned.
2. **Premature shutdown termination.** `Server.shutdown(graceMillis)`
   previously canceled pooled workers **before** waiting for in-flight HTTP
   exchanges. The graceful stop now allows already-admitted requests to
   finish before pool workers are canceled.
3. **I/O executor rejection could strand admission.** When scheduling an
   abort response fails during shutdown, the transport is now closed and
   marked closed before the exchange releases its admission slot.
4. **Pool size could overflow/truncate.** `http.pool_handler` now rejects
   noninteger and out-of-range counts **before** converting them to Java
   `int`; a closed HTTP runtime also rejects new pool registrations.
5. **Load clock began too early.** The sustained-client deadline was
   previously computed before constructing the concurrent worker tasks.
   With many clients, worker construction could erode the 35-second load
   interval. It now starts immediately after task construction, with a
   regression that deliberately delays construction.
6. **Rounded success rates could hide failures.** The client now gates on
   exact integer `attempts == successes`, never on a six-decimal rounded
   percentage.
7. **Standalone runner resilience.** It now validates the number of fixture
   replacements, snapshots Git cleanliness before output creation, and
   reports child-process startup failure without waiting two minutes.

## Follow-up audit: pooled worker termination listener retention

The initial pool implementation attached an actor-termination callback to the
persistent actor's `done()` future **for every transferred HTTP exchange**.
A worker could therefore retain references to completed request states for its
whole lifetime, defeating a principal memory-efficiency benefit of pooling.
A high-throughput worker could accumulate tens of thousands of callbacks.

Java PR #759 now registers exactly one termination callback when each worker
is created. A concurrent registry holds only **currently outstanding**
exchanges. The completion path unregisters each exchange before fulfilling
its response completion future; actor termination removes its registry entry
and aborts only exchanges that are still outstanding. Replacements get
independent registries so an old worker cannot abort a new worker's requests.

New observer: `HttpHandler.workers_inflight` counts live tracked exchanges.
Regressions verify that it returns zero after shared/isolated responses and
that an unexpectedly terminated worker fails its active exchange and is
replaced for a subsequent healthy request.

The updated Java source for this follow-up is pinned in `POOL_SOURCE_REF`:
`1e5a86aca91e80ef69761adafceb90414b922ffa`;
its Git tree is `d584d30233163e1acd97aa9f01891ccf373acc0c`.
The updated source was copied into a funded CI mirror with an **identical
Git tree SHA**. New exact-source verification is tracked at
[Actions run #38331019778](https://github.com/zed-pkg-test/java-app/actions/runs/38331019778).
Its validation status must be checked separately; the earlier completed green
run below predates this callback-retention fix.

## Deterministic regression evidence

[Funded exact-source Actions run #38322191586](https://github.com/zed-pkg-test/java-app/actions/runs/38322191586):
**complete workflow green**. JDK 25, real HTTP sockets, identical Java Git
source tree replay `2494dc52cd41c704432ec15aa658e8703890286b`,
from Java commit `31463d7980f05bae86820ba519a5dc92bd224fc4`.

Java tests: **10 passed, 0 failures/errors** across
`NativeHttpPooledActorTest` and `NativeHttpTest`. New assertions include:

- A request with a deliberately incomplete body times out; a subsequent
  request still uses the **same** pooled worker (no unintended replacement).
- Graceful server shutdown waits for a delayed request body and permits the
  pooled actor to send its successful HTTP response.
- A long integer such as `4294967297` cannot silently become pool size 1.

Python protocol/source-layout tests passed as part of the exact-source gate:
all four handlers use the same `suspends` checkpoint, one `rt cooperate`,
one awaited response, and only fresh handlers terminate themselves;
the client rejects a missing checkpoint header. The load-duration regression
exercises deliberately slow worker creation.

## Fresh baseline after corrections

Both strategies ran 35 seconds of closed-loop admissions with 100 concurrent
clients, no retries, zero admission rejections and all requests successful.
Pooled worker reuse was observed (100 initial workers; reuse counter includes
50 warmup requests).

| Mode | Strategy | Successful requests | Successful req/s | Mean ms | p99 ms |
|---|---|---:|---:|---:|---:|
| shared | fresh | 27,028 | 769.449 | 129.649 | 249.335 |
| shared | pooled | 25,776 | 733.834 | 135.935 | 252.210 |
| isolated | fresh | 26,551 | 755.900 | 131.997 | 268.029 |
| isolated | pooled | 25,890 | 736.354 | 135.429 | 254.081 |

These are *new post-hardening measurements*; do not merge them statistically
with the older V2 table that started its timer before creating client tasks.
The clients and server still share a CI runner, fresh always ran before
pooled, and each cell has only one sample.

## Remaining work before promotion

Repeat fresh/pooled tests in alternating order (at least 3–5 pairs per
concurrency tier), separate client and server CPUs, measure actor allocation,
GC, RSS, CPU and mailbox wait, and check sustained 1,000/10,000-client
transport failure rates with the hardened runtime. Verify JDK Native Image
AOT and LLVM parity separately: these completed tests cover **Java/GraalVM
only**. Keep both PRs in draft until those broader requirements are met.
