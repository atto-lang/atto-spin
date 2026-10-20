# Actor-owned responses: sustained comparison

Measurements captured 2026-10-13; report prepared 2026-10-15. All three runs use
100 persistent connections, one request in flight per connection, ten seconds
warm-up and 180 measured seconds. Each mode uses 32 reusable actors. Every
response must have the expected body, actor mode, worker identity and reuse
marker. No retries; zero client failures or server admission rejections; all
accepted requests completed and active counters drained to zero.

| Mode / control workers | Successful measured requests | Completed/sec | Mean ms | p95 ms | p99 ms |
|---|---:|---:|---:|---:|---:|
| shared-control1 | 2,417,489 | 13,429.94 | 7.375 | 8.000 | 12.332 |
| isolated-control1 | 2,443,920 | 13,576.78 | 7.307 | 7.877 | 12.716 |
| shared-control4 | 2,189,398 | 12,162.77 | 8.158 | 10.008 | 13.650 |

The throughput target of 10,000 requests/sec was met. The 4 ms mean target was
not met. At 100 continuously active clients, 4 ms implies approximately 25,000
requests/sec. One control worker reduced shared mean latency 9.6% versus four
in these sequential runs. Shared and isolated results differ by under 1%; this
is not evidence that isolated actors are intrinsically faster. Runtime defaults
remain unchanged. These are Temurin JVM interpreter measurements, not guest AOT
or native-image measurements; JVM isolated actors do not establish physical
address-space isolation.

The earlier mixed result was 9.376 ms / 10,594 requests/sec. These single-mode
results are around 21–22% lower latency, but that historical run used 32 workers
per mode (64 total), a different runtime revision, and a different host interval.
Use the same-code shared control for the scheduler-setting comparison.

## Where time goes

Warm Oreslang telemetry samples (one request in 1,000, deterministic sampling)
show these means. Exactly seven metric records per sampled request ID were
verified, separately from the core logger's bounded cold-start events.

| Phase | Shared / 1 control | Isolated / 1 control | Shared / 4 control |
|---|---:|---:|---:|
| Admission to dispatch | 7.079 ms | 7.112 ms | 7.933 ms |
| Routing/dispatch | 0.067 ms | 0.067 ms | 0.074 ms |
| Mailbox move to claim | 0.019 ms | 0.017 ms | 0.017 ms |
| Actor preparation | 0.005 ms | 0.005 ms | 0.006 ms |
| Response await | 0.026 ms | 0.024 ms | 0.024 ms |

These intervals overlap; do not sum them. The evidence points to the serial
supervisor dispatch path and its queue, rather than actor mailbox contention,
as the next optimization target. Reducing repeated evaluator/frame traversal
and control scheduling helps, but reaching 25K/sec requires substantially more
dispatch capacity. A compiled dispatch path or safe partitioning of supervisors
is a follow-up; neither is implemented or claimed by this change. Actor callbacks
remain exclusive per actor while different actors run concurrently.

## Ownership and validation

Framework 404/405/414/OPTIONS/error replies now dispatch to shared response actors.
Buffered supervisor/middleware responses transfer their exchange through a
mailbox to a response actor in core HTTP. Root streaming is rejected. Transport
parse errors, admission rejection and crash/deadline cleanup remain native safety
paths. See [the ownership contract](../../../ACTOR_REQUEST_OWNERSHIP.md).

123 focused runtime tests, router semantics, 102 Spin integration checks, four
load-driver tests and the profile-correlation test passed locally. Route caching
and inline synchronous scheduling experiments failed to show a reliable benefit
and were removed; they are not part of the retained implementation.

## Reproduction and evidence

Use the commands in [the ownership guide](../../../ACTOR_REQUEST_OWNERSHIP.md)
with `JAVA_TOOL_OPTIONS=-Dores.runtime.control.parallelism=1`; use `=4` for the
control. The runtime, router and otel revisions, Java options/version, fixture
and driver hashes, and clean Spin revision are recorded in each metadata file.
All measured runs use Spin `8a21d0e652330ac49e23c48eb8f576afd47097dd` and runtime
`797a4a51f716761590f0cb02ec085029e18f26de`.

This was one sequential run per configuration on a shared development Mac,
not a randomized study or an idle dedicated server. The shared/control1 client
had a maximum event-loop pause of 253 ms (p99 0.669 ms); isolated/control1 was
2.277 ms maximum (p99 0.196 ms), and shared/control4 was 2.173 ms maximum (p99
0.257 ms). Tail results include host/client noise. Numeric latency samples are
retained in the workspace outputs; their SHA-256 hashes, compressed raw telemetry,
aggregate latency results, process samples and drained server counters are
preserved alongside this report. Requests started during measurement and drained
afterward count toward latency/success; throughput counts only completions inside
the 180-second measurement window.
