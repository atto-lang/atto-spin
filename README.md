# oreslang-spin

An Oreslang HTTP framework that dispatches each matched request to a shared
actor or isolated actor. Handlers use fresh actors by default; opt-in pools reuse
workers across requests. It uses `oreslang-http-routing` for route
matching and native `http` capabilities from `oreslang-source.java` for I/O.

This is a **draft HTTP/1.1 framework**. Its runtime and router dependencies are
pinned to tested compiler/router snapshots; it is not a published stable release.

## Run

Use JDK 25 and Maven. Clone the compiler at the SHA in SOURCE_REF and build it:

```sh
git clone https://github.com/ores-truffle-oreslang/oreslang-source.java.git ../oreslang-source.java
git -C ../oreslang-source.java checkout "$(cat SOURCE_REF)"
(cd ../oreslang-source.java && mvn -q -DskipTests package dependency:build-classpath -Dmdep.outputFile=target/classpath.txt)
git submodule update --init
export ORESLANG_SOURCE_DIR="$(cd ../oreslang-source.java && pwd)"
./scripts/compiler.sh --platform=server --allow-net=127.0.0.1:8080 examples/mixed.ores
```

Set `ORES_JAVA` if the appropriate Java executable is not on PATH. The example
serves GET `/hello` in a shared actor and POST `/echo` in an isolated actor.
The application's supervisor calls `server.shutdown(grace_ms)` to drain it.

## Application model

[examples/mixed.ores](examples/mixed.ores) is a complete runnable application.
The central registration/dispatch API is:

```ores
val builder = spin.builder();
val path = http_routing.path("/hello", arr[http_routing.literal("hello")]);
builder.get(rt borrow path, http.handler("SharedHello")).unwrap();
val app = builder.build().unwrap();
val server = http.listen("127.0.0.1", 8080, 128, 1048576, 30000);
loop {
  val request = await server.accept();
  app.dispatch(request);
}
```

Register `define actor` for shared execution or `define isoactor` for isolated
execution. The declaration determines the route's execution policy. Factories
reference immutable actor code, not application closures. The actor receives a
single-use token as `ActorMail<String>` and claims its exchange:

```ores
define isoactor Hello as
  receive(ActorMail<String> mail): void {
    val request = http.claim(mail.value);
    await request.respond(200, "text/plain", "hello");
    self.end();
    return;
  }
end
```

The actor owns guest access to the request/response capability. The connection
FD stays with core HTTP so keep-alive continues across requests and actor kinds.
Every operation rejects a stale sender or wrong actor. Shared routes still have
one response writer; sharing arbitrary mutable request objects is not exposed.
See [docs/OWNERSHIP.md](docs/OWNERSHIP.md) for exact guarantees.

## Routes, middleware, and extraction

`builder.route(method, rt borrow path, handler, pipeline_id, contract_id, operation_id)`
accepts any method supported by the router; `get` and `post` are conveniences.
Static, parameter, and wildcard matching, strict slash handling, HEAD fallback,
OPTIONS, 404, 405, and Allow synthesis come from the router.

`builder.use(hook)` registers a `Fnc<bool(borrow HttpExchange)>` supervisor middleware.
Hooks run in registration order after routing metadata/captures are attached,
including for framework-generated errors and OPTIONS. On an unmatched request,
`operation_id` is set **before** middleware to `spin.404`, `spin.405`,
`spin.414`, or `spin.204` (automatic OPTIONS), with pipeline/contract IDs
set to -1. Middleware must apply any global security policy independently of
route-specific metadata; no route match does not imply authorization.
Return true to continue;
return false after scheduling a response to stop dispatch. A hook returning
false without transferring the response produces an actor-owned HTTP 500 rather
than leaving the client hanging. If a hook has already transferred the response,
the framework stops dispatch even when the hook incorrectly returns true;
another hook or handler cannot reuse the revoked supervisor exchange. A hook
may inspect pipeline_id or contract_id to select auth/validation rules. Actor-local processing
belongs in that actor's receive method or synchronous helper functions, where
it cannot retain a supervisor closure. Builder operations return Result and a
second build or later registration fails.

