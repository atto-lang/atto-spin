# .NET source actors on native arenas and execution frames

[.NET PR #461](https://github.com/ores-truffle-oreslang/oreslang-source.net/pull/461)
reconciles the older Counter source compiler stack with the actual ActorRuntime
and execution-owned frame integration. Exact source head
`70f0e4671137907370e28d71838688799386daab`, root tree
`18dd661928cc5261a03162dc0cf230cc96ecfef9`.

The opt-in source emitter produces static C# whose `SpawnRuntime` entry invokes
its one no-argument operation through real mailbox DATA delivery. Each source
actor stores mutable scalar state in its own native arena; operands/results use
the caller's existing execution-owned stack. Responses go through a real shared
supervisor's mailbox. The fixed data envelope does not serialize actor handles
or establish a universal MessagePack wire contract.

Executed cases prove separate A=1,2,3 and B=1,2 state, source-generated overflow
fault containment and peer/fresh-actor survival, exact 16-byte stack cleanup,
logical identity preservation, foreign actor denial and physical native budget
reclamation. A scheduler byte-refund regression failed before its merge fix and
now preserves both data quotas and FIFO control authority. Canonical
`critical-write`, `.atto` inputs and exact emitted/compiled golden comparisons
are included. The older trusted-host managed Counter cells remain separate and
are not relabeled as native arena evidence.

## Executed platform evidence

The full managed suite passes locally on macOS arm64. A genuine NativeAOT
Mach-O probe runs three times with dynamic-code support disabled. The existing
native memory probe also passes with four private heaps, two shared-pool actors,
stack/schema/transfer guards, STOP pins, terminal quotas and reclamation.

Source CI ran zero steps because of billing. Under the user's authorized
fallback, the GitHub connector mirrored all 478 files into verified-private
`streempilot-test/browser-studio-e2e`. All source blobs and the root tree match;
carrier commit `98bbf8d5a713748b1c3f98e1d923feabef1c6245`, temporary branch
`ci/atto-net-state-frames-exact-tree-20261110`.

[Run 42934451529](https://github.com/streempilot-test/browser-studio-e2e/actions/runs/42934451529)
passed real Linux and Windows jobs (`130240933205`, `130240932731`). Each verifies
the checked-out tree, regenerates both source actors, runs the complete managed
suite, publishes NativeAOT and executes three native runs. Required receipts
include source mailbox/native state/execution stack/overflow survival,
dynamic-code-disabled and zero native bytes after retirement. DLL sidecars are
rejected. The destination used its own token; no cross-org secrets/tokens were
added. Origin failures remain recorded and no required merge check was bypassed.

## Open parity work

This still compiles only the experimental synchronous +1 actor profile through
static C# emission. It is not general actor CIL, Java receive/ActorMail syntax,
LLVM on_message(int), arbitrary source objects/strings, async stack restoration,
concurrent-default guest RW admission, shared-region/singleton/symbol borrowing,
or the complete canonical borrow checker and native adapters.

No Spin source pin or backend capability is changed. .NET Spin remains
unverified until the actual common framework/server source compiles and runs.
Source actor scalar data/frame evidence cannot certify all guest allocations,
all stacks or untrusted tenant isolation.
