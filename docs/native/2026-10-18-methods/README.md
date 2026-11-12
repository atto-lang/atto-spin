# Native imported class-method benchmark and validation

The compiled actor calls an imported module whose scalar class method reads its
private status field. This exercises native method resolution, receiver loans,
private-member access and stack object lifetime. HTTP parsing/routing/formatting
still resides in the C++ adapter; this is not full Spin or OTel lowering.

100 persistent connections, 128 reused actors, four native carriers, ten-second
warmup and 180 measured seconds on arm64 macOS:

| Measurement | Result |
|---|---:|
| Measured responses, including drain | 11,306,601 |
| Completed inside measurement window | 11,306,501 |
| Throughput | 62,813.89 requests/sec |
| Mean HTTP exchange | 0.809249 ms |
| Mean full client cycle | 1.591698 ms |
| HTTP p50 / p95 / p99 | 0.768958 / 1.046709 / 1.319166 ms |
| Mean parsed-request to actor queue, including warmup | 0.00796918 ms |
| Mean actor callback, including warmup | 0.000554118 ms |
| Accepted / completed HTTP / completed callbacks, including warmup | 11,967,208 each |
| Failures / retries / mailbox retries / transport errors | 0 / 0 / 0 / 0 |
| Actors observed / peak connections | 128 / 100 |

Benchmark source `55b0c7bdae2e51279f967564a04c07c6c878e41c`, tree
`cc608aa4b21563f13d5099d9e0cf48f7abdf25b6`. [Metadata](metadata.json),
[build receipt](build-receipt.json), [raw result](result.json), and
[server output](server.log) retain the evidence. Every accepted exchange has one
matching actor callback and response. Client metrics exclude warmup; server
phase means include it. Means do not guarantee per-request tails.

No tests, builds or other load generators ran during measurement; source mirror
and delivery preparation did. This desktop measurement does not isolate the
cause of throughput differences from earlier runs. It is not an identical-workload
JVM comparison: guest await/cooperate, shared/private placement, the real Spin
route graph and oreslang-otel are still missing from native execution.

The exact-source [Linux run](https://github.com/led-dynamo/leddy-e2e/actions/runs/39164097906)
passed 431 native CTests, 21 Java tests, 45 module cases (12 identical Java/native
executions), 33 class-method cases (11 identical executions), and five repetitions
each of three native HTTP ownership/Release/sanitizer tests. Qualified imported
class construction is native-only because the current Java runtime rejects it.
The [CI receipt](ci-receipt.json) records source and private connector mirror
identities. No cross-org credentials were added; origin required checks remain.

The current LLVM pin additionally includes the later borrow audit: 421 local
native CTests and 154 Java tests passed with an identical 18-case loan contract.
That audit is locally validated and is not covered by the earlier CI run or
benchmark hashes. LLVM remains zero-GC and full AOT. The actual Spin package
continues to be marked unsupported and is checked against exact rejection probes.
