# Implementation progress

The fifteen steps have been worked through for the first HTTP/1.1 draft. Scope
boundaries are explicit below; this is not a claim of a stable production release.

| Step | Work | Result |
| --- | --- | --- |
| 1 | Inspect and pin dependencies | SOURCE_REF pins core; gitlink pins routing. Core had clients only. |
| 2 | Router compatibility | Explicit ownership migration; native golden and runner suites pass. |
| 3 | Public framework API | Builder, immutable application, actor registrations, middleware, examples. |
| 4 | Exchange ownership contract | Generation-revoked guest handles, one writer and one pending I/O. |
| 5 | Connection/request separation | Core retains connection/TLS-layer boundary; actors own exchange access. |
| 6 | Isolated transfer | Actor/runtime-bound single-use claim; sender/wrong-owner/double-move tests. |
| 7 | Shared actor mode | Fresh shared actor per request; synchronized native state, same single-writer rule. |
| 8 | HTTP transport | HTTP/1.1, strict path adapter, keep-alive, bounded text/binary bodies and streaming. |
| 9 | Routing policy | Existing trie router, handler kind, route/capture metadata, HEAD/OPTIONS/404/405/Allow. |
| 10 | Supervised dispatch | Startup/dispatch failure cleanup, deadlines, bounded actors and requests. |
| 11 | Extraction/responses | Required-value Results, captures/query/cookies/headers, text/HTML/JSON/redirect helpers; application-owned codecs. |
| 12 | Middleware | Ordered supervisor hooks, route pipeline/contract IDs, auth/CORS example, ordinary error containment. |
| 13 | Lifecycle/limits | Admission through actor finalization, draining, parser/connection defaults, counters, optional timings. |
| 14 | Verification | 1,232 core tests; native routing suite; 55 real-HTTP integration assertions. |
| 15 | Examples/benchmark/draft | Runnable mixed-mode example, timing/JFR allocation baseline, pinned test scripts, linked draft PRs. |

## Draft boundaries

- HTTP/1.1 backend only. TLS termination, HTTP/2, WebSockets, multipart,
  compression, JSON codecs, and signed cookies remain adapters/libraries.
- Isolated ownership is enforced guest authority; the OS FD and native framing
  objects stay in the transport. Several actors cannot share an exchange through
  a guest SharedMutex. No physical JVM/OS-process isolation claim is made.
- Validation/serialization is application-specific. A contract ID does not
  automatically validate a payload; middleware selects the validator.
- CI definitions are reviewable templates because the connected OAuth credential
  cannot publish workflow files. Activating native cross-repository CI also needs
  a read token for private dependencies. Companion hosted jobs did not start
  because GitHub reported a billing/spending-limit block; local tests pass.
- Benchmarks currently use interpreter fallback and show substantial allocation
  overhead. Optimizing-Graal/native-image and production load testing are not
  represented as complete.

[Merged runtime #438](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/438)

[Merged routing #8](https://github.com/ores-truffle-oreslang/oreslang-http-routing/pull/8)

## Keyword-borrow and boundary hardening follow-up

- Migrated routing/Spin types and expressions to keyword borrows.
- Pinned compiler support for explicit singleton tuple unpacking and borrow leases.
- Audited and hardened cleanup retention and source failure propagation.
- Revalidated 1,232 core tests, router golden tests, and 55 HTTP assertions.
