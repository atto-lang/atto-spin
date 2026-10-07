# Request ownership

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
