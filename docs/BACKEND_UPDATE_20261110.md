# Current compiler compatibility, 2026-11-10

Java compiler: `e6098659c2e1641564bb5835b4dbb92a6a00b1a8` (sealed-state/frame integration PR #2796, preserving #2781/#2747 and fetched main).
LLVM compiler: `a0119fb17c1f74f4a9e2503deaedaee15ad2fc51` (the router parity
branch, including fetched main `0ee037ca3e5dd9ac6ac1e9cc3d40f19ee6326a9c`).
Routing: `504c65b9df9c468e4a2718d44aa3ec5f2554146d`, based on routing main
`de85570f26351f25d0bb3d9a80e930d9a5cbb0f1` with the Java pin aligned.

The shared Spin source now uses canonical `rt mut borrow` and imports the
routing dependency's actual `.atto` file. Both compilers receive identical
framework source; no per-backend rewrite or HTTP host adapter is used.

Executed Java evidence: `scripts/test.sh` passed routing frontend checking and
guest semantics, the single-use builder guest regression, and 110 black-box
HTTP checks against a real server, including shared/isolated actors, framing,
timeouts, keep-alive and failure recovery. This is JVM guest execution, not
Native Image or LLVM server execution.

Executed LLVM evidence: the backend checker accepts a real positive compiler
control, then requires exact rejection without IR for `examples/mixed.ores`
and `src/spin.ores`. Both still stop at fieldless receive actors. Package
execution therefore remains **unsupported**. Scalar record views and canonical
control-flow work do not prove owning-array node views, methods, general actor
suspension, or HTTP exchange capability transfer.

The .NET backend remains unverified for Spin and is part of the active parity
work. Host transport or compiler probes do not establish shared-source server
execution.

Additional local LLVM evidence at that revision: 86 Java/LLVM program comparisons
passed with generated guest ASan instrumentation, alongside 168 no-IR rejection
cases. The new .atto entry-view fixture executes at O0 and O2 through the
no-GC IR audit. These are compiler/guest-subset results, not Spin server execution.

## Actor-frame integration follow-up

The preceding frame checkpoint used Java `2e21d99af9f7b4b5564647fb9b914da0be1ac22c` from
[PR #2781](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2781)
and routing `9741ac1da25e3f276ccb5949adc5b1b324c1c4d8`. The Java branch
semantically merges the actor scalar-frame stack with main
`6d8eb70048eafc9a84c5aebe9c1bb06104f16e76`, retaining the newer actor factory,
mailbox, physical-turn and WAL proof restrictions. It is an unmerged snapshot.

Local evidence: 110 combined Java frame and boundary tests pass with zero skips;
seven real guest tests also pass under Surefire `-DargLine=-Xss512k`.
Spin's complete `scripts/test.sh` then passes routing semantics, builder
execution, and all **110 real HTTP checks** using the exact clean compiler
checkout and routing pin above. The earlier mainline compiler result used `6d8eb70048eafc9a84c5aebe9c1bb06104f16e76`.

This adds executed integration evidence; it does not establish general
source-object arena lowering, native-image execution, concurrent-default actor
frames, independent actor collectors, or full stack/heap separation. LLVM Spin
execution stays unsupported at its unchanged pin; .NET Spin execution remains
unverified and part of the active parity work. Tenant-VM work follows proof of
actor-private heaps/arenas and stacks, as described in [OWNERSHIP.md](OWNERSHIP.md).

## Sealed-state/frame follow-up

The current Java and routing pins above execute Spin's complete routing,
builder and 110 HTTP checks. Java PR #2796 reconciles sealed state with the
frame branch: canonical `critical-read`/`critical-write`, exact logical context
and actor allocation identity, immediate lexical callback ownership, and
physical notification/STOP retirement fences. Nine migrated local fixtures use
`.atto` and `rt mut borrow` with exact updated blob checks.

The compiler passes 306 focused tests plus four current-main admission tests;
31 selected source/conformance/frame tests pass under `-Xss512k`. This is local
JVM evidence. Source CI is billing-blocked and not claimed as executed. Guest
actors remain physically serial; concurrent-default guest admission and queued
critical acquisition are open. Host reader/writer concurrency does not prove
LLVM/.NET parity or supervisor access to a child's private state.
