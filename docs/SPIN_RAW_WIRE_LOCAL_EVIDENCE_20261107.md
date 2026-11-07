# Spin raw-wire client: exact-blob local host evidence (2026-11-07)

**Evidence class: HOST_EXECUTED_LOCAL_EXACT_BLOBS; not native guest evidence.**

## Identity

The following source files were fetched from stacked [Spin #37](https://github.com/ores-truffle-oreslang/oreslang-spin/pull/37) at head `7849c724d2585f0734b648fbd24635b044b6dc93`, and locally checked using `git hash-object`.

| GitHub path | SHA-1 Git blob verified locally |
| --- | --- |
| `tests/transport_security.py` | `4bb070448b57c1f5fe40fa37c0f8e1d7e2649d32` |
| `tests/test_transport_security.py` | `3e1bc526ae965e1cedd66a99f7e8453c2a0d07e5` |

Environment: local Linux x86-64, Python 3.13.5, Git 2.47.3.
No private-source cross-org GitHub mirroring; only these two already
retrieved source-file blobs were used for isolated local host tests.

## Reproduced local execution

From the directory containing the exact files under `tests/`:

```bash
python3 -B -m unittest discover -s tests -p 'test_transport_security.py' -v
```

**10/10 host-only unittest methods PASS**, including one actual local
loopback socket exchange. The tests validate the raw-wire assertion helper,
not the AttoLang compiler or the native Spin guest server.

Three independent negative mutation copies were constructed without
altering the PR:

1. Replace the explicit status/count/closure guard with only `if not closed`.
   **KILLED**: tests reject 200, 404, 500, garbage, duplicate status lines,
   and a silent socket close.
2. Replace the guest middleware marker check with `if False`.
   **KILLED**: `test_rejected_header_must_not_enter_guest_middleware`.
3. Make `_statuses` report only the first status line.
   **KILLED**: `test_second_pipelined_status_fails` and
   `test_status_parse_ignores_body_digits`.

Every mutant ran the same test suite and returned nonzero with named
assertion failures, rather than merely a compile/syntax error.

## Missing end-to-end proof

The live `run(port)` matrix is registered in
`tests/integration.py` and now includes **16 negative raw-wire frames**
plus two positive controls (normal recovery and a valid chunked POST).
This larger matrix **has not been executed against the real guest**.
The compiler pin is Java [#2629](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2629)
at `6fcfc377eaedb1403a7233f3a3d9b6946dd52e97`.
The parent Spin [#35](https://github.com/ores-truffle-oreslang/oreslang-spin/pull/35)
must also preserve its dependency pin and prerequisites.

The hosted Spin framing-conformance workflow at this exact stack's
pre-receipt head ran as [42412763392](https://github.com/ores-truffle-oreslang/oreslang-spin/actions/runs/42412763392),
`host-contract-tests` job `128524247312`, **failure with `steps=[]`**;
this is **NOT_EXECUTED / runner-admission failure**, not failure of host tests.

Before readiness: recover origin private Actions admission, execute exact-head
host tests with nonzero steps, then execute all pinned `.atto` Spin guest
integration and raw-wire probes with a known clean Java compiler checkout,
record job/attempt, test output, exact Git trees and independent approval.
Never promote a source-only host test to compiler-backed guest proof.
