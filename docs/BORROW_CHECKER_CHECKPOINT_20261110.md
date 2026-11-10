# Canonical borrow checker checkpoint

The canonical Rust checker reconciled its unique open cyclic/projection work in
[PR #10](https://github.com/ores-truffle-oreslang/atto-borrow-checker.rs/pull/10).
Its preserved ancestry also marked PR #2 merged. Main is
`a3ca742deb868384ec38686a64e5c77540a7811c`, with exact tested root tree
`280680e4507fd125167e03e7b6f855aeadb8e0ad`.

The original V0 ownership, reverse cleanup proposals, complete submitted MIR
inventory checks and atomic shadow observations remain intact. An explicit
`cyclic_v1` module adds field-sensitive MAY/MUST joins, move/reinitialization
loops, shared readers and exclusive through-loan writes. Its input, work queue,
analysis work and retained-state budgets fail closed. Read-only loans cannot
authorize writes, and raw owner access cannot bypass an overlapping loan.

All **108 Rust library/model tests** pass in debug and release on macOS arm64
and on the Linux private carrier, with formatting and strict Clippy. Source CI
ran no steps because of account billing. Using the authorized fallback, the
GitHub connector mirrored all 21 source blobs to the verified-private repository
`streempilot-test/browser-studio-e2e`; each blob and the root tree matched.
Carrier commit `7e05e4dddd7eb411fcd7d76f7de37fb2ae6633b1`, temporary branch
`ci/atto-borrow-cyclic-exact-tree-20261110`,
[run 42924354741](https://github.com/streempilot-test/browser-studio-e2e/actions/runs/42924354741)
and job `130206895563` show actual executed test steps. The destination used its
own token; no cross-organization secrets/tokens were added. Origin check failures
remain recorded; no required merge check was overridden.

## Gates for Spin and compiler parity

This is not a production compiler adapter or full borrow-checker certification.
The cyclic model does not yet provide destructor/unwind cleanup or the complete
typed-MIR inventory envelope. V0/MIR V1 still reject loops; a cyclic report must
not be used to override their rejection through a lossy translation. Field
disjointness and Copy/transfer facts require independently validated typed layout
and trait provenance. Dynamic indices, overlapping layouts and unsupported
effects cannot be silently omitted.

Java, LLVM/C++ and .NET/C# retain independent compiler-local ownership passes.
They still need complete instruction inventories and differential guest tests
against the canonical model. Further requirements include nonlexical/reborrow
analysis, pinned continuation/drop/unwind correctness, checked 32-bit arena
references, private actor heaps and one logical stack per execution context,
and runtime-authenticated shared-region, singleton and symbol borrowing. A static
loan model does not prove runtime lease identity, cancellation quiescence or
safe physical reclamation.

No compiler pin or backend capability gate changes in this checkpoint. Spin's
real LLVM and .NET HTTP execution remains unproven. The
[shared-memory/mailbox contract](SHARED_MEMORY_AND_MAILBOXES.md) and
[request ownership](OWNERSHIP.md) remain the acceptance targets.
