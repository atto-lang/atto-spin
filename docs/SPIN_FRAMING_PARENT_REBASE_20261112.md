# Spin framing receipt reconciliation (2026-11-12)

PR #35 is merged into `main`; PR #37 is retargeted to `main` and preserves its current pinned Java compiler `e6098659c2e1641564bb5835b4dbb92a6a00b1a8` and Router gitlink.

An **executed native AttoLang Java guest run** for original Spin PR #35 at head `5f8c0ec1ea56e30c14776eea47b4211549e4bc5f`, root tree `aab402f5bed5aebc23fc6f786b622dad4e57f2ee`, produced **124 functional checks** in [run 43252086287](https://github.com/gha-indie-worker/gha-indie-worker-docs/actions/runs/43252086287), not 116 as previously inferred by static counting.

PR #37 adds 23 malformed raw-wire negatives and 2 raw-wire positive controls, so its **expected**, as yet unexecuted, full native guest receipt is **149 checks = 124 functional + 25 raw-wire**. The exact-count oracle and optimized-mode host tests reject short or extra counts. The 149 total is not a native execution claim until this branch's own exact-head Java guest and transport tests run.

Keep independent code review and non-zero execution receipts as merge gates; host-only and source-free checks are not guest runtime proof. Other backends remain unverified.
