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

## Supplemental exact-blob replay — 2026-11-07, HTTP response framing

Latest source/test head before this evidence-doc commit:
`f0b827a178ecbb60ac17418ed3d311aa47d02149`.

Two **new exact file identities** were compared with `git hash-object`
after fetching GitHub PR #37. The local Git SHA-1s matched GitHub exactly:

| Path | Git blob SHA-1 |
| --- | --- |
| `tests/transport_security.py` | `518932fecdadd3f88cf6821cf00acb214228152e` |
| `tests/test_transport_security.py` | `61be1eb160f825738944cdbd22a9d90a46652ef9` |

Local environment Linux x86_64, Python 3.13.5, Git 2.47.3.

```bash
python -m py_compile tests/transport_security.py
python -B -m unittest discover -s tests -p 'test_transport_security.py' -v
```

**Result: 22/22 executed tests PASS** (0.005 s, source-only/host assertion
layer). New negatives include forged leading junk before a status line,
missing CRLF header terminator, duplicate/ambiguous response Content-Length,
truncated/surplus body, invalid header names, obsolete folded headers,
response Transfer-Encoding+Content-Length, and embedded fake statuses.

Four independent deliberate mutations were then exercised using the same
**22-test** suite, each failing by a **named unittest assertion**:

1. `if len(body) != int(lengths[0])` → `if False`:
   **KILLED** by surplus and truncated body tests (two failures).
2. Duplicate response CL/TE+CL rejection → `if False`:
   **KILLED** by duplicate CL and TE+CL tests (two failures).
3. Guest `X-Spin` middleware marker rejection → `if False`:
   **KILLED** by `test_rejected_header_must_not_enter_guest_middleware`.
4. Socket-close enforcement → `if False`:
   **KILLED** by the open-connection negative status test.

No unrelated syntax/compile errors counted as mutant kills.
The actual `tests/transport_security.py::run(port)` **16 malformed frames
and two positive controls have NOT been executed against compiler-backed
`tests/server.atto`**, and this exact head has no successful stepful hosted
Actions evidence. These local tests do not certify guest execution or AOT.

The earlier 10/10 / 3-mutant subsection above remains a historical receipt
for the older blobs; this subsection supersedes it for the newer test files.

## Latest exact-blob replay: 26/26 host tests and 6/6 JDK responses

The current PR's raw-wire host source/test files, fetched at pre-receipt
head `76eaad0a8ec219463a3e78025c60f62f465ff453`, were independently reproduced in a local isolated test
directory, with `git hash-object` matching the GitHub source blobs:

| File | Verified Git blob SHA-1 |
| --- | --- |
| `tests/transport_security.py` | `2dab3514b0ed62a679600767f20c4ec02698619d` |
| `tests/test_transport_security.py` | `ce0a6e531ffa499c29dc81f2eaf8d7c720eca0eb` |

Executed under Linux x86_64, Python 3.13.5:
`python -B -m unittest discover -s tests -p test_transport_security.py -v` →
**26/26 PASS**. Four deliberately weakened source variants were again killed
by specific test assertions: bypass response-body length, bypass duplicate
response Content-Length/TE+CL rejection, bypass guest marker isolation, and
bypass connection closure.

**JDK 21 host characterization:** Independently compiled a minimal local
`com.sun.net.httpserver.HttpServer` and sent six raw HTTP/1.1 requests.
The exact Spin parser accepted the **six actual captured raw responses** with
the expected statuses and body sizes:

| Request case | JDK status | Response body |
| --- | --- | --- |
| valid GET | 200 | 0 bytes |
| unsupported `Transfer-Encoding: gzip` | 501 | 63 bytes |
| conflicting TE/CL | 400 | 65 bytes |
| duplicate Content-Length | 400 | 65 bytes |
| HTTP/1.1 missing Host (no AttoLang gate) | 200 | 0 bytes |
| invalid chunk size | 400 | 0 bytes |

That fifth case demonstrates why AttoLang's **own Host gate** is necessary;
stock JDK's missing-Host response is not a security rejection.

The PR now contains four additional regression methods for those JDK
response patterns and a bounded numeric `Content-Length` parse, bringing
the host oracle to 26 methods. These are **host-only** checks, not a
`.atto` server run. The real Spin actor guest's **16 malformed requests
and two positive controls remain NOT_EXECUTED**. Do not infer
full-request, runtime actor, or backend parity from this local receipt.


## Exact-blob 36/36 and seven-target mutation gate — 2026-11-07

Independent local Git SHA-1 hashes of the fetched, executed host-test files
match the objects written to Spin #37:

| File | Verified SHA-1 blob |
| --- | --- |
| tests/transport_security.py | 07be11569dc78f8d9c17f6a295bf23584d968e4f |
| tests/test_transport_security.py | a555ac1a9cd695153bc26d6be7c75bfa3cca4295 |
| scripts/test_host_oracle_mutations.py | da7ad8ef44f43e8f60df65b7e006ad1af615ed13 |

Source and tests were committed at 778ba6780159b877072f49a3e981161dc317c0ef;
the independent negative mutation gate was committed at
49fff35478bd28b66ba4439fd839aa192a7a098e.

**Executed locally using Python 3.13.5:**

- python -B -m unittest discover -s tests -p test_transport_security.py -v
  → **36/36 PASS**.
- python -B scripts/test_host_oracle_mutations.py → baseline **36/36 PASS**
  and **7/7 source mutations KILLED by named assertion failures**.
- Mutants: bypass fixed-length response framing, guest-marker isolation,
  response connection closure, strict status, chunk terminator, control
  bytes in response headers, and unframed secondary HTTP response rejection.
- Each mutation compiled/imported in a separate temporary directory and
  failed because an expected named test assertion fired; unrelated syntax
  and import errors are not accepted as evidence.
- Valid chunked responses are now decoded within a 64 KiB bound. Bad hex
  sizes, truncation, trailers and pipelined replies fail closed.
- A correct length-delimited body containing apparent HTTP status text is
  accepted without falsely claiming a second HTTP response.

The two new host workflows now run the mutation script from both
scripts/test.sh and .github/workflows/framing-parity-contract.yml.
This is HOST_ONLY_EXACT_BLOB execution. The live server.atto suite
(16 negative requests and two positive controls) has not executed against
the real AttoLang compiler/runtime. Source-org GitHub Actions jobs still
fail runner admission with zero executed steps. No CI or guest-parity claim.
