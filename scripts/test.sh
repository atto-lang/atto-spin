#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compiler="${ORESLANG_COMPILER:-$root/scripts/compiler.sh}"
# Single fail-closed admission guard shared with compiler launcher and CI.
bash "$root/scripts/check-pins.sh"
export ORESLANG_COMPILER="$compiler"
bash "$root/dependencies/http-routing/scripts/test.sh"
"$compiler" --check --platform=server "$root/examples/mixed.ores"
# Explicitly register the native builder regression: checking alone is not execution.
"$compiler" --check --platform=server "$root/tests/builder_contracts_20261101.ores"
"$compiler" --platform=server "$root/tests/builder_contracts_20261101.ores"
python3 "$root/tests/integration.py"
