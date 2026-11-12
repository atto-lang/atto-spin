# Spin PR #37 current reconciliation (2026-11-12)

The two-parent merge preserves mainline PR #30 checkout-provenance checks,
PR #36 exact-head admission, and PR #41 early framework routing outcome metadata.
Canonical `.atto` and legacy `.ores` actor paths retain main's
fail-closed middleware and one-writer response boundaries.

The expanded raw-wire matrix is 23 negative socket requests and 2 positive
controls. Including #41's 3 new outcome checks, the exact guest receipt must be
**144 = 119 functional + 25 wire**.

[Previous candidate CI 43257667613](https://github.com/gha-indie-worker/gha-indie-worker-docs/actions/runs/43257667613)
passed 141 (116+25) using a local test-only patch for the pinned Java Host
authority bug. That result does not certify this updated head or the current
unmerged [Java PR #2988](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2988).

Merge gates: independently approve/merge Java fix (or reviewed backport),
repin the actual merged compiler, rerun 144 live guest checks and negative
oracles against final Spin head, and obtain independent Spin approval.
Zero-step/host-only CI and local patch SHAs are not substitutes.
