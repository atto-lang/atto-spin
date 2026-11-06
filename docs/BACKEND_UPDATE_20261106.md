# Compiler main tips — 2026-11-06

Pins at this revision (all `main` tips except the router, which is the head of its open repin PR):

| Dependency | Pin |
|---|---|
| oreslang-source.java (`SOURCE_REF`) | `main` `67ff8ad05b`: `.atto` admission (#2460), formatting-borrow fix (#2497), slot-leak fix (#2521) |
| oreslang-source.llvm (`LLVM_SOURCE_REF`) | `main` `16e986c4c7`, LLVM 21.1.8 |
| `dependencies/http-routing` | `50408cdde0` (oreslang-http-routing#46: router `main` + Java/LLVM tips) |
| `dependencies/otel` | `main` `ee6aa6f54c` |

Sources are canonical `.atto`, including `tests/builder_contracts_20261101.atto` from #32.

## Java evidence (local, macOS arm64, JDK 21.0.12)

- Router semantics, the `examples/mixed.atto` check and the builder regression pass.
- `tests/integration.py` against the real `tests/server.atto` listener: **all 102 checks pass**,
  including `deadline releases every admission slot` (fixed by Java #2521; see #2498).
- The raw-wire transport gate added in #33 fails, which `scripts/test.sh` reports.
  Per probe, recorded individually: invalid chunk size gets 500 (regression; it was 4xx on the old
  pin); duplicate `Host` and a 12 KB header are accepted with 200 (also on the old pin, so #33
  merged failing). All are Java HTTP host behaviour:
  [oreslang-source.java#2569](https://github.com/ores-truffle-oreslang/oreslang-source.java/issues/2569).
  The lasting fix is AttoLang framing (#10).

**Java execution is not verified at this pin until #2569 is fixed:** `scripts/test.sh` still fails at the transport gate.

## LLVM evidence

`scripts/check-backend.py llvm`: positive control plus exact rejection of `examples/mixed.atto`
and `src/spin.atto` (`actor requires at least one scalar field`), PASS. Package execution stays
unsupported; router-level gaps are tracked as executable `.atto` cases 32-36 in
oreslang-compilers-parity-testing#28.

## Other gates

`scripts/test-backend-checker.py`, `tests/test_transport_security.py` and the load/profile
unit tests pass. `scripts/test-preflight.sh` passes again; on `main` it failed because #32 made
`test.sh` execute the builder regression and the preflight stub compiler only accepted `--check`.

The local Java checkout used `git update-index --skip-worktree .github/pull_request_template.md`
for one path, because Java `main` tracks case-colliding templates
([oreslang-source.java#2567](https://github.com/ores-truffle-oreslang/oreslang-source.java/issues/2567)).
