#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/ores-spin-preflight.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/compiler-source" "$tmp/router" "$tmp/project/scripts" "$tmp/project/tests" "$tmp/project/examples" "$tmp/project/dependencies"
git -C "$tmp/compiler-source" init -q
printf 'compiler source\n' > "$tmp/compiler-source/tracked"
git -C "$tmp/compiler-source" add tracked
git -C "$tmp/compiler-source" -c user.name=Audit -c user.email=audit@example.invalid commit -qm init
ref="$(git -C "$tmp/compiler-source" rev-parse HEAD)"
git -C "$tmp/router" init -q
mkdir -p "$tmp/router/scripts"
printf '#!/usr/bin/env bash\nexit 0\n' > "$tmp/router/scripts/test.sh"
printf 'router\n' > "$tmp/router/tracked"
git -C "$tmp/router" add .
git -C "$tmp/router" -c user.name=Audit -c user.email=audit@example.invalid commit -qm init
cp "$root/scripts/test.sh" "$tmp/project/scripts/test.sh"
printf '%s\n' "$ref" > "$tmp/project/SOURCE_REF"
printf 'sample\n' > "$tmp/project/examples/mixed.atto"
printf 'builder fixture\n' > "$tmp/project/tests/builder_contracts_20261101.atto"
printf 'print("integration fixture OK")\n' > "$tmp/project/tests/integration.py"
cat > "$tmp/compiler" <<'COMPILER'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$PREFLIGHT_COMPILER_CALLS"
if [[ "${1:-}" = '--check' ]]; then shift; fi
[[ "$#" = 2 && "$1" = '--platform=server' && -f "$2" ]]
COMPILER
chmod +x "$tmp/compiler"
git -C "$tmp/project" init -q
git -C "$tmp/project" -c protocol.file.allow=always submodule add -q "$tmp/router" dependencies/http-routing
git -C "$tmp/project" add .
git -C "$tmp/project" -c user.name=Audit -c user.email=audit@example.invalid commit -qm fixture
export ORESLANG_COMPILER="$tmp/compiler" ORESLANG_SOURCE_DIR="$tmp/compiler-source"
export PREFLIGHT_COMPILER_CALLS="$tmp/compiler-calls"
run() { bash "$tmp/project/scripts/test.sh"; }
expect_failure() {
  local needle="$1" output
  if output="$(run 2>&1)"; then
    echo "preflight incorrectly succeeded: $needle" >&2
    exit 1
  fi
  if [[ "$output" != *"$needle"* ]]; then
    echo "expected '$needle' but got: $output" >&2
    exit 1
  fi
}
run >/dev/null
[[ "$(wc -l < "$PREFLIGHT_COMPILER_CALLS" | tr -d '[:space:]')" = 3 ]]
[[ "$(tail -1 "$PREFLIGHT_COMPILER_CALLS")" = "--platform=server $tmp/project/tests/builder_contracts_20261101.atto" ]]
mkdir -p "$tmp/compiler-source/nested"
export ORESLANG_SOURCE_DIR="$tmp/compiler-source/nested"
expect_failure 'Compiler directory must be its own Git checkout'
export ORESLANG_SOURCE_DIR="$tmp/compiler-source"
printf 'dirty\n' >> "$tmp/compiler-source/tracked"
expect_failure 'Compiler checkout must be clean'
git -C "$tmp/compiler-source" restore tracked
printf 'untracked\n' > "$tmp/compiler-source/untracked"
expect_failure 'Compiler checkout must be clean'
rm "$tmp/compiler-source/untracked"
printf 'dirty\n' >> "$tmp/project/dependencies/http-routing/tracked"
expect_failure 'Router checkout must be clean'
git -C "$tmp/project/dependencies/http-routing" restore tracked
printf 'untracked\n' > "$tmp/project/dependencies/http-routing/untracked"
expect_failure 'Router checkout must be clean'
rm "$tmp/project/dependencies/http-routing/untracked"
git() {
  if [[ "$*" == *" status "* ]]; then return 128; fi
  command git "$@"
}
export -f git
expect_failure 'Cannot inspect compiler checkout status'
unset -f git
git() {
  if [[ "$*" == *"dependencies/http-routing status "* ]]; then return 128; fi
  command git "$@"
}
export -f git
expect_failure 'Cannot inspect router checkout status'
unset -f git
run >/dev/null
echo "Spin compiler/router provenance preflight: PASS"
