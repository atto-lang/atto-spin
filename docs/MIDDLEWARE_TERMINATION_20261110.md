# Terminal middleware exchange ownership — 2026-11-10

This follow-up stacks on compiler-integration PR #39 and ports the behavior from
the older middleware PR #28 onto the tested canonical routing / Java compiler
pins. It does not change either compiler pin or the routing submodule gitlink.

## Contract

- A middleware hook returning false must already have transferred the response.
  If the exchange is still writable, Spin schedules an actor-owned 500 rather
  than leaving an admitted request stranded.
- A hook that has transferred the exchange ends dispatch even if it erroneously
  returns true. No subsequent hook, route handler, 404, 405 or OPTIONS fallback
  can reuse that capability.
- When middleware transfers a response, the response it produced remains
  authoritative; the framework must not overwrite it.
- The behavior applies to normal routing, unmatched routes, HEAD (no body),
  method-not-allowed, OPTIONS, authenticated routes and keep-alive reuse.

## Regression matrix

`tests/server.ores` has two explicit negative controls
(`X-Stop-Without-Response` and `X-Respond-And-Continue`) plus a second
middleware hook exposing the ordering through a response header.
`tests/integration.py` exercises the two controls across matched and
unmatched routes, automatic OPTIONS, synthetic 405, HEAD, and a reused HTTP/1.1
connection. The existing actor/transport tests remain in the same suite.

## Evidence and release gate

**Not executed at this branch head.** The current source-org Actions jobs were
returning no steps, which is runner admission failure, not successful testing.
Required: exact branch head + tree, clean `SOURCE_REF` Java checkout, clean
pinned routing gitlink, executed `scripts/test.sh`, final 200/403/500 and HEAD
body assertions against a real guest HTTP listener, run attempt, nonzero job
steps and logs. NativeAOT, LLVM and .NET Spin HTTP execution remain unverified.
Keep this follow-up draft until compiler-backed guest evidence and independent
review are obtained.
