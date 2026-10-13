# Native Oreslang HTTP transport (experimental)

This feature branch introduces an **opt-in transport seam** for Spin that
calls `std/http_server` and `std/net`, keeping the HTTP parser, response bytes,
and request control flow in `.ores`. The Java backend only implements
nonblocking readiness and Future completion.

- Core compiler/socket source pin: `41353d2a64103c8a97608ac2595a212704ebf5d7`
  (native owned-token API draft branch; update pin after fixes).
- `src/spin_native_http.ores` wraps the asynchronous owned-token task.
- `tests/native-http-transport.ores` demonstrates two concurrent TCP request
  lifetimes and does not route requests to actors.
- Existing `src/spin.ores`, `tests/pooled-load-server.ores` and the established
  `SOURCE_REF` are **unchanged**. Default Spin still uses old Java HTTP.

## Merge gates

1. Exact-source GraalVM JIT, AOT and hybrid smoke for the native transport.
2. Supervised bounded lifecycle and cancellation for arbitrary concurrent
   request tasks, without orphan Futures or socket tokens.
3. Actor request/reply routing via typed messages (not passing raw socket
   capabilities into actors), including middleware, streaming, error handling,
   and old Spin compatibility.
4. HTTP/1.1 production parser coverage: general headers, body framing,
   chunked transfer, keepalive/pipeline limits, timeouts, and request-smuggling
   negatives. Today's strict parser only supports a deliberately narrow
   GET/HEAD dialect.
5. Matched sustained 100/1,000/10,000-client tests at equal semantics and
   hardware, with queue wait, socket readiness, actor admission, and p99
   profiling. Record failures/admission rejection and CPU separately.

**Do not merge this adapter as a replacement for Spin HTTP until all gates pass.**
