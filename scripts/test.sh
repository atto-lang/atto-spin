#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compiler="${ORESLANG_COMPILER:-$root/scripts/compiler.sh}"
# Single fail-closed admission guard shared with compiler launcher and CI.
bash "$root/scripts/check-pins.sh"
# Host-only oracle and mutation tests supplement but never replace guest execution.
python3 -B -m unittest discover -s "$root/tests" -p 'test_transport_security.py' -v
python3 -B -m unittest discover -s "$root/tests" -p 'test_integration_receipt.py' -v
python3 -B "$root/scripts/test_host_oracle_mutations.py"
export ORESLANG_COMPILER="$compiler"
bash "$root/dependencies/http-routing/scripts/test.sh"
"$compiler" --check --platform=server "$root/examples/mixed.atto"
# Explicitly register the native builder regression: checking alone is not execution.
"$compiler" --check --platform=server "$root/tests/builder_contracts_20261101.atto"
"$compiler" --platform=server "$root/tests/builder_contracts_20261101.atto"
python3 "$root/tests/integration.py"
