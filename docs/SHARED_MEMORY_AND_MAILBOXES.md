# Shared memory and mailboxes

## Required contract

`send`/`receive` is the default way to invoke an actor or deliver work. A
supervisor has no implicit right to call its child's methods or read the child's
private arena. Shared actors still have private allocations and execution stacks.

An explicit shared region may be used by an actor, its supervisor and other
authorized actors. Creating the region consumes the mutable owner; aliases to
the original payload must become unusable. Copying a shared capability is
different from copying an unguarded mutable reference. The capability grants
permission to request access, not continuous access to its payload.

Access has two permitted forms:

- Exclusive mutex: one holder, including readers, at a time.
- Reader/writer region: compatible read-only loans, or one exclusive writer.
  Readers cannot mutate transitively reachable data. Writers exclude all readers
  and other writers. Queued writers must not be starved by new readers.

The borrow checker must reject raw aliases after promotion, guard or protected
reference escape through returns/closures/containers, conflicting loans, and
ordinary loans live across suspension. A runtime lease independently validates
the region, actor/application domain, authenticated execution context, access
mode and generation. A mutex alone cannot repair a raw alias left usable by the
compiler. Host/FFI access needs the same boundary or an explicitly trusted host
contract; checking guest syntax cannot constrain arbitrary host Java/C++/C# code.

Acquire must suspend or report contention rather than park an actor carrier.
Releasing, cancellation and STOP revoke logical access; physical storage cannot
be reclaimed or regranted while a previous holder is still executing against it.
An awaited acquisition does not permit suspending while holding the resulting
ordinary guard. A later invocation must not inherit the previous execution's
guard. Await/resume needs authenticated context restoration rather than thread
identity as authority.

## Mailbox data encoding

MessagePack is a candidate portable **data** encoding. It is not yet a universal
mailbox wire contract across the three backends. The serialization repository at
`8c9975760d8e46caaabfe72bca02fa5a1a2f229d` provides a MessagePack value codec and
bounded channel collection. Its `decode_messagepack_from_channel` is EOF-framed
and rejects `allow_trailing_data`; a persistent mailbox must not wait for the
whole channel to close before delivering each message.

A mailbox already has message boundaries. A future adapter should decode exactly
one bounded payload per envelope, reject trailing bytes, and enforce byte,
nesting, collection and schema limits before exposing receiver-owned values.
Malformed payloads must not partially publish state or consume a capability.
Same-process delivery needs no HTTP forwarding or OS-process IPC.

Actor references, shared-region grants, HTTP req/res handles, file descriptors,
guards and execution identities must not be reconstructed from MessagePack
integers, strings or extension tags. Runtime-issued capabilities travel through
an authenticated mailbox capability path, with destination checks and atomic
ownership transfer where required. MessagePack bytes may describe application
data associated with such a transfer; the bytes do not authorize it. Isolated
actors receive values in their own arena, or a runtime-managed transferred
capability, rather than pointers into the sender's private heap.

## Current evidence and open work

Java's current `SharedMutex` is exclusive, not a reader/writer implementation.
The actor-frame integration executes its existing lock, language, publication,
task-retirement and guard-count matrix locally: 107 passing tests, including two
added ownership regressions checking consumed raw state for both mutex factories
and accepted aliases of the guarded capability. This is separate from Spin's 110
HTTP assertions and is not full cross-backend shared-memory certification.

Java [#2747](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2747)
addresses actor-private sealed-state loans; it does not make that private state
supervisor-visible. Java
[#2772](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2772)
prototypes a separately guarded shared domain, but compiler integration and
authenticated actor-context wiring remain gates. Neither draft is enabled by
this document. LLVM and .NET need matching compiler-backed borrowing,
revocation/quiescence, arena ownership and mailbox codec conformance tests.

See [request ownership](OWNERSHIP.md) for HTTP capability and backend evidence
boundaries. Tenant-VM work follows independent actor-private heaps and stacks.

Java [#2796](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2796)
integrates the private sealed-state loans from #2747 with current main and
execution-owned frames. Canonical critical scopes retain the caller's logical
execution identity. It passes 306 focused tests plus four admission cases,
31 low-stack source/frame tests and Spin's 110 HTTP checks locally. This is
actor-private state access, not supervisor-visible shared application memory.
Guest admission remains serial; scheduler-owned async RW contention and the
three-backend shared-region contract remain open.
