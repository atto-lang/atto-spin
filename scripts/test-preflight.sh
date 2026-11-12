#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/ores-spin-preflight.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/compiler-source" "$tmp/router" "$tmp/project/scripts" "$tmp/project/tests" "$tmp/project/examples" "$tmp/project/dependencies"
git -C "$tmp/compiler-source" init -q
printf 'compiler source\n' > "$tmp/compiler-source/tracked"
printf 'target/\n' > "$tmp/compiler-source/.gitignore"
git -C "$tmp/compiler-source" add tracked .gitignore
git -C "$tmp/compiler-source" -c user.name=Audit -c user.email=audit@example.invalid commit -qm init
ref="$(git -C "$tmp/compiler-source" rev-parse HEAD)"
git -C "$tmp/router" init -q
mkdir -p "$tmp/router/scripts"
printf '#!/usr/bin/env bash\nexit 0\n' > "$tmp/router/scripts/test.sh"
printf 'router\n' > "$tmp/router/tracked"
git -C "$tmp/router" add .
git -C "$tmp/router" -c user.name=Audit -c user.email=audit@example.invalid commit -qm init
cp "$root/scripts/test.sh" "$tmp/project/scripts/test.sh"
cp "$root/scripts/check-pins.sh" "$tmp/project/scripts/check-pins.sh"
cp "$root/scripts/compiler.sh" "$tmp/project/scripts/compiler.sh"
cp "$root/scripts/ci-native.sh" "$tmp/project/scripts/ci-native.sh"
printf '%s\n' "$ref" > "$tmp/project/SOURCE_REF"
printf 'sample\n' > "$tmp/project/examples/mixed.ores"
printf 'builder fixture\n' > "$tmp/project/tests/builder_contracts_20261101.ores"
printf 'print("integration fixture OK")\n' > "$tmp/project/tests/integration.py"
cat > "$tmp/compiler" <<'COMPILER'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$PREFLIGHT_COMPILER_CALLS"
if [[ "${1:-}" = '--check' ]]; then shift; fi
[[ "$#" = 2 && "$1" = '--platform=server' && -f "$2" ]]
COMPILER
chmod +x "$tmp/compiler"
mkdir -p "$tmp/compiler-source/target"
printf 'fake-classpath\n' > "$tmp/compiler-source/target/classpath.txt"
cat > "$tmp/fake-java" <<'JAVA'
#!/usr/bin/env bash
if [[ "${1:-}" == '-version' ]]; then
  echo 'openjdk version "25.0.1" (MOCK ONLY)' >&2
  exit 0
