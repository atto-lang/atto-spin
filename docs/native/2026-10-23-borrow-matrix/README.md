# Shared borrow matrix — 2026-10-23

Spin and routing now pin LLVM `c7e4f28aa36f896e347e2c9a87f8feccc56a8c71`
and Java `10792c332e6a31d685ca65960f841543fe95fbb8`. These follow-ups change
only tests and build/test registrations; production compiler/runtime code is
unchanged from the preceding [515-native / 317-Java validation](../2026-10-22-integration/README.md).

[Exact-tree Linux run 40007239817](https://github.com/led-dynamo/leddy-e2e/actions/runs/40007239817)
completed successfully against those exact heads. It built all targets, audited
517 registered CTests with 35 critical gates, and executed the four changed native
borrow/manifest tests. The shared Java test ran all 162 corpus vectors. The
standalone runner additionally compared all 144 generated programs directly
between Java and LLVM: 60 valid executions and 84 required loan-conflict rejections.
Both native release and ASan/UBSan matrix registrations passed.

The matrix exhausts two-/three-argument alias partitions and shared/exclusive
modes for int, bool and class owners. It checks repeated calls, values and no-IR
rejection. Both repositories keep the same 162-vector TSV (18 original plus
144 generated) and reject truncated, malformed or duplicate vectors. The test
manifest requires the real executable/compiler arguments and sanitizer flag.

This is bounded invocation evidence, not a proof of every borrowing, escape,
projection, suspension, FFI or concurrent-memory case. Full native Spin/routing/
async HTTP/OTel lowering remains unfinished. Origin CI remains billing-blocked;
private validation does not replace required origin merge checks. The receipt
records private destination identity, exact source/mirror tree hashes and run/job
identities. No cross-organization checkout secrets were introduced.
