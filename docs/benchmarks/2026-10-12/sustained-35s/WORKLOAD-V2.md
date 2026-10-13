# Sustained HTTP actor scheduling workload V2

The historical 2026-10-12 throughput results used HTTP response awaiting but did
not explicitly require a suspend-capable checkpoint or `rt cooperate`. This
new fixture intentionally measures **more realistic actor scheduling** and
requires a fresh set of benchmark results; do not mix V1 and V2 values.

## Identical per-request work in all four handlers

The following happens once for **every** fresh or reused shared or isolated
actor request, with no special case for a pooled worker:

1. `suspends receive(...)` accepts a scheduling-aware message turn.
2. `self.checkpoint()` calls the actor's `suspends checkpoint(): int`
   **exactly once**.
3. Inside that checkpoint, `rt cooperate;` executes **exactly once**, yielding
   to the actor's cooperative scheduling machinery and resuming the continuation.
4. Upon checkpoint return, the actor writes `X-Work-Verified: 1` (or zero
   on failure). The HTTP client validates `X-Work-Verified: 1` on **every**
   successful response, along with status 200, exact body, and actor-mode header.
5. `await request.respond(...)` performs **exactly one explicit await** per
   actor receive call.

Only lifecycle differs: a fresh handler executes `self.end()` after response
completion; a reused handler returns to its mailbox without ending.

**Language nuance:** `suspends` is a callable effect contract, **not an
additional standalone scheduling operation**. The concrete cooperative
suspension is `rt cooperate`, and the separate asynchronous suspension is
the awaited response. Thus the workload has one suspend-capable helper
invocation, one cooperative handoff, and one await, rather than claiming three
independent runtime yield points.

## Validation gates

- `tests/test-sustained-fixture.py` checks exact AST-shaped source layout,
  one checkpoint invocation, one `rt cooperate`, one `await`, the response
  checkpoint header, and fresh-vs-reused body parity excluding `self.end()`.
- `tests/test-sustained-client.py` validates keepalive and rejects a response
  without a confirmed checkpoint.
- A funded mirror verifies each changed Spin file by **Git blob SHA** and
  reconstructs the unchanged Java runtime as an **exact Git tree**, without
  cloning private sources across organizations.
- Real client/server jobs execute both fresh and reused actor traffic with
  checkpoint response validation, recording 35-second throughput and latency,
  successful/requested counts, transport errors, 503s, and reuse counters.

The v2 test is not a CPU-cost-isolated microbenchmark: HTTP response handling,
application routing, and actor scheduling remain in the timed path. Keep
client load, HTTP transport limits, pool size, runtime build, and JDK flags
identical in each fresh/reused pair. Favor multiple alternating-order trials
before claiming small speed differences are significant.
