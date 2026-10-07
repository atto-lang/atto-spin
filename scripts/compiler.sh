#!/usr/bin/env bash
set -euo pipefail
: "${ORESLANG_SOURCE_DIR:?Set ORESLANG_SOURCE_DIR to the pinned oreslang-source.java checkout}"
java_bin="${ORES_JAVA:-java}"
source_dir="$(cd "$ORESLANG_SOURCE_DIR" && pwd -P)"
if [[ ! -f "$source_dir/target/classpath.txt" ]]; then
  echo 'Build core with: mvn -q -DskipTests package dependency:build-classpath -Dmdep.outputFile=target/classpath.txt' >&2
  exit 69
fi
exec "$java_bin" --enable-native-access=ALL-UNNAMED -Dpolyglot.engine.WarnInterpreterOnly=false \
  -cp "$source_dir/target/classes:$(cat "$source_dir/target/classpath.txt")" dev.oreslang.launcher.OresMain "$@"
