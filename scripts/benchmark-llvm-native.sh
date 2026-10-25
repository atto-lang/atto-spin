#!/usr/bin/env bash
# Experimental native transport baseline; does not compile Spin's guest modules.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source="${ORESLANG_LLVM_SOURCE_DIR:?Set ORESLANG_LLVM_SOURCE_DIR to the pinned LLVM checkout}"
expected="$(cat "$root/LLVM_SOURCE_REF")"
[[ "$(git -C "$source" rev-parse HEAD)" == "$expected" ]] || { echo 'LLVM_SOURCE_REF differs; use the pinned checkout.' >&2; exit 1; }
[[ -z "$(git -C "$source" status --porcelain --untracked-files=all)" ]] || { echo 'LLVM checkout must be clean.' >&2; exit 1; }
[[ -x "$source/build/oreslang-llvmc" ]] || { echo 'Build oreslang-llvmc first.' >&2; exit 1; }
bash "$source/scripts/build-native-http.sh"
exec python3 "$source/scripts/benchmark-native-http.py" --server "$source/build/native-http/native-http-server" "$@"