Handlers can read `param`, `param_at`, `header`, `query`, and `cookie` values.
`spin.require_param`, `require_query`, and `require_header` return typed
`Result<String,String>` values for required nonempty inputs. Application-specific
schema validation and JSON decoding use the application's serialization library;
contract_id is preserved for selecting it. No validation is implied merely by
setting a contract ID.

`spin.text`, `html`, `json`, and `redirect` return Future<void>. The JSON helper
expects already serialized JSON. With current cross-file inference, annotate a
helper's result before awaiting it, as the example does. Native respond/start/
write/finish support UTF-8 responses; respond_bytes/read_chunk/write_bytes support
binary bodies and streaming with bounded chunks and one pending I/O operation.
The test app demonstrates CORS headers, auth, wildcard captures, binary echo,
SSE-style response streaming, and graceful shutdown.

## Verify and measure

```sh
./scripts/test.sh
ORESLANG_COMPILER="$PWD/scripts/compiler.sh" python3 scripts/benchmark.py
```

Tests require clean compiler/router checkouts at exact pins and execute native
Oreslang, not a compiler test double. [docs/VALIDATION.md](docs/VALIDATION.md)
records local checks and CI activation requirements; [docs/BENCHMARK.md](docs/BENCHMARK.md) records the baseline.
[docs/PROGRESS.md](docs/PROGRESS.md) tracks the fifteen implementation steps.

The first backend is JDK HTTP/1.1. TLS termination, HTTP/2, WebSockets, multipart,
compression, JSON codecs, and signed cookies are outside this draft. Request
limits and JVM-wide parser/connection defaults are described in the runtime's
HTTP_SERVER.md; they must be configured before JDK HTTP server initialization
when embedding in another host. No automatic handler retry is performed.

## Backend compatibility

See [the compiler compatibility contract](docs/BACKENDS.md) for pinned Java/LLVM
revisions, reproducible checks, and unsupported features.

## Reusable workers and sustained load

See [reusable request actors](docs/REUSABLE_ACTORS.md) for
`http.handler("Worker").pooled(32)` and three-minute keep-alive load tests.

## Repository ownership and migration (2026-11-08)

**AttoLang** is the current public language; this code is still maintained under `ores-truffle-oreslang/oreslang-spin` in the original Oreslang organization. Preserve working `.ores` files, repo naming and package/CLI compatibility until an independently tested change migrates them.

- **Owns:** web framework/integration experiments for AttoLang and guest execution contracts.
- **Not this repository:** production multi-tenant cloud management.
- **Code ownership:** [atto-lang](https://github.com/atto-lang) is the destination for language semantics, core/std, compilers, developer tools, libraries and demos. [atto-co](https://github.com/atto-co) independently owns managed infrastructure, tenancy, identity, billing and production deployments. A separate `atto-*` repo is not by itself a verified Git transfer or equivalent source tree.
- **Proposed migration, not authorization:** existing repository into `atto-lang/oreslang-spin` with original name, history and numeric GitHub ID; no first-wave direct move into `atto-co`. A later production product spinout requires its own approval.

**Repository transfer playbook:** coordinate in [issue #26](https://github.com/ores-truffle-oreslang/.github/issues/26) and review [private migration draft #25](https://github.com/ores-truffle-oreslang/.github/pull/25). Capture stable numeric ID, exact head SHA/tree, PRs, releases, packages, GitHub Pages, dependencies, branch/ruleset protections, Actions runners, secrets, App/webhook grants and rollback plan. Require explicit source and target administrators plus independent security reviewer. Never export/mirror private sources as a shortcut. After an actual GitHub ownership transfer, verify unchanged ID/history/tree, re-bind security controls and run exact-head CI. A job with `steps=[]` or `steps=null` is `NOT_EXECUTED`, and host/reference results do not prove compiled AttoLang guest or production HTTP execution.
