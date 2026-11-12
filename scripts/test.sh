#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compiler="${ORESLANG_COMPILER:-$root/scripts/compiler.sh}"
: "${ORESLANG_SOURCE_DIR:?Set ORESLANG_SOURCE_DIR to the compiler checkout}"
source_dir="$(cd "$ORESLANG_SOURCE_DIR" && pwd -P)"
[[ "$(git -C "$source_dir" rev-parse --show-toplevel)" == "$source_dir" ]] || { echo 'Compiler directory must be its own Git checkout' >&2; exit 65; }
expected="$(tr -d '[:space:]' < "$root/SOURCE_REF")"
[[ "$expected" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid SOURCE_REF' >&2; exit 65; }
[[ "$(git -C "$ORESLANG_SOURCE_DIR" rev-parse HEAD)" == "$expected" ]] || { echo 'Compiler revision differs from SOURCE_REF' >&2; exit 65; }
source_status="$(git -C "$ORESLANG_SOURCE_DIR" status --porcelain --untracked-files=all)" || { echo 'Cannot inspect compiler checkout status' >&2; exit 65; }
[[ -z "$source_status" ]] || { echo 'Compiler checkout must be clean' >&2; exit 65; }
router_status="$(git -C "$root/dependencies/http-routing" status --porcelain --untracked-files=all)" || { echo 'Cannot inspect router checkout status' >&2; exit 65; }
[[ -z "$router_status" ]] || { echo 'Router checkout must be clean' >&2; exit 65; }
expected_router="$(git -C "$root" ls-files --stage dependencies/http-routing | awk '{print $2}')"
[[ "$(git -C "$root/dependencies/http-routing" rev-parse HEAD)" == "$expected_router" ]] || { echo 'Router revision differs from gitlink' >&2; exit 65; }
export ORESLANG_COMPILER="$compiler"
bash "$root/dependencies/http-routing/scripts/test.sh"
"$compiler" --check --platform=server "$root/examples/mixed.ores"
# Explicitly register the native builder regression: checking alone is not execution.
"$compiler" --check --platform=server "$root/tests/builder_contracts_20261101.ores"
"$compiler" --platform=server "$root/tests/builder_contracts_20261101.ores"
# Golden test uses the pinned compiler to execute guest HTML rendering.
"$compiler" --check --platform=server "$root/tests/html_render.ores"
"$compiler" --check --platform=server "$root/examples/render.ores"
render_output="$("$compiler" --platform=server "$root/tests/html_render.ores")"
[[ "$render_output" == "HTML_RENDER_OK" ]] || {
  printf 'Native HTML golden test failed: %s\n' "$render_output" >&2
  exit 1
}
python3 "$root/tests/integration.py"