fi
[[ "$*" == *"dev.oreslang.launcher.OresMain"* ]] || exit 80
echo 'mock launcher reached'
JAVA
chmod +x "$tmp/fake-java"
git -C "$tmp/project" init -q
git -C "$tmp/project" -c protocol.file.allow=always submodule add -q "$tmp/router" dependencies/http-routing
git -C "$tmp/project" add .
git -C "$tmp/project" -c user.name=Audit -c user.email=audit@example.invalid commit -qm fixture
export ORESLANG_COMPILER="$tmp/compiler" ORESLANG_SOURCE_DIR="$tmp/compiler-source"
export PREFLIGHT_COMPILER_CALLS="$tmp/compiler-calls"
run() { bash "$tmp/project/scripts/test.sh"; }
run_launcher() { ORES_JAVA="$tmp/fake-java" bash "$tmp/project/scripts/compiler.sh" --check --platform=server; }
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
[[ "$(wc -l < "$PREFLIGHT_COMPILER_CALLS" | tr -d '[:space:]')" = 3 ]] || { echo 'Three compiler fixture steps were not executed' >&2; exit 1; }
[[ "$(tail -1 "$PREFLIGHT_COMPILER_CALLS")" = "--platform=server $tmp/project/tests/builder_contracts_20261101.ores" ]] || { echo 'Builder execution was not last' >&2; exit 1; }
mkdir -p "$tmp/compiler-source/nested"
export ORESLANG_SOURCE_DIR="$tmp/compiler-source/nested"
expect_failure 'Compiler must be its own Git checkout root'
export ORESLANG_SOURCE_DIR="$tmp/compiler-source"
[[ "$(run_launcher)" == 'mock launcher reached' ]] || { echo 'Pinned launcher did not execute' >&2; exit 1; }
printf 'invalid\n' > "$tmp/project/SOURCE_REF"
expect_failure 'Invalid SOURCE_REF'
if run_launcher >/dev/null 2>&1; then echo 'Launcher accepted invalid SOURCE_REF' >&2; exit 1; fi
printf '%040d\n' 0 > "$tmp/project/SOURCE_REF"
expect_failure 'SOURCE_REF differs from committed tree'
if run_launcher >/dev/null 2>&1; then echo 'Launcher accepted wrong compiler SHA' >&2; exit 1; fi
git -C "$tmp/project" add SOURCE_REF
expect_failure 'SOURCE_REF differs from committed tree'
if run_launcher >/dev/null 2>&1; then echo 'Launcher accepted staged SOURCE_REF change' >&2; exit 1; fi
git -C "$tmp/project" reset -q HEAD -- SOURCE_REF
printf '%s\n' "$ref" > "$tmp/project/SOURCE_REF"
printf '%040d\n' 0 > "$tmp/project/SOURCE_REF"
git -C "$tmp/project" add SOURCE_REF
printf '%s\n' "$ref" > "$tmp/project/SOURCE_REF"
expect_failure 'SOURCE_REF index differs from committed tree'
if run_launcher >/dev/null 2>&1; then echo 'Launcher accepted index-only SOURCE_REF change' >&2; exit 1; fi
git -C "$tmp/project" reset -q HEAD -- SOURCE_REF
run >/dev/null
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
router="$tmp/project/dependencies/http-routing"
old_router_ref="$(git -C "$router" rev-parse HEAD)"
printf 'second\n' >> "$router/tracked"
git -C "$router" add tracked
git -C "$router" -c user.name=Audit -c user.email=audit@example.invalid commit -qm second
git -C "$tmp/project" add dependencies/http-routing
expect_failure 'Router index gitlink differs from committed tree'
if run_launcher >/dev/null 2>&1; then echo 'Launcher accepted staged router gitlink' >&2; exit 1; fi
git -C "$tmp/project" reset -q HEAD -- dependencies/http-routing
expect_failure 'Router revision differs from committed gitlink'
git -C "$router" checkout -q --detach "$old_router_ref"
git -C "$tmp/project" add dependencies/http-routing
run >/dev/null
printf 'modified application fixture\n' >> "$tmp/project/examples/mixed.ores"
expect_failure 'Spin checkout must be clean'
git -C "$tmp/project" add examples/mixed.ores
expect_failure 'Spin checkout must be clean'
git -C "$tmp/project" restore --staged --worktree examples/mixed.ores
printf 'untracked source\n' > "$tmp/project/rogue.ores"
expect_failure 'Spin checkout must be clean'
rm "$tmp/project/rogue.ores"
run >/dev/null
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
# Validate the new native-acceptance *orchestration* with doubles only.
# This does not compile any Oreslang code or establish native acceptance.
mkdir -p "$tmp/mock-bin"
cat > "$tmp/mock-bin/mvn" <<'MAVEN'
#!/usr/bin/env bash
set -euo pipefail
[[ "${MOCK_MAVEN_FAIL:-0}" != 1 ]] || exit 77
printf '%s\n' "$*" >> "$MOCK_MAVEN_RECORD"
mkdir -p target/classes/dev/oreslang/launcher
printf 'mock class\n' > target/classes/dev/oreslang/launcher/OresMain.class
printf 'mock classpath\n' > target/classpath.txt
MAVEN
chmod +x "$tmp/mock-bin/mvn"
cat > "$tmp/bad-java" <<'JAVA'
#!/usr/bin/env bash
echo 'openjdk version "21.0.1" (MOCK ONLY)' >&2
JAVA
chmod +x "$tmp/bad-java"
export MOCK_MAVEN_RECORD="$tmp/mock-maven-invocations"
run_native_mock() {
  PATH="$tmp/mock-bin:$PATH" ORES_JAVA="$tmp/fake-java" bash "$tmp/project/scripts/ci-native.sh"
}
native_mock_output="$(run_native_mock)"
[[ "$native_mock_output" == *SPIN_PINNED_NATIVE_ACCEPTANCE_PASS* ]] || {
  echo 'Fresh-build acceptance mock did not reach final gate' >&2
  exit 1
}
grep -Fx -- '-B -ntp -q -DskipTests clean package dependency:build-classpath -Dmdep.outputFile=target/classpath.txt' "$MOCK_MAVEN_RECORD" >/dev/null || {
  echo 'Native acceptance did not clean and rebuild the pinned compiler' >&2
  exit 1
}
: > "$MOCK_MAVEN_RECORD"
if PATH="$tmp/mock-bin:$PATH" ORES_JAVA="$tmp/bad-java" bash "$tmp/project/scripts/ci-native.sh" > /dev/null 2>&1; then
  echo 'Native acceptance accepted wrong JDK major' >&2
  exit 1
fi
[[ ! -s "$MOCK_MAVEN_RECORD" ]] || {
  echo 'Native acceptance invoked Maven before rejecting wrong JDK' >&2
  exit 1
}
if MOCK_MAVEN_FAIL=1 run_native_mock > /dev/null 2>&1; then
  echo 'Native acceptance ignored compiler rebuild failure' >&2
  exit 1
fi
echo 'Spin clean compiler rebuild orchestration mocks: PASS (not native execution)'
echo "Spin compiler/router provenance preflight: PASS"
