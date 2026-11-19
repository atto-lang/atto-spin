#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compiler="${ORESLANG_COMPILER:-$root/scripts/compiler.sh}"
# Single fail-closed admission guard shared with compiler launcher and CI.
bash "$root/scripts/check-pins.sh"
export ORESLANG_COMPILER="$compiler"
bash "$root/dependencies/http-routing/scripts/test.sh"
"$compiler" --check --platform=server "$root/examples/mixed.atto"
# Explicitly register the native builder regression: checking alone is not execution.
"$compiler" --check --platform=server "$root/tests/builder_contracts_20261101.atto"
"$compiler" --platform=server "$root/tests/builder_contracts_20261101.atto"
# Execute the canonical native AttoLang HTML golden test on this exact pin;
# retain a compiler check for legacy .ores compatibility.
"$compiler" --check --platform=server "$root/tests/html_render.ores"
"$compiler" --check --platform=server "$root/tests/html_render.atto"
"$compiler" --check --platform=server "$root/examples/render.atto"
render_output="$("$compiler" --platform=server "$root/tests/html_render.atto")"
[[ "$render_output" == "HTML_RENDER_OK" ]] || {
  printf 'Native HTML golden test failed: %s\n' "$render_output" >&2
  exit 1
}
python3 "$root/tests/integration.py"
