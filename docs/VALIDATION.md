# Validation

## Clean pinned compiler build (merged source-admission gate)

For a native acceptance run, invoke `bash scripts/ci-native.sh` from a clean,
exact-head Spin checkout with `ORESLANG_SOURCE_DIR` set to the complete clean
Java compiler checkout at `SOURCE_REF` and the router at the committed gitlink.
The script validates immutable pins and source cleanliness, checks JDK 25,
rebuilds compiler classes and the classpath from scratch, checks artifact paths,
then executes native HTTP tests through `scripts/test.sh` before emitting
`SPIN_PINNED_NATIVE_ACCEPTANCE_PASS`.

`scripts/test-preflight.sh` checks orchestration and hostile source mutations
with mock executables. Its PASS marker never constitutes compiler-backed guest
or HTTP acceptance. A release requires a nonzero-step exact-head runner receipt
from the real native acceptance command; a private partial mirror is not a
substitute for exact physical source provenance.


## Preflight hardening (2026-11-10)

The suite now requires the compiler directory to be the checkout root, matching
the backend checker. Its host-only preflight regression covers nested-directory
rejection, dirty/untracked compiler and router files, and failed Git status
inspection. The regression fixture also checks that the builder program is
executed after its source check; previously it rejected that invocation itself.

Local validation at Java pin `6d8eb70048eafc9a84c5aebe9c1bb06104f16e76`:
`bash scripts/test-preflight.sh` passes, all 21 backend-checker host tests pass,
and `scripts/test.sh` passes routing semantics, builder execution, and 110 real
HTTP assertions. Host preflight fixtures are separate from that guest execution
evidence. These checks do not establish LLVM Spin execution or hosted CI success.

The native HTTP and actor implementation is tested in the compiler repository's
NativeHttpTest. It checks strict path decoding, malformed UTF-8, sender
revocation, double move, wrong-actor claims, one-time claim, exactly-once
response completion, shared-actor streaming, and rejection of ordinary borrows
across actor await. The broader compiler/runtime suite covers actor lifecycle,
transport isolation, futures, and ownership.

The router's existing golden semantics suite is executed against the exact
compiler pin. It covers precedence, static-branch backtracking, named/wildcard
captures, strict slashes, snapshot behavior, metadata, HEAD/OPTIONS, 404/405,
Allow, and route limits. Two missing golden lines were restored for assertions
already in the test source; no routing outcomes were removed.

The Spin integration test launches a real Oreslang server on an ephemeral port
and uses HTTP clients. It exercises shared/isolated routes, fresh actor state,
request IDs, the imported Future-returning helper regression, binary streaming,
query/cookie/capture extraction, strict paths, HEAD/OPTIONS, CORS/auth middleware,
middleware error containment, bounded/chunked bodies, invalid UTF-8, actor panic,
deadlines, keep-alive, 80 concurrent mixed requests, 16-slot overload and recovery,
disconnect recovery, and graceful shutdown with zero active exchanges.

Run `scripts/test.sh` with a clean compiler checkout at SOURCE_REF and the exact
router gitlink. The launcher is built with JDK 25. Local baseline validation uses
interpreter mode; native-image and optimizing-Graal deployment profiles are not
claimed by these results.

CI templates are included under docs/ci. GitHub rejected the initial push of
workflow files because the connected OAuth credential lacks workflow scope;
the definitions are reviewable templates rather than active workflows. With a
workflow-authorized credential, install checks.yml.example and native.yml.example
as .github/workflows/checks.yml and native.yml. The former checks script syntax.
The latter is manual because dependencies are private: configure
ORESLANG_READ_TOKEN with read access to both before dispatching it. Static CI
success is not evidence that native integration ran.

The companion runtime/router GitHub Actions jobs did not start: GitHub reported
failed account payments or an insufficient spending limit. Their hosted checks
remain unverified; the passing results below are local, on exact dependency pins.

Pinned local results on 2026-10-07: **1,232 core tests, zero failures/errors/skips**;
router native golden and runner-contract suites pass; **55 Spin HTTP assertions
pass** including handlers that omit self.end and shutdown with a live actor.

The follow-up keyword-borrow migration was validated against current main plus
the pinned compiler hardening commit. Core regressions include explicit singleton
tuples, grouping, borrow suspension, cleanup retention, and async/actor diagnostics.


## PR #37 framing status on merged Spin main (2026-11-12)

The current branch requires **119 functional + 25 live raw-wire = 144**
assertions, including three framework routing outcome checks merged in #41.
Earlier private candidate execution with a local test-only Java patch passed
141 checks on a previous PR head. Those checks do not attest this final branch.
The pinned Java `SOURCE_REF` is still unsafe for malformed Host ports.
Merge is blocked on independent reviewed Java authority fix, source pin update,
fresh executed exact-PR-head native checks and independent Spin approval.
