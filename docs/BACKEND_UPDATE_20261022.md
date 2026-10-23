# Spin backend reconciliation — 2026-10-22

This integration retains the native transport experiment while restoring the
pooled HTTP actors, framework response actors, dispatch timing, profiling tools
and OTel dependency from the ongoing actor performance work. One Spin app owns
the dispatcher and worker pools. Existing benchmark receipts remain historical
measurements; merging them does not constitute a new performance run.

All 102 real Java HTTP integration checks pass against the Java revision in
`SOURCE_REF`, with the exact pinned router and OTel submodules. The production Java baseline passed 317 actor/ownership/I/O/mutex tests in
38 suites; the later test-only 162-vector follow-up also passes its changed suite. Source examples
use `rt borrow` / `rt borrow mut`; the shared borrow corpus agrees byte-for-byte
with the LLVM corpus. Profiling/load/backend harnesses pass locally.

`LLVM_SOURCE_REF` identifies a clean, reconciled compiler containing current
main, module linking, scalar methods and bool borrowing. The full Spin source
still rejects without emitting IR. The changed Spin source encounters the empty
actor-field boundary first; `BACKENDS.json` records that exact real-source
rejection, with a successful native compilation as its positive control.

The separate C++ reactor/LLVM actor adapter remains a lighter baseline. It is
same-process, full AOT and uses deterministic actor-owned storage; it does not
execute the full Spin routes, general async/await or OTel guest modules. No new
physical address-space sandbox, complete borrow-checker proof, or full framework
AOT parity is claimed. GitHub Actions results for older commits do not certify
this updated integration; the checks described here were run locally.

The latest test-only pin update has [exact Linux borrow-matrix evidence](native/2026-10-23-borrow-matrix/README.md).
