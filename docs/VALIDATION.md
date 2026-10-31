# Validation

## Native acceptance from a fresh compiler build (2026-10-31)

Run `bash scripts/ci-native.sh` from an exact-head Spin checkout with
`ORESLANG_SOURCE_DIR` pointing to the full clean Java `SOURCE_REF` checkout
and the router submodule initialized at the committed gitlink. The script:

1. Rejects modified/staged/untracked Spin, Java compiler and router inputs.
2. Requires an executable JDK 25, rejecting other Java major versions.
3. Executes `mvn -B -ntp -q -DskipTests clean package dependency:build-classpath
   -Dmdep.outputFile=target/classpath.txt` in that pinned compiler checkout.
4. Requires fresh `OresMain.class` and a non-symlink, nonempty classpath file.
5. Rechecks source admission and runs the actual native Spin HTTP integration via
   `scripts/test.sh` before printing `SPIN_PINNED_NATIVE_ACCEPTANCE_PASS`.

The mocked `scripts/test-preflight.sh` checks the *orchestration*, including
wrong-JDK and Maven-failure rejection, but **does not** run native Oreslang.
A successful native acceptance claim requires an actual runner/job/step
receipt from `ci-native.sh` on an authorized full source checkout.

Private source mirror restrictions remain enforced; a partial mirrored router
subtree must not be relabeled as a complete exact-tree native test.

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
