# Native HTTP with statically imported guest helpers — 2026-10-18

The actor now calls public/private Oreslang helper functions from an imported
module, compiled into the native artifact ahead of time. Its request counter
still lives in the actor-owned heap. All actors and the I/O reactor stay in one
OS process; invocation and completion use bounded memory mailboxes/queues.

100 persistent connections, 128 reused actors, 4 native carriers, 10-second
warmup and 180 measured seconds on arm64 macOS:

| Measurement | Result |
|---|---:|
| Measured responses including drain | 11,855,825 |
| Responses completed within measurement | 11,855,725 |
| Throughput | 65,865.14 requests/sec |
| Mean HTTP exchange | 0.771224 ms |
| Mean complete client cycle | 1.517963 ms |
| HTTP p50 / p95 / p99 | 0.748333 / 0.906208 / 1.136500 ms |
| Mean parsed-request → actor queue, including warmup | 0.00770785 ms |
| Mean actor callback, including warmup | 0.000522566 ms |
| Accepted / HTTP completed / scheduler completed, including warmup | 12,514,948 each |
| Failures / retries / mailbox retries | 0 / 0 / 0 |
| Actors observed / peak connections | 128 / 100 |

Exact LLVM source commit `0e18358596959e4ad7f7bbc32ad9f4f32833b42a`,
tree `98b0010b324fb43887029ce0222505b804c0cada`. The
[build receipt](build-receipt.json) records the binary/source hashes and Clang 23
toolchain. [Raw results](result.json), [metadata](metadata.json) and
[server output](server.log) preserve the measured evidence.

This remains a lighter native integration workload, not full Spin or an
identical-workload JVM comparison. Relative module functions now lower, but
Spin's exported objects/methods, String/Array APIs, guest await/cooperate and
Oreslang OTel modules remain unsupported. The native benchmark formats/routes
HTTP in the trusted C++ adapter. It does not claim shared/private source actor
parity or hardware heap isolation. See [the roadmap](../README.md).

Every successful response was actor-owned; exact HTTP and scheduler counts match.
Client results exclude warmup; server phase means include it. Means do not impose
a per-request tail guarantee. Source/mirror preparation and GitHub delivery ran
during the measurement, and two lightweight compiler rejection probes also ran; no local build, full
test suite or other load generator did. The result is a successful native integration baseline, not a controlled
attribution of the small throughput difference from the earlier compiler build.

The exact-source [Linux CI run](https://github.com/led-dynamo/leddy-e2e/actions/runs/39161058984)
passed **429 native tests, 21 Java ownership tests, all 45 module cases with 12
identical Java/native executions, and five repeats each of three native HTTP
ownership/Release/sanitizer tests**. [The CI receipt](ci-receipt.json) records both
source trees, mirror commit/tree and executed job. Private destination verified
before connector mirroring; no cross-org secrets/tokens. Billing-blocked origin
checks still executed zero steps and have not been bypassed.
