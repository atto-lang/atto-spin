# Shared source execution checkpoint — 2026-11-10

The [common-source parity corpus PR #264](https://github.com/ores-truffle-oreslang/oreslang-common-source/pull/264)
introduces identical `.atto` files and a Rust executable runner for Java, LLVM and
.NET. Tested runner/corpus commit: `4a40d52f7ba863b4cc49853e0bc03d992c0e930e`.

The unchanged imported Foo program executes correctly on Java JVM
`e6098659c2e1641564bb5835b4dbb92a6a00b1a8` and LLVM native O2
`66ff048d03b3175ca6027e42667e862b3d96d1cf`. Exact stdout is
`hello world\nhiiii 2hiiii`, without a final newline. A `pub fnc main` scalar
executes on all three, including .NET emitted CIL at
`21552e121964fcb9a28e4329e8346f7386ed1a58`.

The four-case suite records 10 passing observations and 2 gaps: .NET rejects
`pub routine main` and the `.atto` class import. The import diagnostic is the
first observed blocker; this does not establish general .NET class support.
Malformed source is rejected by every backend without execution. The gate
intentionally exits 1 until the valid examples all pass.

This is local executable evidence on integration branches. It does not alter
Spin compiler pins or backend support declarations, and it does not prove
LLVM/.NET HTTP server, actor, borrow, or NativeAOT parity. Existing Java Spin
HTTP validation remains separate. LLVM source/server gaps must still be closed
and the actual Spin server executed before promoting support.

The runner uses pipes because the strict-NIO native console deliberately refuses
regular-file stdout. Full local logs, compiler/source/build hashes, LLVM IR and
executables are retained in `outputs/three-backend-corpus-run-20261110-final`.
The common-source PR also preserves the dated baseline and selected raw results.
