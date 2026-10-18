# LLVM native HTTP baseline

The first native integration connects LLVM-compiled Oreslang scalar actor
handlers to the existing C scheduler/mailboxes and a C++ nonblocking HTTP
adapter. One process hosts all actors and the reactor. Actor invocation uses
in-memory mailboxes; there is no worker HTTP or cross-process IPC.

```sh
# Checkout/build the LLVM_SOURCE_REF commit in oreslang-source.llvm first.
export ORESLANG_LLVM_SOURCE_DIR=/path/to/oreslang-source.llvm
# If needed, select Clang matching the LLVM development toolchain:
export CLANG=/opt/homebrew/opt/llvm@20/bin/clang
export CXX=/opt/homebrew/opt/llvm@20/bin/clang++
./scripts/benchmark-llvm-native.sh --output /tmp/spin-native-baseline \
  --clients 100 --actors 128 --carriers 4 --warmup 10 --seconds 180
```

This experiment is **not full Spin source support**. `BACKENDS.json` continues
to reject unsupported LLVM module compilation. Parsing, fixed routing and
response formatting are native adapter work; the guest actor maintains its
persistent request count and returns status. It does not execute the JVM
benchmark's guest suspend/cooperate checkpoints, shared/private source actor
placement or oreslang-otel module. Separate actor heaps live in the same address
space and do not provide hardware memory protection against malicious native code.

The native adapter uses kqueue on macOS and epoll on Linux, exclusively owns
socket operations and hands exclusive request/response capabilities to actors.
Generation/actor checks and release/acquire publication fence ownership; socket
readiness remains reactor work. Unsupported filesystem I/O has no worker fallback.
Numeric timings are buffered/aggregated and exported at shutdown.

The next milestones are import/type graph lowering, typed HTTP capabilities,
Future/await/cooperate state machines, shared/private actor source integration,
route and OTel module compilation, then identical-workload JVM/native comparisons.
The native repository's `docs/SPIN_NATIVE_PARITY.md` tracks these gates.
