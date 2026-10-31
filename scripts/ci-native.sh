#!/usr/bin/env bash
# Native acceptance only. Never equate mocked admission tests with this gate.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
: "${ORESLANG_SOURCE_DIR:?Set ORESLANG_SOURCE_DIR to the exact SOURCE_REF compiler checkout}"
source_dir="$(cd "$ORESLANG_SOURCE_DIR" && pwd -P)"
java_bin="${ORES_JAVA:-java}"

# Fail before Maven execution unless sources are exactly those reviewed.
bash "$root/scripts/check-pins.sh"
java_version="$("$java_bin" -version 2>&1)" || {
  echo 'Cannot execute JDK 25' >&2
  exit 69
}
if ! grep -Eq '^(openjdk|java) version "25([.+" ]|$)' <<< "$java_version"; then
  echo 'Native Spin acceptance requires JDK 25' >&2
  exit 65
fi
command -v mvn >/dev/null 2>&1 || {
  echo 'Maven is required for clean pinned compiler rebuild' >&2
  exit 69
}
[[ ! -L "$source_dir/target" ]] || {
  echo 'Compiler target directory must not be a symlink' >&2
  exit 65
}

# A dirty/ignored target directory is not a trustworthy compiler binary.
# Regenerate classes and dependency classpath from the exact pinned source.
(
  cd "$source_dir"
  mvn -B -ntp -q -DskipTests clean package dependency:build-classpath \
    -Dmdep.outputFile=target/classpath.txt
)
[[ -d "$source_dir/target/classes" && ! -L "$source_dir/target/classes" ]] || {
  echo 'No fresh compiler classes generated' >&2
  exit 65
}
[[ -f "$source_dir/target/classes/dev/oreslang/launcher/OresMain.class" &&
   ! -L "$source_dir/target/classes/dev/oreslang/launcher/OresMain.class" ]] || {
  echo 'Pinned compiler launcher class missing or symlinked after rebuild' >&2
  exit 65
}
[[ -s "$source_dir/target/classpath.txt" && ! -L "$source_dir/target/classpath.txt" ]] || {
  echo 'Fresh compiler dependency classpath missing or unsafe' >&2
  exit 65
}
bash "$root/scripts/check-pins.sh"
printf 'SPIN_SOURCE_HEAD=%s\n' "$(git -C "$root" rev-parse HEAD)"
printf 'SPIN_COMPILER_HEAD=%s\n' "$(git -C "$source_dir" rev-parse HEAD)"
printf 'SPIN_ROUTER_HEAD=%s\n' "$(git -C "$root/dependencies/http-routing" rev-parse HEAD)"
printf 'SPIN_COMPILER_LAUNCHER_SHA256=%s\n' "$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$source_dir/target/classes/dev/oreslang/launcher/OresMain.class")"
ORES_JAVA="$java_bin" bash "$root/scripts/test.sh"
echo 'SPIN_PINNED_NATIVE_ACCEPTANCE_PASS'
