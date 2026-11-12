# Compiler tip update — 2026-11-03

- `SOURCE_REF`: oreslang-source.java `273dafad1b` = `main` `eb02a86348` +
  [#2497](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2497).
  Unpatched `main` rejects the router's field reads inside `stdio.println`.
- `LLVM_SOURCE_REF`: oreslang-source.llvm `main` `de7dec73d0` (LLVM 21.1.8; LLVM 22
  removed `Intrinsic::getDeclaration`).
- Router: `dependencies/http-routing` at oreslang-http-routing#33. OTel at current `main`.
- `src/spin.ores`: call sites use `rt mut borrow` (current Java rejects `rt borrow mut`).
- `BACKENDS.json`: LLVM still rejects `examples/mixed.ores` and `src/spin.ores` at the
  same empty-actor-field boundary; the diagnostics now carry a `[file: …]` suffix.

## Java evidence at these pins (local, macOS arm64, JDK 21.0.12)

`scripts/test.sh`: router semantics PASS and `examples/mixed.ores` type check PASS.
`tests/integration.py` fails at check 78, `deadline releases every admission slot`.
Running every check: only 78 (`deadline releases every admission slot`), 95
(`response before actor end`) and the graceful-shutdown wait fail, all one root cause:
an oversized chunked body leaks an HTTP admission slot because the cancelled fresh
actor never reaches `done()`
([oreslang-source.java#2498](https://github.com/ores-truffle-oreslang/oreslang-source.java/issues/2498)).
With an experimental HTTP-layer workaround applied to the runtime, all 102 checks pass,
so nothing else in Spin regressed. **Do not mark Java execution verified at this pin
until #2498 is fixed.**

LLVM gate (`scripts/check-backend.py llvm`), checker self-tests and the provenance
preflight pass. LLVM package execution remains unsupported.

## AttoLang `.atto` sources

`src/spin.atto`, `examples/mixed.atto` and the six `tests/*-server.atto` fixtures are
the canonical sources (pure renames). Scripts, generated temp fixtures, the project
config and the LLVM probes follow. Historical receipts under `docs/benchmarks/` keep
their original `.ores` names. Java `main` does not accept `.atto` yet, so `SOURCE_REF`
pins `00afec5384` (`integration/atto-2460-with-2497-20261103` in oreslang-source.java:
#2460 `.atto` admission merged with #2497); the router submodule is
oreslang-http-routing#34.

At these pins the results are identical to the `.ores` run above: router semantics and
the `examples/mixed.atto` check pass, and `tests/server.atto` fails only checks 78 and 95
and the shutdown wait (#2498). The LLVM gate, the checker self-tests, the provenance
preflight and the load/profiling unit tests pass.
