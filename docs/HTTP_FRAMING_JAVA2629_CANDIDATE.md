# Candidate verification: Java HTTP framing fix #2629

Status: **candidate only / NOT_EXECUTED / must not merge as parity evidence**.

- Spin base: PR #35 head `0cdeb333ce77d389237601d82e0bede931e59f8a`.
- Java source pin: `932b3b044bca5a5ddf56237c8e4f2a7b7d18238e`, the current candidate head of
  [Java #2629](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2629).
- Router submodule pin: merged router `main` `de85570f26351f25d0bb3d9a80e930d9a5cbb0f1`,
  with Git tree `b18acbf38bb68ab4fe439d9959563010afb57716`.
- No compiler/Spin code is modified in this branch; only `SOURCE_REF` and this note.

## Required exact-source acceptance

1. Obtain an admitted runner: run source-free synthetic canary in the origin org and demand
   nonzero executed steps, assigned runner, logs, and bound SHA/tree receipt.
2. Build/check Java compiler source at exactly `SOURCE_REF`, with a clean checkout and
   reproducible source dependency pin.
3. Execute Java's `NativeHttpFramingAdmissionTest` and
   `NativeHttpRawWireAdmissionTest`; distinguish host transport tests from actual
   guest-executed `.atto` source.
4. Boot `tests/server.atto` from a clean compiler tip. Run
   `tests/transport_security.py` against a real HTTP socket and assert:
   - malformed chunk-size `Z` => 4xx, close, and no successful processing
     of the rejected body. The body is read after request admission, so this
     does **not** currently prove the guest was never scheduled or that an
     actor performed no pre-read side effects
   - two `Host` fields => 4xx, close, rejected before guest dispatch
   - 12 KiB header field => 4xx, close, rejected before guest dispatch
   - duplicate and joined Content-Length, TE+CL, negative CL and unsupported/repeated TE are rejected as parser-level or admission-level errors; assert no guest dispatch when transport exposes them
   - good subsequent requests recover and all 102 guest integration checks continue passing.
5. Record exact Spin head/tree, Java source head/tree, router gitlink/tree, workflow
   run attempt, job IDs, executed steps, raw-wire response status and source stderr.
6. Keep #2629 and Spin #35 draft until source-org Actions runner admission,
   independent review, Java JUnit/Graal guest proof and transport acceptance all succeed.

**Security:** no cross-org private-source transfer, no fabricated green checks and
no inference that source-free canaries establish compiler-backed guest parity.

## 2026-11-07 case expansion

This candidate now pins Java #2629's revised raw-wire regression head `932b3b044bca5a5ddf56237c8e4f2a7b7d18238e`.
Three new HTTP/1.1 raw-wire cases cover mixed-case duplicate Host headers, blank Host,
and missing Host. A standalone JDK 21 host harness returned the expected 200/400
codes with connection closure and listener recovery across 9/9 cases; this does
**not** count as a Java #2629 JUnit or compiler-backed Spin `.atto` run.

## November 7, 2026 TE/CL defense-in-depth head update

Pinned Java #2629 head `932b3b044bca5a5ddf56237c8e4f2a7b7d18238e`, which adds explicit host-header and
TE/CL framing admission to the host adapter plus dedicated unit and raw-wire
regression coverage. The JDK 21 standalone wire probe observed that duplicate
Content-Length and TE/CL conflicts are rejected by JDK **before** its handler;
this is a parser-level rejection, not proof that AttoLang code ran. Record
host rejections and statuses distinctly from actual guest execution.

## Raw-wire negative response-body characterization

JDK 21 parser-level HTTP 400 responses for duplicate Content-Length and TE/CL
may contain an explanatory response body. The Java #2629 raw-wire regression now
reads at most 64 KiB before asserting connection EOF; it does not incorrectly
require the error response to be empty. A separately executed local JDK socket
harness passed **13/13** request/status/close/recovery probes after this fix,
including 400 responses with bodies of 52 and 65 bytes. This is not an
execution of the PR JUnit tests or a compiler-backed Spin guest.
