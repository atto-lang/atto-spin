# Fresh request actors versus larger pools

Runs captured 2026-10-15; report prepared 2026-10-18. Each configuration runs
100 persistent clients, one request in flight per client, for 180 measured
seconds after ten seconds warm-up. Same pinned JVM runtime, fixture template,
response body and headers, one control scheduler worker, and 1/1,000 sampled
Oreslang telemetry. Runs were sequential in table order on a shared development
Mac, not randomized replicates. This is a useful comparison, not a causal proof
that pool size alone explains the differences.

| Configuration | Successful measured requests | Completions/sec | Mean ms | p99 ms |
|---|---:|---:|---:|---:|
| 32 shared workers | 2,201,289 | 12,228.83 | 8.108 | 19.796 |
| Fresh shared actor/request | 2,087,334 | 11,595.74 | 8.543 | 17.993 |
| Fresh isolated actor/request | 2,266,923 | 12,593.46 | 7.870 | 11.590 |
| 128 shared workers | 2,533,422 | 14,074.01 | 7.045 | 9.230 |

All 9,088,968 measured requests succeeded. No retries or server admission
rejections occurred; every run drained accepted/completed counters with zero
active requests. Fresh mode verified a unique actor ID on every response,
including warm-up, and rejected reuse markers. The actor calls `self.end()` after
responding and emitting any sampled metrics. Pool modes verified all configured
workers were observed and reused. This changes actor lifecycle, not route logic.

The 128-worker run had 13.1% lower mean latency than the 32-worker run. Fresh
shared actors were 5.4% slower than the 32-worker shared pool. Fresh isolated
actors averaged 7.87 ms, but there was no new isolated-pool control in this matrix,
so do not attribute the small difference to isolation. These JVM private actors
are not proof of separate OS address spaces. None of these results reaches 4 ms.

## The two queues

| Configuration | Admission → dispatch ms | Routing/dispatch ms | Mailbox move → claim ms |
|---|---:|---:|---:|
| 32 shared workers | 7.8611 | 0.0742 | 0.0426 |
| Fresh shared actor/request | 8.3351 | 0.0771 | 0.0295 |
| Fresh isolated actor/request | 7.6505 | 0.0716 | 0.0137 |
| 128 shared workers | 6.8810 | 0.0642 | 0.0131 |

Telemetry correlation validation passed for every sampled request (seven metrics
per ID). Intervals overlap; do not add them. The mailbox interval includes
scheduling/startup after transfer and is not a direct queue-depth counter.

`NativeHttp.Server.receive` places admitted exchanges in its pending queue.
The source supervisor accepts and routes requests, then `Handler.dispatch`
selects or spawns an actor and transfers the exchange into its mailbox. Fresh
actors therefore still pass through the same supervisor. Mailbox capacity
exhaustion throws in `ActorRuntime.send`; it does not wait for free capacity.
The successful responses and small mailbox interval do not show saturated
mailboxes here. Most measured latency remains before dispatch, including pending
HTTP acceptance and supervisor scheduling. A larger pool can reduce downstream
contention, but it does not remove that serial dispatch path.

## Serial versus non-serial semantics

The tested runtime at `797a4a51f716761590f0cb02ec085029e18f26de` currently gates all
source receives across await using actor-wide `sourceReceiveSuspended` and
`activeMail`. `hasQueuedWorkLocked` permits ordinary mail only when the active
source receive is no longer suspended. Thus it does not yet implement the user's
intended distinction between serial and non-serial actors. This experiment does
not change those semantics.

The intended non-serial behavior is multiple logical requests in flight within
one actor, interleaved at await/yield boundaries, while retaining exactly one
executing thread per actor. Implementing it safely requires per-request suspended
frames, mail identity and continuation ownership, plus termination/cancellation
handling for all active requests. Simply removing the actor-wide guard would
violate existing assumptions. Serial actors should retain one logical receive
until completion. This semantics gap is distinct from the bottleneck measured
here and is not resolved by creating more actors.

## Reproduction and caveats

Build the pinned runtime and set `ORESLANG_SOURCE_DIR` and `ORES_JAVA` as in the
existing benchmark guide. Run each configuration sequentially:

```sh
JAVA_TOOL_OPTIONS=-Dores.runtime.control.parallelism=1 \
python3 scripts/sustained-load.py --concurrency 100 --seconds 180 \
  --actor-mode shared --actor-lifecycle fresh --sample-every 1000 --core-perf \
  --output /tmp/spin-fresh-shared
```

Use `--actor-mode isolated` for fresh isolated actors, or `--actor-lifecycle pooled
--pool-size 32` / `--pool-size 128` for the shared pools. The driver preserves the
exact generated fixture and records its hash and the clean source revision.
All four measured runs used Spin `eb23e583df` (full SHA in metadata). Seven driver
tests cover pooled connections, fresh identities, reuse rejection, response
validation, sampling and fixture configuration.

Fresh-mode identity verification retains IDs in the client, adding client memory
and bookkeeping. Client event-loop p99 lag stayed below 0.5 ms; max pauses were
7.17 ms (pool32), 32.05 ms (fresh shared), 2.45 ms (fresh isolated), and 2.16 ms
(pool128). Server peak-active counters were 100, 130, 119 and 100 respectively:
server cleanup can overlap the next request after bytes reach the client, so this
counter is not identical to client requests in flight. Do not describe the fresh
runs as capped at 100 server-side live exchanges. Resource samples and latency
hashes are retained; compressed raw telemetry and aggregates are included here.
