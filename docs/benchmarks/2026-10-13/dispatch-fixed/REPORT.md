# Dispatcher optimization — 2026-10-13

Spin #14 was merged into the reusable-actor parent branch, not main. Runtime
PR #862 caches completed suspension analyses and changes declaration traversal
cycle guards to use AST identity instead of structural record hashing. This
removes repeated interpreter work without changing actor callback exclusivity.

All runs below use the same sampled telemetry fixture, 32 shared plus 32 isolated
workers, half the clients per mode, keep-alive, ten seconds warm-up and 180 seconds
measured. No retries. Changes are JVM runtime analysis/lookup changes, not guest
AOT compilation. Earlier baseline runs are sequential comparisons on the same
host, not randomized statistical trials.

| Runtime | Clients | Successful measured requests | Mean response | Throughput/sec | Mean routing/dispatch |
|---|---:|---:|---:|---:|---:|
| before | 100 | 594,221 | 30.241 ms | 3300.67 | 0.2958 ms |
| before | 10,000 | 588,174 | 3060.131 ms | 3212.08 | 0.2954 ms |
| after | 100 | 1,907,088 | 9.376 ms | 10594.38 | 0.0862 ms |
| after | 10,000 | 1,896,483 | 945.058 ms | 10480.46 | 0.0858 ms |

Every measured request succeeded and all server counters drained. Telemetry
correlation validation requires exactly seven records per sampled request ID.
Request intervals overlap; do not sum admission, dispatch, mailbox and lifetime
intervals. See the previous `profiled-pooled` report for baseline artifacts and
[the profiling guide](../../../PROFILING.md) for reproduction commands.

## Actor concurrency

Each reusable actor processes one request callback at a time, including its await
continuations. The pool allows different actors to execute concurrently. Changing
to one actor per request provides independent request lifetimes, but each request
still passes through this supervisor's routing path first. Actor-per-request
therefore does not inherently remove the measured serial dispatch bottleneck.
No change here allows two threads to execute one actor concurrently.

## Validation and AOT boundary

114 targeted runtime tests passed, covering suspension, Future values, async,
mailbox exclusivity, continuation capacity, HTTP actor reuse, constructors,
visibility, overloads, generics and imported classes. Router semantics and all
55 Spin integration checks passed on the final runtime pin.

The runtime cache stores only complete root analyses; recursion-local answers
are never published. Identity sets apply to compiler declaration traversal, not
guest data equality. The per-evaluator cache synchronizes publication and does
not hold a lock while analyzing or executing guest code.

Full guest AOT should move this analysis and binding work to build time. Current
Graal native-aot is an AOT-compiled interpreter with guest JIT disabled. The LLVM
AOT driver produces native code only for its admitted subset; full Spin imports,
actors, continuations and HTTP lowering remain future work. These results measure
the JVM interpreter and do not establish Graal/LLVM AOT performance.

At 10,000 clients the load generator's p99 event-loop lag rose to 121.16 ms
(max 237.86 ms), versus 0.247 ms at 100 clients. This same-host Python client
is now a material measurement limitation. Use an independent higher-capacity
load generator before treating the 10,000-client throughput as a server ceiling.
