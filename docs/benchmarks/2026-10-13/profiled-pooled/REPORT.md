# Spin reusable-actor profiling — 2026-10-13

The dominant delay is the queue ahead of the serial supervisor's dispatch loop.
At 100 clients, admission-to-dispatch accounts for approximately 98.9% of the
sampled admission-to-response-continuation interval; at 10,000 clients it accounts
for approximately 99.99%. Routing/dispatch itself remains about 0.296 ms per
request, limiting the serial path to roughly 3,300 requests/sec before other
supervisor work. More reusable handler actors cannot remove this serial limit.

## Three-minute measurements

Every run used 180 seconds of measured load after ten seconds of warm-up,
32 shared plus 32 isolated workers, half the clients per mode, HTTP keep-alive,
and no retries. All measured requests succeeded and all server counters drained.

| Run | Concurrency | Measured requests, including final drain | Mean client latency | Completed within window/sec |
|---|---:|---:|---:|---:|
| baseline-100 | 100 | 604,853 | 29.709 ms | 3359.74 |
| sampled-100 | 100 | 594,221 | 30.241 ms | 3300.67 |
| sampled-10000 | 10,000 | 588,174 | 3060.131 ms | 3212.08 |

Both actor modes had essentially identical client means. The 100-client
instrumented mean increased by 1.79% versus baseline in this single comparison.
This is observed run overhead, not a statistically established universal cost:
the fixture adds reads/clocks on every request, sampled telemetry exports, and
cold core recording. An earlier uninstrumented run averaged 31.4 ms, showing
host/run variability. The baseline was recorded from a dirty instrumentation
checkout; its original fixture and driver hashes are in metadata. Instrumented
runs used the clean `b816109` commit.

## Warm native telemetry

Bernoulli sampling with a fixed seed and probability 1/1000 produced 553 complete
request records at 100 clients and 548 at 10,000. Export uses the native pinned
`oreslang-otel` implementation and standard-library stdout. No request bodies are
logged. Raw sampled logs are included as `stdout.log.gz` alongside JSON summaries.

| Mean elapsed interval | 100 clients | 10,000 clients |
|---|---:|---:|
| `actor.prepare` | 0.0082 ms | 0.0080 ms |
| `admission.to_claim` | 30.1780 ms | 3059.2392 ms |
| `admission.to_dispatch` | 29.8726 ms | 3058.9362 ms |
| `admission.to_response_continuation` | 30.2063 ms | 3059.3165 ms |
| `mailbox.move_to_claim` | 0.0155 ms | 0.0141 ms |
| `response.await` | 0.0201 ms | 0.0693 ms |
| `routing.dispatch` | 0.2958 ms | 0.2954 ms |

These intervals overlap and must not be summed. Response-await includes I/O and
continuation scheduling; the client may receive bytes before the continuation.
Admission-to-dispatch includes supervisor queueing and small pre-dispatch reads.
The sampled request has not exported any telemetry before these clocks are
captured, but exports for earlier requests can delay later work.

At 10,000 clients, mean response-await is 0.0693 ms versus p95 0.0356 ms because
of outliers; the complete phase statistics retain that distinction. It remains
a small contribution compared with the three-second supervisor queue.

## Core diagnostics and limits

Core performance/debug buffers saturate at 8,192 events and describe cold start,
not the three-minute warm window. At 10,000 clients the performance buffer fills
with executor/admission events before actor-dispatch events: that is truncation,
not evidence of zero dispatch work. Do not extrapolate these cold distributions.
Core stdio timings also exclude guest JSON construction. Warm telemetry spans
the measured interval and its summarizer validates all seven records per ID.

This is a local JVM, Java-carrier, closed-loop test, not an AOT/native-carrier or
physical-isolation measurement. Client and server share the host. Client p99
loop lag was 0.182 ms at 100 clients and 2.003 ms at 10,000; it cannot explain the
observed supervisor queue. Native OTLP and distributed trace propagation are
not provided by this exporter.

Reproduce using [the profiling guide](../../../PROFILING.md).

## CPU attribution

A separate 30-second measured diagnostic at 100 clients used JFR `profile`
settings, starting ten seconds after JVM launch for thirty seconds. This is
approximately warm but its clock does not exactly match the client warm-up.
It is excluded from the overhead comparison. All 97,462 requests succeeded.
Of 2,418 execution samples, 2,395 were on `ores-control-plane-*` threads (99.0%).
`expressionContainsPotentialSuspension` appeared in 1,020 samples (42.2%);
`Objects.hashCode` appeared in 932 (38.5%). These inclusive percentages overlap
and are not CPU utilization percentages. Many stacks were truncated, so the
specific caller responsible for hashing is not yet established. Do not infer
that every hash sample is suspension analysis.

The source repeatedly traverses callable bodies in
`OresEvalRootNode.Evaluator.methodContainsPotentialSuspension` and
`functionContainsPotentialSuspension`. The measured hot path is therefore the
supervisor's interpreted dispatch work, with repeated suspension analysis a
concrete optimization candidate. A safe follow-up should avoid repeated
analysis of stable declarations, respecting imported methods, dynamic bindings,
actor/module contexts, and async semantics. Hashing needs deeper attribution.
No runtime optimization is claimed by this instrumentation PR.

The initial JFR launches failed before serving traffic because the JVM writes
a startup banner before the fixture port. The harness now ignores non-port
startup lines within its existing 30-second deadline; the successful diagnostic
uses that correction. The failed launch directories are retained locally.

## Validation

Router semantic checks and all 55 Spin integration checks passed on the pinned
runtime. Nine Python harness/summary tests passed, including rejection of
incomplete or duplicate sampled telemetry. Both complete three-minute sampled
logs passed correlation validation.
