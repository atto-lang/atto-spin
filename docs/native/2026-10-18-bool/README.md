# Native bool and borrow parity validation

The compiler now keeps `bool` distinct from `int` in fields, locals, calls,
returns and borrowed arguments. Literal values, logical negation and bool guards
compile to native code. The actor HTTP helper reads a private bool field during
real request handling. LLVM remains zero-GC and full AOT.

The [exact-tree Linux run](https://github.com/led-dynamo/leddy-e2e/actions/runs/39166194349)
passed 434 native CTests, 154 Java tests, 45 module cases (12 identical executions),
33 class-method cases (11 identical executions), 36 bool cases (12 identical
executions), and five repeats each of three HTTP ownership/Release/sanitizer
checks. The native CTest inventory includes the shared 18-case borrow contract.
The matching macOS suite passed 423 CTests.

[The receipt](ci-receipt.json) identifies both source trees, private mirror and
executed job. The destination's own token built its local mirror; no cross-org
credentials were added. Required origin checks remain billing-blocked and
unchanged. The Java returned-loan receiver follow-up and later NIO integration
are separate heads and are not certified by this earlier run.

This is compiler capability evidence, not another HTTP performance measurement.
The latest sustained [benchmark](../2026-10-18-methods/README.md) retains its own
older source/binary hashes. String/Array/object lifetime APIs, HTTP capability
lowering, general async continuations and the actual Spin/OTel graph still remain.

## Combined borrow/NIO framework follow-up

A later [exact-tree run](https://github.com/led-dynamo/leddy-e2e/actions/runs/39167627664)
passed 317 combined Java runtime tests, pinned router semantics, 55 real Spin
HTTP checks, sixteen routing harness checks and fourteen Spin harness checks.
The runtime includes returned-loan receiver rejection, physical-segment mutex
fencing and live-guard accounting, while preserving the existing NIO HTTP/client
work. Spin's no-argument constructor performs router factory initialization
rather than an unproven function call in a field initializer.

[The framework receipt](framework-ci-receipt.json) records exact Java, native,
routing and Spin trees. The private dependency was materialized from its own
mirrored checkout without network credentials. This follow-up does not rebuild
LLVM; that unchanged commit has the separate 434-test native run above. It is
JVM framework execution evidence, not native Spin execution or a new benchmark.
