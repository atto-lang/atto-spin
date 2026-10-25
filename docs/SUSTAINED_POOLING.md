# Sustained Spin workload and reusable actors: verification contract

## Measurement protocol

Use `scripts/sustained-client.py` with `--duration 180`, separately for
100, 1,000, and 10,000 closed-loop clients and both actor modes. Each client
issues another HTTP/1.1 request only after consuming the complete prior body.
Client and server should run on separate hosts or jobs with a reachable address;
when loopback is unavoidable, report CPU contention explicitly. Warm up before
measurements, then collect at least three independent 180-second trials per
configuration, recording runner type, OS, CPU, Java version, source SHA, and
all server-side counters. Capture server RSS/CPU, GC, queue depth, active
exchanges, worker creation, worker completion, and total accepted/completed.

The client records successful requests per second, mean/p50/p95/p99 full
response latency, errors, status codes, persistent connection reuse, and total
requests. A 100% result requires every attempted request to return a validated
200 with correct body and actor mode. Errors are not retried. High load (10,000
clients) may exceed GitHub-hosted runner file descriptors, CPU or memory; report
such limits rather than claiming server failure or success.

**Important:** HTTP connection reuse is *not* actor reuse. The sustained
client works against the current fresh-actor implementation. Until the runtime
has reusable worker dispatch, its metrics must not be called pooled-actor results.

## Required implementation before declaring pooled actors

The HTTP runtime currently binds claimable exchange authority to a spawned
request actor. A response may complete before the actor lifecycle ends. For a
persistent actor to serve subsequent requests safely, the runtime needs a
distinct, *one-shot* exchange finalization operation that:

1. Atomically closes the old exchange, releases the HTTP admission slot once,
   and invalidates all claim tokens, body streams, and response capabilities.
2. Keeps the actor alive without retaining references to the old exchange.
   Reusing a token, a completed response, or borrowed request data must fail.
3. Delivers the next exchange as a fresh actor mailbox message, with request
   and cancellation identity tied to an incarnation/generation. No overlap of
   actor execution is allowed; outstanding message lifetimes still obey the
   actor scheduling contract.
4. Defines bounded worker mailboxes and backpressure independently of TCP
   backlog, socket maximum, exchange admission, and worker count.
5. Handles timeout, cancellation, user exceptions, panic, shutdown, and
   partial/streaming responses by retiring that exchange exactly once.
   Panicked workers must be replaced, without replaying a possibly performed
   external effect.
6. Supports shared and isolated worker modes without transferring mutable
   exchange data across actor isolation boundaries.
7. Exposes runtime counters `workers_created`, `workers_alive`,
   `worker_reuses`, `exchange_completed`, and `active_exchanges`.
   Pooling is proven only when successful requests exceed worker creations,
   `worker_reuses > 0`, and all exchanges drain to zero.

Before a performance claim, add deterministic failure/race tests for
finalization vs cancellation, finalization vs shutdown, duplicate completion,
stale tokens, request cross-talk, actor panic/replacement, backpressure, and
stream body termination. Preserve existing actor-per-request mode as a baseline.

## CI and funded test-org provenance

If the source org cannot run Actions, mirror the *exact* PR-head Git tree to a
temporary test-org repository branch. GitHub token permissions are repository
scoped; do not try cross-org checkout of private source using `GITHUB_TOKEN`.
Record source head commit/tree SHA, mirror commit/tree SHA, and compare the
complete tree SHA and all submodule dependencies before accepting results.
Do not claim tests ran just because a workflow file was committed: verify run
URL, conclusion, exact source tree, logs, and uploaded JSON artifacts.

Each 180-second trial requires a runner for at least three minutes **plus**
startup and shutdown time; a six-case, three-repeat matrix is at least 54
minutes of measured time before overhead (more if run serially).
