# Request ownership

## Actor-memory acceptance target

Every handler actor, shared or isolated, must have its own private allocation
arena and logical execution frames. Explicit shared application regions remain
separate and require checked ownership or reader/writer access. HTTP capability
transfer and mailbox delivery do not by themselves prove this storage boundary.
Tenant-VM work for untrusted actors comes after independent actor arenas and
frames are established; a tenant VM cannot substitute for that requirement.

Each **execution context owns one logical stack**, including its nested call
frames. A receive is one entry point that can create an execution context;
stack ownership is not tied to the receive method. Synchronous calls use their
caller's stack, while independently scheduled work needs its own context/stack.
Await/resume and carrier migration retain the original context and stack.
Overlapping contexts need disjoint live stack storage under the actor's aggregate
heap quota. Completed contexts may release scrubbed arena bytes for reuse. A
carrier's machine stack or thread-local identity cannot substitute for this
logical stack.

The three backend implementations currently have different executed scopes:

- [Java #2781](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2781)
  reconciles actor-owned scalar frames with current main. It passes 69 frame
  tests, 39 boundary tests, seven low-stack guest tests, and Spin's real routing,
  builder and 110 HTTP checks. General native guest allocation remains open.
- [LLVM #1649](https://github.com/ores-truffle-oreslang/oreslang-source.llvm/pull/1649)
  executes restricted source-compiled scalar actors with disjoint native frame
  arenas, actor-local quota failure, sibling/replacement survival and sanitizers.
- [.NET #459](https://github.com/ores-truffle-oreslang/oreslang-source.net/pull/459),
  commit `9c0b65eb2fbf2ded17aded8c1579b466617c32b0`, makes each execution
  context own one logical stack, uses actor-owned physical storage, scrubs on completion/failure, and
  rejects later-DATA frame reuse while retaining persistent heap data. Its full
  managed verification executable passes, and its macOS arm64 NativeAOT host
  probe passes three runs with four private heaps and native budget reclamation.
  General compiler-generated `.atto` actors, authenticated continuation resume,
  concurrently live invocation stacks, and Linux/Windows execution remain open.

These results do not establish complete actor-memory separation across all three
compilers. Spin's LLVM and .NET package capability gates remain unchanged.

The current Java Spin HTTP tests prove request capability behavior and executed
HTTP responses, not complete allocation/frame lowering or an independent GC heap
for every actor. LLVM Spin package execution remains unsupported at its pin.

An independently tested LLVM follow-up,
[PR #1649](https://github.com/ores-truffle-oreslang/oreslang-source.llvm/pull/1649),
commit `f4948859d5d455373275ef3a9018b8ebdaed5f59`, provides restricted **compiled
scalar actor** evidence: nonoverlapping 64-KiB frame regions, domain/turn denial,
actor-local 64-frame exhaustion, sibling progress, and fresh-incarnation
execution. O0/O2 run with a 512-KiB native stack; a separate ASan/UBSan build
instruments generated IR and runtime. Six focused local tests passed. This is a
separate compiler branch, not Spin's pinned LLVM or its HTTP server executing.

Remaining gates include all guest allocations (objects, strings, arrays and
closures), checked 32-bit arena references, concurrent-default actor invocations,
actor-owned call/operand/continuation frames through await and cancellation,
borrow/drop/unwind correctness, and physical resource retirement. Java and .NET
need their own equivalent compiler-backed evidence. No full actor-memory or
tenant-sandbox certification follows from the restricted LLVM result.

## Request capability lifecycle

```mermaid
stateDiagram-v2
    [*] --> Supervisor: accept
    Supervisor --> InTransit: spawn + atomic move
    InTransit --> ActorOwned: owner-bound token claimed once
    ActorOwned --> Responding: await bounded I/O
    Responding --> ActorOwned: next streamed operation
    ActorOwned --> Completed: buffered response
    Responding --> Completed: finish
    Supervisor --> Closed: framework response / error
    InTransit --> Closed: startup failure / deadline
    ActorOwned --> Closed: termination / deadline / disconnect
    Completed --> Closed: actor finalized
    Closed --> [*]: release admission
```

The ownership generation changes at move, before token delivery. Every alias of
the original guest wrapper becomes stale (can_respond reports false; data/I/O
operations reject it). A failed delivery closes the request
and cancels the actor; it never leaves a live handle usable by two guest domains.
Claim checks both the runtime and the destination actor ID before consuming the
token. A wrong actor cannot steal or invalidate the rightful recipient's claim.
The transport supervisor retains cancellation/connection-lifecycle authority;
it does not retain guest access to the moved request body or response writer.

The native state contains synchronized framing and cancellation metadata. Guest
code only sees an opaque, domain-checked capability. Isolated actors do not get
Java references, raw FDs, parent closures, routing tables, or capture views.
Immutable scalar captures are attached before transfer. Actor-owned mutable
state is created by the actor runtime under that actor's execution domain.

A shared actor may use the language's permitted explicit shared-memory APIs for
application state. Its HTTP exchange still has one guest owner and one pending
I/O operation. This draft does not allow several actors to mutate an exchange
through a shared-memory cell. Shared mode selects the runtime actor policy; it
does not mean reusing one handler actor across requests.

This provides exclusive guest authority, not separate OS processes or a physical
socket relocation into an isolated heap. The native transport must still retain
connection and protocol state. That distinction preserves HTTP/1.1 keep-alive
and leaves a path to request-stream capabilities for a future HTTP/2 backend.

Actors call self.end after their final response/cleanup. A response that finishes
before actor termination retains its admission slot; the deadline remains active
until the actor exits. This bounds handlers that omit self.end. A disconnect is
detected on I/O failure, or by the deadline when no I/O is occurring. Failures
before headers produce an error response when possible; failures after headers
close the stream. The supervisor never retries a handler automatically.
