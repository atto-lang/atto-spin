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
