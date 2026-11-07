# Candidate verification: Java HTTP framing fix #2629

Status: **candidate only / NOT_EXECUTED / must not merge as parity evidence**.

- Spin base: PR #35 head `0cdeb333ce77d389237601d82e0bede931e59f8a`.
- Java source pin: `de411f807d2cd9ac9d281f626a705441e2d010ff`, the current candidate head of
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
   - malformed chunk-size `Z` => 4xx, close, no guest handler dispatch
   - two `Host` fields => 4xx, close, no guest handler dispatch
   - 12 KiB header field => 4xx, close, no guest handler dispatch
   - existing TE+CL, duplicate CL, negative CL and unsupported TE cases remain rejected
   - good subsequent requests recover and all 102 guest integration checks continue passing.
5. Record exact Spin head/tree, Java source head/tree, router gitlink/tree, workflow
   run attempt, job IDs, executed steps, raw-wire response status and source stderr.
6. Keep #2629 and Spin #35 draft until source-org Actions runner admission,
   independent review, Java JUnit/Graal guest proof and transport acceptance all succeed.

**Security:** no cross-org private-source transfer, no fabricated green checks and
no inference that source-free canaries establish compiler-backed guest parity.
