# Spin actor-reuse benchmark and HTTP pooling: hardening audit

## 2026-10-13 follow-up: linearizable pooled admission and release

**Finding:** Admission previously held the per-worker
`ConcurrentHashMap.computeIfPresent` key lock while checking the
64-entry `Set.size()`, but completion removed states directly from
the concurrent set via `inFlight.get(worker).remove(state)`. Those
mutations were not serialized with admission and could race against
weakly consistent concurrent-set size observation.

**Fix:** Java/GraalVM [PR #759](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/759)
now uses `releasePoolAdmission`, a keyed `computeIfPresent` removal,
and invokes it from `Handler.untrack`. Worker termination still
atomically removes the registry key before aborting its remaining
states; late release does not recreate a removed worker.

**Regression:** A new 5-round admission churn test races 64 releases
against 256 new registrations on the same 64-capacity worker, verifies
that the remaining count never exceeds capacity, replenishes available
slots, checks that further registration is FULL, and verifies
worker-removal tombstoning against late release. A separate deterministic
latch test holds admission inside the worker's per-key capacity check,
then proves a concurrent release must wait for the same key lock.

Current Java source `e9f20f611d5a0a8225aa11ecc5c2a8f07a5bd935`, Git tree
`4fcbc76a1ed926f8d454524c8c40dce37c9039c7`. The funded CI
mirror reproduced this exact tree SHA. [CI run #38450604235](https://github.com/zed-pkg-test/java-app/actions/runs/38450604235)
passed **19/19 HTTP JUnit tests, zero failures/errors**, including the
deterministic latch regression. The two 35-second shared/isolated
fresh/pooled benchmark jobs were still running when this evidence was
recorded. The preceding [run #38450209024](https://github.com/zed-pkg-test/java-app/actions/runs/38450209024)
passed all three jobs but tested the earlier 18-test revision.

The gate proves bounded per-worker HTTP exchange registration under
the exercised races; it does not prove 15-minute retained heap,
10,000-client admission recovery, actor CONTROL priority latency, or
GraalVM Native Image/LLVM parity.

---

## 2026-10-13 follow-up: capacity-aware routing and real HTTP recovery

Java/GraalVM [PR #759](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/759)
now chooses a pooled worker that actually has room under the 64-exchange
per-worker limit. It starts searching at a rotating cursor, skips full
workers, preserves fairness, and responds 503 only when the pool has no
admissible worker. Handler locking serializes dispatch decisions; the
per-worker `ConcurrentHashMap.computeIfPresent` gate still owns the
atomic reservation and protects against worker death.

Regression coverage includes a deterministic slot-selection test with
saturated and free slots, negative and near-overflow cursors, complete
exhaustion, and recovery after slot release. A real HTTP test sends 64
held requests to a one-worker pool, requires the 65th to receive 503,
then verifies all timed-out exchanges are released and the original
worker serves a subsequent 200 response without being replaced.

**Exact source:** `e5171d6f80053924567886ccf6f8def7df85f794`;
Git tree `6f8c8824c6c6de6b07fabd753a130dac5d217e6a`. The
funded mirror reproduces that Git tree exactly.
[CI run #38427100237](https://github.com/zed-pkg-test/java-app/actions/runs/38427100237)
**passed all three jobs**: 17 targeted Java HTTP JUnit tests, zero failures
and errors, and two 35-second fresh/pooled comparisons with 100 concurrent
clients, separately for shared and isolated actors.

| Mode | Strategy | Successful requests | req/s | Mean ms | p95 ms | p99 ms |
|---|---|---:|---:|---:|---:|---:|
| shared | fresh | 39,097 | 1114.203 | 89.603 | 103.732 | 186.249 |
| shared | pooled | 39,072 | 1113.622 | 89.660 | 102.776 | 170.629 |
| isolated | fresh | 26,084 | 742.527 | 134.344 | 162.112 | 245.975 |
| isolated | pooled | 25,736 | 732.371 | 136.199 | 156.073 | 284.305 |

All 129,989 measured requests succeeded: no admission rejections,
zero active server exchanges at shutdown, and substantial pooled worker
reuse (100 workers created per mode). This is one fresh-first paired
sample per mode with clients/server sharing the CI runner, **not**
proof of a stable throughput advantage. In particular, isolated pooled
p99 latency was worse in this run.

The saturation/recovery behavior was separately verified in the
end-to-end Java JUnit gate, not by this non-saturating 100-client run.

**Scope:** This bounds HTTP exchange lifetimes, not ordinary actor
mailboxes. The underlying `ActorRuntime` already enforces the
configured `maxMailboxMessages` for user messages and separate
`INTERNAL_CONTINUATION_SLOTS` headroom; priority CONTROL dispatch is
separate. Multi-worker live-socket fairness across mixed workloads,
mailbox-stress parity, repeatable 1000/10000-client overload, sustained
heap/GC profiling, Native Image and LLVM remain open gates.

---

## 2026-10-13 follow-up: bounded pooled-worker HTTP admission

The current Java/GraalVM PR #759 adds `MAX_POOLED_INFLIGHT_PER_WORKER = 64`.
Admission uses `ConcurrentHashMap.computeIfPresent` for per-worker
reservation and returns `FULL` when saturated and `WORKER_GONE`
if the actor has already terminated. A full worker's newly transferred
exchange is aborted with HTTP 503 without canceling that worker.
`workers_rejected` exposes the count of these pool-specific rejections.

A new concurrency regression in Java commit
`a2b7eb47ec45007e28a9c5de826ce3aacaa6a777` races 256 reservations for a
64-exchange capacity and requires exactly 64 admissions and 192
rejections. It also exercises capacity recovery after removal and
proves the worker's registry is not recreated following termination.

The source Git tree `c5a94ddd66f648a49a7291a1c4c031fb9ff2537f` was
reconstructed identically in the funded CI mirror.
[Run #38423621658](https://github.com/zed-pkg-test/java-app/actions/runs/38423621658)
is the exact-source verification gate; results must be checked
separately from earlier green CI runs.

**Limitations:** the 64-request quota bounds tracked HTTP exchange
lifetimes per pooled actor, but it is not a universal actor mailbox
quota. Strict round-robin dispatch can still reject a saturated slot
even if another worker has capacity. A per-worker quota is not a
global fairness scheduler, and Native Image/LLVM, memory retention,
high-client-count overload behavior and transport pressure remain
separate gates.

---

## 2026-10-13 follow-up: guaranteed shutdown cleanup and admission accounting

Java/GraalVM [PR #759](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/759)
remains a draft. The historical Spin [PR #8](https://github.com/ores-truffle-oreslang/oreslang-spin/pull/8)
is merged; this follow-up documents the newer unmerged Java runtime tree without
claiming the existing Spin benchmarks verify that tree.

**Current Java pin:** `c873562561676912d686415245aa60da3f0fdd21`
(Git tree `c302d640819bdf9ab00b8e24eeff1adb68cac3f4`).
The funded test mirror was verified to have the identical Java Git tree.

Changes in this revision:

- Replace `NativeHttp.close()`'s `io.shutdownNow()` with orderly executor
  shutdown after stopping listeners, allowing already-admitted cleanup tasks
  to run their `finally` and admission-release paths.
- If the executor has stopped accepting new work, schedule each terminal
  exchange's cleanup on an independent virtual thread rather than doing
  socket I/O on an Oreslang actor carrier or timer thread.
- Make graceful shutdown idempotent, including after the listener is closed;
  reject/cleanup fallback occurs outside the server monitor.
- Fix post-admission exceptions in `Server.receive`: release through
  `State.abort` rather than manually releasing the semaphore, including
  the `IllegalArgumentException` branch.
- Add focused tests for accepted versus rejected cleanup and repeat shutdown.

**Current exact-source evidence:**
[CI #38421771486](https://github.com/zed-pkg-test/java-app/actions/runs/38421771486)
passed **all 3 jobs** on `c873562561676912d686415245aa60da3f0fdd21`
(tree `c302d640819bdf9ab00b8e24eeff1adb68cac3f4`): 13 JUnit
HTTP regressions, 0 failures/errors, and two 35-second 100-client
fresh-versus-pooled benchmark comparisons.

| Mode | Strategy | Successes | Successful req/s | Mean ms | p95 ms | p99 ms |
|---|---|---:|---:|---:|---:|---:|
| shared | fresh | 26,676 | 759.354 | 131.376 | 182.347 | 259.295 |
| shared | pooled | 26,357 | 750.336 | 132.942 | 156.307 | 255.174 |
| isolated | fresh | 38,065 | 1084.685 | 92.036 | 109.679 | 150.927 |
| isolated | pooled | 38,242 | 1089.797 | 91.612 | 109.584 | 136.786 |

All 129,340 measured attempts succeeded. Each configuration reported zero
HTTP rejections and zero active exchanges at shutdown. The pooled cases
created 100 workers each and reused them for subsequent requests.

This is a **single**, same-runner, fresh-first comparison for each actor
mode, not evidence of statistically significant throughput improvement.
GC allocation, retained heap under multi-minute load, high-concurrency
1000/10000-client behavior, and native backend parity remain open.

The HTTP server still relies on JDK virtual-thread-backed blocking transport;
Native Image/LLVM equivalence, mailbox bounds, deterministic race scheduling,
and multi-minute heap/GC stabilization are not verified by these gates.

---

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

The first callback-retention fix was Java commit
`1e5a86aca91e80ef69761adafceb90414b922ffa` with Git tree
`d584d30233163e1acd97aa9f01891ccf373acc0c`.
Its exact-source [Actions run #38331019778](https://github.com/zed-pkg-test/java-app/actions/runs/38331019778)
**passed** targeted regressions and both 100-client, 35-second sustained comparisons.
See the next section for the newer race fix and current pin.


## Second follow-up: dispatch registration versus release

A separate race existed between `moveToPooled()`, registration in the worker's
`inFlight` set, and setting `poolHandler`. The HTTP deadline/close path could
finish and release the exchange between those steps. Cleanup would observe a
null handler and skip unregistration, after which dispatch could insert the
already-released `State` into the long-lived worker registry.

Java PR #759 now synchronizes the terminal-state check, handler association,
and in-flight registration on the exchange state monitor. A terminal exchange
is not registered. This prevents registration after request-local cleanup.

The timeout/healthy-reuse integration test additionally requires
`workers_inflight == 0` after the healthy response, complementing the existing
successful-response and worker-death regressions.

Current Spin `POOL_SOURCE_REF`:
`0f98498ad7f7d1a780fcf71bcffe01572b307d4b`.
The exact Java source tree SHA is
`96b00bf8469afe8044378cce20f93dc158fec5f4`.
That tree was reconstructed in the funded test repository with a matching
SHA, including the revised Java runtime and regression test.

[GitHub Actions run #38339736951](https://github.com/zed-pkg-test/java-app/actions/runs/38339736951)
**passed all three jobs** on the newer exact Java tree. The real-socket
gate ran 11 JUnit tests (0 failures/errors) and source/fixture regressions.
The 35-second sustained 100-client comparisons also passed for shared
and isolated actor modes, with no request failures/rejections and zero
active server exchanges after shutdown.

| Mode | Strategy | Successes | Successful req/s | Mean ms | p95 ms | p99 ms |
|---|---|---:|---:|---:|---:|---:|
| shared | fresh | 38,103 | 1085.779 | 91.943 | 110.282 | 177.624 |
| shared | pooled | 39,170 | 1116.236 | 89.439 | 103.097 | 159.182 |
| isolated | fresh | 25,290 | 719.848 | 138.553 | 183.603 | 298.242 |
| isolated | pooled | 25,295 | 720.037 | 138.527 | 214.221 | 267.869 |

All rows use tree `96b00bf8469afe8044378cce20f93dc158fec5f4`,
commit `0f98498ad7f7d1a780fcf71bcffe01572b307d4b`.
Single-run, shared-runner comparisons cannot establish a statistically
meaningful throughput advantage; the isolated pooled p95 is worse. The
long-run leak/GC claim needs repeated runs and a direct heap/allocation
profile, not only a zero-in-flight assertion.

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
