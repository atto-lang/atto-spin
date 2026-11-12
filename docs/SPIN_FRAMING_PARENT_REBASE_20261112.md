# Spin framing receipt reconciliation (2026-11-12)

Spin PR #35 merged into main; its executed [private original-commit guest run 43252086287](https://github.com/gha-indie-worker/gha-indie-worker-docs/actions/runs/43252086287) returned **124 total checks = 116 functional + 8 existing raw-wire probes** (seven rejections and one recovery). It did **not** execute 124 functional-only checks.

PR #37 replaces that 8-check raw-wire fixture with **25 actual socket checks: 23 malformed-request negative probes + 2 legitimate-request controls**. Consequently its exact expected receipt is **141 total = 116 functional + 25 raw-wire**. The integration oracle and host tests reject counts below or above the expected values, even under Python optimization. No negative assertions were relaxed.

The [PR #37 original exact-head CI run 43254243063](https://github.com/gha-indie-worker/gha-indie-worker-docs/actions/runs/43254243063) proved that pinned Java `e6098659c2e1641564bb5835b4dbb92a6a00b1a8` rejects too little: `Host: example.test:abc` reached guest middleware and returned 200. This is a real blocker, not a flaky test.

A test-only candidate applies physically SHA-verified [Java source #2988](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/2988) Host authority and raw-wire changes in an isolated private CI checkout, preserving original Java/Router/Spin Git commit/tree verification **before** local test commits. The candidate proved 15 Java JUnit tests and got through all 25 Spin socket probes; previous run 43256992870 stopped only because the oracle incorrectly expected 149 instead of 141.

**Merge gate:** obtain an independently reviewed Java authority fix on the appropriate compiler mainline/ref, pin an actual merged Java exact commit, and execute a fresh full original-Spin-head guest run with 141/141 receipt, independent Spin approval, and zero bypass of checkout/provenance checks. An isolated test-only integration commit is not the original Java or Spin PR SHA and cannot itself authorize a merge.
