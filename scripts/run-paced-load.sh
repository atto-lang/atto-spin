#!/usr/bin/env bash
set -euo pipefail
[[ $# == 5 ]] || { echo 'Usage: run-paced-load.sh LABEL CORE_DIR shared|isolated disabled|core|both SECONDS' >&2; exit 64; }
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
label="$1"; source_dir="$(cd "$2" && pwd -P)"; mode="$3"; logging="$4"; seconds="$5"
[[ "$label" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 64
[[ "$mode" == shared || "$mode" == isolated ]] || exit 64
[[ "$seconds" =~ ^[0-9]+$ ]] || exit 64
[[ -z "$(git -C "$source_dir" status --porcelain --untracked-files=all)" ]] || { echo 'Compiler must be clean' >&2; exit 65; }
export ORESLANG_SOURCE_DIR="$source_dir"
: "${ORES_JAVA:?Set ORES_JAVA to the matching GraalVM java executable}"
output="$root/.cache/latency-20261013/$label"
[[ ! -e "$output" ]] || { echo 'Output directory already exists' >&2; exit 65; }
mkdir -p "$output"
flags=(--no-core-perf); sample=0
case "$logging" in
 disabled) ;;
 core) flags=(--core-perf --core-perf-sample-every=1024) ;;
 both) flags=(--core-perf --core-perf-sample-every=1024); sample=1000 ;;
 *) exit 64 ;;
esac
cd "$root"
jq -n --arg source "$(git -C "$source_dir" rev-parse HEAD)" --arg spin "$(git rev-parse HEAD)" \
 --arg router "$(git -C dependencies/http-routing rev-parse HEAD)" --arg otel "$(git -C dependencies/otel rev-parse HEAD)" \
 --arg logging "$logging" --arg mode "$mode" --arg java "$ORES_JAVA" \
 --arg java_options "${JAVA_TOOL_OPTIONS:-}" --arg started_at "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
 --arg client_artifact "$(shasum -a 256 tools/load/target/release/spin-paced-load | awk '{print $1}')" \
 --arg artifact "$(shasum -a 256 "$source_dir/target/oreslang-source-0.1.0-SNAPSHOT.jar" | awk '{print $1}')" \
 '{source:$source,spin:$spin,router:$router,otel:$otel,logging:$logging,actor_mode:$mode,java:$java,java_options:$java_options,started_at_utc:$started_at,client_sha256:$client_artifact,jar_sha256:$artifact}' > "$output/metadata.json"
"$ORES_JAVA" -version 2> "$output/java-version.txt"
./scripts/compiler.sh --platform=server --allow-net=127.0.0.1:0 "${flags[@]}" tests/profiled-pooled-server.ores > "$output/stdout.log" 2> "$output/stderr.log" &
server_pid=$!
monitor_pid=''
cleanup() {
 kill "$server_pid" 2>/dev/null || true
 if [[ -n "$monitor_pid" ]]; then kill "$monitor_pid" 2>/dev/null || true; fi
 wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT
for attempt in $(seq 1 200); do
 port="$(sed -n '1p' "$output/stdout.log")"
 [[ "$port" =~ ^[0-9]+$ ]] && break
 kill -0 "$server_pid" 2>/dev/null || { cat "$output/stderr.log" >&2; exit 1; }
 sleep .1
done
[[ "$port" =~ ^[0-9]+$ ]] || exit 1
(
 while kill -0 "$server_pid" 2>/dev/null; do
   date -Iseconds
   ps -p "$server_pid" -o pid,pcpu,rss,nlwp 2>/dev/null || ps -p "$server_pid" -o pid,pcpu,rss
   sleep 2
 done
) > "$output/resources.log" &
monitor_pid=$!
tools/load/target/release/spin-paced-load "$port" "$mode" "$seconds" "$sample" "$output/result.json"
curl -fsS "http://127.0.0.1:$port/__stop" > "$output/stop.txt"
wait "$server_pid"
kill "$monitor_pid" 2>/dev/null || true
wait "$monitor_pid" 2>/dev/null || true
trap - EXIT
