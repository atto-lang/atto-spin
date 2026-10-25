#!/usr/bin/env bash
# Source-free release preflight only; it does not execute Oreslang guest code.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
pin="$(tr -d '[:space:]' < "$root/SOURCE_REF")"
[[ "$pin" =~ ^[0-9a-f]{40}$ ]] || { echo 'SOURCE_REF is not immutable full SHA' >&2; exit 1; }
grep -Fq 'SOURCE_REF' "$root/scripts/test.sh" || { echo 'Test runner does not consult SOURCE_REF' >&2; exit 1; }
grep -Fq 'expected_router=' "$root/scripts/test.sh" || { echo 'Missing router gitlink pin' >&2; exit 1; }
grep -Fq 'Router revision differs from gitlink' "$root/scripts/test.sh" || { echo 'Missing router identity enforcement' >&2; exit 1; }
printf '%s\n' "PASS: retained SOURCE_REF and admission contract shape (no native execution)"
