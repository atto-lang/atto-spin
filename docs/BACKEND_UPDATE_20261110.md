# Current compiler compatibility, 2026-11-10

Java compiler: `6d8eb70048eafc9a84c5aebe9c1bb06104f16e76` (fetched main).
LLVM compiler: `8f818fd53e9f85e7823ac1c5a8ea8c302cfd8449` (the router parity
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
