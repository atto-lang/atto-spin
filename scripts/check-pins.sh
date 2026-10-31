#!/usr/bin/env bash
# Source-side admission only: this does not attest previously built class files.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
: "${ORESLANG_SOURCE_DIR:?Set ORESLANG_SOURCE_DIR to the pinned compiler checkout}"
[[ -d "$ORESLANG_SOURCE_DIR" ]] || { echo 'Compiler checkout does not exist' >&2; exit 65; }
source_dir="$(cd "$ORESLANG_SOURCE_DIR" && pwd -P)"
expected="$(cat "$root/SOURCE_REF")"
[[ "$expected" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid SOURCE_REF' >&2; exit 65; }
# The checked-in pin is authoritative. Neither worktree nor index overrides
# may select a different compiler revision at launch time.
[[ ! -L "$root/SOURCE_REF" ]] || { echo 'SOURCE_REF must not be a symlink' >&2; exit 65; }
committed_ref="$(git -C "$root" show HEAD:SOURCE_REF 2>/dev/null)" || { echo 'Cannot inspect committed SOURCE_REF' >&2; exit 65; }
[[ "$expected" == "$committed_ref" ]] || { echo 'SOURCE_REF differs from committed tree' >&2; exit 65; }
committed_pin_blob="$(git -C "$root" rev-parse 'HEAD:SOURCE_REF' 2>/dev/null)" || { echo 'Cannot inspect committed SOURCE_REF blob' >&2; exit 65; }
staged_pin_blob="$(git -C "$root" rev-parse ':SOURCE_REF' 2>/dev/null)" || { echo 'Cannot inspect staged SOURCE_REF blob' >&2; exit 65; }
[[ "$staged_pin_blob" == "$committed_pin_blob" ]] || { echo 'SOURCE_REF index differs from committed tree' >&2; exit 65; }
source_top="$(git -C "$source_dir" rev-parse --show-toplevel 2>/dev/null)" || { echo 'Cannot inspect compiler checkout root' >&2; exit 65; }
[[ "$(cd "$source_top" && pwd -P)" == "$source_dir" ]] || { echo 'Compiler must be its own Git checkout root' >&2; exit 65; }
source_head="$(git -C "$source_dir" rev-parse --verify HEAD 2>/dev/null)" || { echo 'Cannot inspect compiler revision' >&2; exit 65; }
[[ "$source_head" == "$expected" ]] || { echo 'Compiler revision differs from SOURCE_REF' >&2; exit 65; }
source_status="$(git -C "$source_dir" status --porcelain --untracked-files=all)" || { echo 'Cannot inspect compiler checkout status' >&2; exit 65; }
[[ -z "$source_status" ]] || { echo 'Compiler checkout must be clean' >&2; exit 65; }

project_top="$(git -C "$root" rev-parse --show-toplevel 2>/dev/null)" || { echo 'Cannot inspect Spin checkout root' >&2; exit 65; }
[[ "$(cd "$project_top" && pwd -P)" == "$root" ]] || { echo 'Spin must be its own Git checkout root' >&2; exit 65; }
router="$root/dependencies/http-routing"
[[ -d "$router" ]] || { echo 'Router submodule is not initialized' >&2; exit 65; }
router_top="$(git -C "$router" rev-parse --show-toplevel 2>/dev/null)" || { echo 'Cannot inspect router checkout root' >&2; exit 65; }
[[ "$(cd "$router_top" && pwd -P)" == "$router" ]] || { echo 'Router must be its own Git checkout root' >&2; exit 65; }
router_status="$(git -C "$router" status --porcelain --untracked-files=all)" || { echo 'Cannot inspect router checkout status' >&2; exit 65; }
[[ -z "$router_status" ]] || { echo 'Router checkout must be clean' >&2; exit 65; }

# Read the immutable HEAD gitlink, not the mutable index (ls-files --stage).
gitlink="$(git -C "$root" ls-tree HEAD -- dependencies/http-routing)" || { echo 'Cannot inspect committed router gitlink' >&2; exit 65; }
[[ "$gitlink" =~ ^160000[[:space:]]commit[[:space:]]([0-9a-f]{40})[[:space:]]dependencies/http-routing$ ]] || { echo 'Invalid committed router gitlink' >&2; exit 65; }
expected_router="${BASH_REMATCH[1]}"
staged_router="$(git -C "$root" rev-parse ':dependencies/http-routing' 2>/dev/null)" || { echo 'Cannot inspect router index gitlink' >&2; exit 65; }
[[ "$staged_router" == "$expected_router" ]] || { echo 'Router index gitlink differs from committed tree' >&2; exit 65; }
router_head="$(git -C "$router" rev-parse --verify HEAD 2>/dev/null)" || { echo 'Cannot inspect router revision' >&2; exit 65; }
[[ "$router_head" == "$expected_router" ]] || { echo 'Router revision differs from committed gitlink' >&2; exit 65; }
