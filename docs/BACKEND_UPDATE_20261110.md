# Current compiler compatibility, 2026-11-10

Java compiler: `6d8eb70048eafc9a84c5aebe9c1bb06104f16e76` (fetched main).
LLVM compiler: `a0119fb17c1f74f4a9e2503deaedaee15ad2fc51` (the router parity
branch, including fetched main `0ee037ca3e5dd9ac6ac1e9cc3d40f19ee6326a9c`).
Routing: `8aae392ad88ababbc6b27a1b78e23f902b207be6`, based on routing main
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

The .NET backend remains unverified for Spin in this repository. It is a later
phase; host transport or compiler probes do not establish shared-source server
execution.

Additional local LLVM evidence at that revision: 86 Java/LLVM program comparisons
passed with generated guest ASan instrumentation, alongside 168 no-IR rejection
cases. The new .atto entry-view fixture executes at O0 and O2 through the
no-GC IR audit. These are compiler/guest-subset results, not Spin server execution.
# Actor-frame integration follow-up

Spin now pins Java `3cf4559f7b5e232c3d05639a16358f53a1a6f18f` from
[PR #2781](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2781)
and routing `6fcdb2446876b9797f82834d3937c10d73e2f708`. The Java branch
semantically merges the actor scalar-frame stack with main
`6d8eb70048eafc9a84c5aebe9c1bb06104f16e76`, retaining the newer actor factory,
mailbox, physical-turn and WAL proof restrictions. It is an unmerged snapshot.

Local evidence: 69 Java frame tests and 39 boundary tests pass with zero skips;
seven real guest tests also pass under Surefire `-DargLine=-Xss512k`.
Spin's complete `scripts/test.sh` then passes routing semantics, builder
execution, and all **110 real HTTP checks** using the exact clean compiler
checkout and routing pin above. Earlier results below describe earlier pins.

This adds executed integration evidence; it does not establish general
source-object arena lowering, native-image execution, concurrent-default actor
frames, independent actor collectors, or full stack/heap separation. LLVM Spin
execution stays unsupported at its unchanged pin; .NET Spin execution remains
unverified and part of the active parity work. Tenant-VM work follows proof of
actor-private heaps/arenas and stacks, as described in [OWNERSHIP.md](OWNERSHIP.md).

