# Candidate verification: Java HTTP framing fix #2629

Status: **candidate only / NOT_EXECUTED / must not merge as parity evidence**.

- Spin base: PR #35 head `0cdeb333ce77d389237601d82e0bede931e59f8a`.
- Java source pin: `6fcfc377eaedb1403a7233f3a3d9b6946dd52e97`, the current candidate head of
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
   - good subsequent requests recover and the pre-existing 102 integration checks and 10 added raw-wire checks pass.
5. Record exact Spin head/tree, Java source head/tree, router gitlink/tree, workflow
   run attempt, job IDs, executed steps, raw-wire response status and source stderr.
6. Keep #2629 and Spin #35 draft until source-org Actions runner admission,
   independent review, Java JUnit/Graal guest proof and transport acceptance all succeed.

**Security:** no cross-org private-source transfer, no fabricated green checks and
no inference that source-free canaries establish compiler-backed guest parity.

## 2026-11-07 case expansion

This candidate now pins Java #2629's revised raw-wire regression head `6fcfc377eaedb1403a7233f3a3d9b6946dd52e97`.
Three new HTTP/1.1 raw-wire cases cover mixed-case duplicate Host headers, blank Host,
and missing Host. A standalone JDK 21 host harness returned the expected 200/400
codes with connection closure and listener recovery across 9/9 cases; this does
**not** count as a Java #2629 JUnit or compiler-backed Spin `.atto` run.

## November 7, 2026 TE/CL defense-in-depth head update

Pinned Java #2629 head `6fcfc377eaedb1403a7233f3a3d9b6946dd52e97`, which adds explicit host-header and
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

## 2026-11-07 strict raw-wire negative oracle and admission counters

- Test harness now **requires one explicit HTTP 400** (or 400/501 for
  unsupported transfer encoding), clean connection closure, and no second
  pipelined response. Silent EOF, generic 404, success, and server 500 do not
  qualify as negative evidence. Invalid headers must not emit guest
  middleware's `X-Spin` marker; malformed chunked bodies may fail after actor
  admission, so that marker exception is intentional.
- Actual Spin server probe matrix expanded from 7 malformed frames to
  **16 malformed frames** plus two positive controls (listener recovery and a
  valid chunked `POST /echo`). This adds **10** native integration assertions
  beyond the earlier eight.
- Existing `tests/test_transport_security.py` was aligned with the stricter
  oracle and extended to **10 host-only test methods**, including silent close,
  404/500, double response, middleware bypass, and 501 exclusivity.
  `scripts/test.sh` now runs the host-only oracle suite before guest tests.
- Java #2629 exact source head `6fcfc377eaedb1403a7233f3a3d9b6946dd52e97` adds a native JDK raw-wire
  regression that counts successful header admission and completed body reads.
  The host-only regression explicitly distinguishes a malformed chunk
  discovered after admission from a Host/TE/CL denial before guest dispatch.

These are code changes and test registrations, **NOT_EXECUTED** on hosted
GitHub Actions. They do not prove the actual AttoLang guest works until the
full exact-pinned server integration is executed on an admitted source runner.

## 2026-11-07 source doc pin refresh

Java #2629's new exact head `6fcfc377eaedb1403a7233f3a3d9b6946dd52e97` only clarifies the Host, TE/CL and
post-admission malformed-body security documentation relative to the prior
pinned head; its runtime/test behavior remains unchanged. The exact Spin
integration replay remains **NOT_EXECUTED** and CI runner admission remains
blocked. Do not mistake this metadata synchronization for an execution pass.

## 2026-11-07 current compiler candidate: Java #2659

For the *next* compiler-backed integration run, this Spin branch now pins
Java [PR #2659](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2659)
exact head `0cf6583ec9621c7cbb2da84db90d8e5136419a99`, the HTTP error-origin status fix built on
merged Java #2629. This newer pin **supersedes previous pinned source
references above only for future test execution**; earlier local host receipts
remain historical and are not rewritten as Java #2659 full-repository tests.

The full `tests/integration.py` suite now requires exactly 102 functional
actor/HTTP checks and 18 actual raw-wire socket checks (**120 total**),
checks independently that the actual wire matrix returned 18, and fails
explicitly under Python `-O` rather than relying on stripped `assert`
statements. Six isolated receipt-helper tests cover correct counts, short or
extra counts, and optimized-Python failure. The actual 120-check native
`.atto` suite remains **NOT_EXECUTED** until original-org runner admission
is restored. Java #2659 is DRAFT and must receive independent review.

## 2026-11-07 typed HTTP 413 quota re-pin

The **current executable compiler source pin** is Java [PR #2659](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2659)
head `81ffb6d5a4882da29dae970e698bbaaa71227560`, which changes the quota admission status logic
from message-text matching to the dedicated `RequestBodyTooLargeException`
and adds declared-limit versus malformed-length JDK wire regressions.
This supersedes older source pins **only for future exact-head execution**;
historical local receipts are unchanged.

An independent *isolated* JDK21 host-model check of the new Java policy
returned **4/4 expected HTTP statuses and connection closures** (200, 413,
400, and recovered 200). That is not execution of Java #2659 JUnit or Spin
`tests/server.atto`. Spin's existing 120-check gate must still be run
against the actual compiler and actor runtime after source-org Actions
runner admission is restored.

## 2026-11-07 current Host-authority security gate — 124 live guest checks

The current Spin `SOURCE_REF` pins Java [PR #2659](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2659)
exact head `f7539ae7f11ea78feacd85b297f6b685c1b76056`, including strict Host authority syntax and typed
request-body quota provenance. This supersedes the older pins above **only**
for future end-to-end execution; previously executed local host receipts
remain historical.

Added four malformed Host raw-wire frames: nondecimal port, empty host,
port 65536, and malformed bracketed IPv6. This brings the live wire matrix
to **20 rejection probes plus two positive controls = 22**, while the
existing functional actor/HTTP checks remain 102. The release receipt now
requires **124 total guest checks (102 functional + 22 raw-wire)**. A
separate host-side receipt test asserts that all four named authority probes
are actually visited and that both positive controls are run.

The prior **39/39 host-only response oracle** and **10/10 deliberate
mutation kills** are unchanged and do not prove these four new probes
have run against the real `server.atto`. The isolated Java21 model
reported 38/38 direct host admission/status assertions and 8/8 actual
JDK socket replies for the new Host authority guard; these are **not**
compiler-backed guest evidence. Real 124-check execution remains
**NOT_EXECUTED** pending origin-private runner admission and independent
review. No cross-organization private-source transfer.

## November 8 — Host authority raw-wire expansion (authored, NOT EXECUTED)

This branch now requires **127** live guest-integration checks: the established
102 functional checks, **23** malformed HTTP wire rejections, and two positive
recovery/chunked controls. Three new wire probes deny an empty Host port
(`localhost:`), unbracketed IPv6 (`::1`), and a percent-escaped Host
authority (`example.test%20attacker`). The source-free receipt regression
asserts all seven named malformed Host cases are visited and refuses both
under-counting and surplus counts. These are proposed live socket tests;
this section does **not** claim that the Java compiler, Spin actor guest,
or any physical target executed. The existing `SOURCE_REF` remains pinned
to its reviewed Java candidate rather than silently tracking an active
Java PR head. Revalidate that exact Java tree before any guest claim.
