# Spin framing review base refresh (2026-11-12)

This branch preserves current parent Spin #35 at `5f8c0ec1ea56e30c14776eea47b4211549e4bc5f` as its base and retains Java pin `e6098659c2e1641564bb5835b4dbb92a6a00b1a8` rather than downgrading to the earlier Java #2659 candidate.

The parent now contains additional terminal-middleware and security assertions. Static source inspection counts **116 functional checks**; the 23 negative plus 2 positive raw-wire probes yield an intended **141-check** native receipt. The test and receipt oracle reject any other count.

These are *expected* counts, not executed native results. Host-only oracle tests cannot establish compiler/guest correctness. Require exact merged head, clean dependency Git trees, actual admitted CI steps, Java guest execution, and independent review before promotion.
