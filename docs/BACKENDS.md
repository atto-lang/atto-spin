# Compiler backend compatibility

The compiler snapshots are recorded in `SOURCE_REF` (Java) and
`LLVM_SOURCE_REF` (LLVM). `BACKENDS.json` describes the tested boundary.

## Java / Truffle

Use JDK 25 and Maven. Build a clean compiler checkout at `SOURCE_REF`:

```sh
git -C ../oreslang-source.java fetch origin
git -C ../oreslang-source.java checkout --detach "$(cat SOURCE_REF)"
(cd ../oreslang-source.java && mvn -q -DskipTests package dependency:build-classpath -Dmdep.outputFile=target/classpath.txt)
export ORESLANG_SOURCE_DIR="$(cd ../oreslang-source.java && pwd)"
# Optional: export ORES_JAVA=/absolute/path/to/jdk-25/bin/java
python3 scripts/check-backend.py java
```

The check rejects a wrong revision or dirty compiler checkout. Build artifacts
are ignored by the compiler repository. Rebuild after changing the compiler
revision; source provenance alone cannot prove a previously built binary matches.
The bundled launcher is the default; compiler overrides are trusted caller input.

The pinned parser accepts `rt borrow`, not the `ft borrow` spelling shown in some
newer runtime documentation. These packages use the executable parser contract.

The native Oreslang semantic/integration suite passes at the pinned Java revision.
This is JVM execution evidence; it does not certify Graal native-image builds,
physical actor heap isolation, or LLVM runtime parity.

## LLVM

**Package execution is unsupported at this pin.** The LLVM backend does not yet
provide the import/runtime surface required by these libraries. An LLVM compiler
build succeeding is not evidence that this package can run on it.

Build the pinned compiler with LLVM 20 and CMake:

```sh
git -C ../oreslang-source.llvm checkout --detach "$(cat LLVM_SOURCE_REF)"
cmake -S ../oreslang-source.llvm -B ../oreslang-source.llvm/build   -DCMAKE_BUILD_TYPE=Release -DLLVM_DIR="$(llvm-config --cmakedir)"
cmake --build ../oreslang-source.llvm/build --target oreslang-llvmc --parallel 4
export ORESLANG_LLVM_SOURCE_DIR="$(cd ../oreslang-source.llvm && pwd)"
python3 scripts/check-backend.py llvm
```

On Homebrew, use `$(brew --prefix llvm@20)/bin/llvm-config` if LLVM 20 is not on
PATH. LLVM 23 exposed incompatible compiler APIs during local validation. The
compiler target builds on macOS; the wider native actor test target additionally
requires `threads.h`, absent from the tested macOS SDK.

The LLVM check first compiles a supported integer program as a positive control.
It then requires the listed package entry points to reject with a compiler
error and emit no IR. A broken compiler cannot satisfy the positive control.
A passing rejection check only establishes explicit unsupported behavior; it is
not a code-generation, ABI, networking, or actor-isolation test. Once imports and
runtime APIs are implemented, replace these rejection probes with executable
semantic tests before changing `execution` to `supported`.

## Local validation (2026-10-12)

Java: `4fe60a8b7d381b69695af17f5bfead27c5469da5`.
LLVM: `76a4de42567ab7e6f3c602c683724e16d503003c`.

These are pinned snapshots, not a claim that an arbitrary future `main` works.

The backend checker validates the manifest and requires nonempty, unique, local
LLVM probes with exact expected diagnostics. Crashes, internal errors, changed
diagnostics, or accidental IR emission fail the check. Run its negative-contract
regressions with `python3 scripts/test-backend-checker.py`.
