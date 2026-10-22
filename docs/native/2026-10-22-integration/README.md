# Reconciled native adapter baseline — 2026-10-22

Exact LLVM head `f29692aeee92d0fa692b5485e1e06a79fc29ad16`, tree
`0e4c76c278e45d2625236308ca48acefe631f2c2`; clean source at build time.
macOS arm64, Clang 23. Compiler/binary/source hashes are in the build receipt.

One native OS process, 100 persistent connected clients, 128 reused actor slots,
four execution carriers, 10 seconds warm-up, 180 seconds measurement:

| Measurement | Result |
| --- | ---: |
| Responses completed in measurement window | 11,848,881 |
| Throughput | 65,827.12 requests/sec |
| Mean client HTTP time | 0.770268 ms |
| HTTP p50 / p95 / p99 | 0.736208 / 0.992791 / 1.388292 ms |
| Mean full client cycle | 1.518848 ms |
| Mean native pending queue interval | 0.00771651 ms |
| Failures / retries | 0 / 0 |
| Actor slots observed | 128 |

HTTP timing and full client cycle timing are distinct measurements; client-cycle
throughput at 100 in flight is consistent with roughly 1.52 ms per cycle. Server
phase means include warm-up. Requests started in the measurement window can
finish just after it; the server receipt records all of them as completed.

This is the existing lighter **native adapter + compiled scalar actor** workload.
It has no guest await/cooperate, full Spin imports, general route payloads or
guest OTel module execution. It is not a shared-vs-isolated actor comparison and
must not be presented as the full framework reaching these numbers. Differences
from older runs are not evidence of a causal performance improvement.

The same source head passed all 504 locally registered CTests, including sanitizer
and real-GPU cases; the manifest gate checked 33 critical tests. Module/bool
source differential checks against Java passed (48/37 native cases, 14/13 Java
executions). The pinned Java runtime separately passed 317 tests in 38 suites;
the exact pinned Spin/route integration passed 102 real HTTP checks.

Origin Actions jobs never started due to billing. The first private fallback
[run 39844532779](https://github.com/led-dynamo/leddy-e2e/actions/runs/39844532779)
found two GCC range-loop warnings treated as errors in the newer allocation JSON
test. Head `ff5f7eaf1217545e579e4ce610d86aaffa46bf7f` fixes those two loop
declarations; its affected test passes locally, and the production runtime code
is unchanged from the benchmark head. The backend pins include this repair.

The exact-tree retry is [run 39845008508](https://github.com/led-dynamo/leddy-e2e/actions/runs/39845008508).
No successful fallback result is claimed until its completed receipt exists;
required origin repository checks remain separate.
