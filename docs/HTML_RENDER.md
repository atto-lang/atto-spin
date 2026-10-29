# Native Oreslang HTML rendering (initial Spin slice)

**Status: experimental; requires exact pinned compiler.** This change adds a
typed and safely escaped HTML value in `src/render/html.ores`, plus a
`spin.render_html` response adapter. It deliberately does **not** add an
actor kind to the core compiler. Use an existing `define actor` or
`define isoactor` with a single-use `http.claim` token.

## Shape and ownership

`Html` is a native Oreslang class whose sole public constructor escapes
**untrusted text**, never parses markup. Fixed-tag class factories construct
HTML and `fragment` composes child values. The class's encoded storage is
private. `markup()` exposes serialization for HTTP output, but passing it
back to the public constructor treats it as untrusted and escapes it.

The current API intentionally has **no caller-defined tags, dynamic
attributes, URLs, script/style tags, raw HTML, inline event handlers, or
Java/C# renderer**. In particular, the existing `spin.html(..., String)`
remains a low-level raw-string API; user input must not go through it.
Do not use `markup()` to build an unsafe raw-string HTML response.

This initial encoder escapes `& < > " '` and replaces NUL with the Unicode
replacement character. Escaping is performed in native Oreslang with the
runtime's `replace_literal` storage primitive (available at SOURCE_REF).
It is **not** a CSS, JavaScript, URI, or attribute sanitizer.

## Usage

```ores
import module spin from "../src/spin";
import module spin_html from "../src/render/html";

// Inside an ordinary actor's receive callback after http.claim:
val title = spin_html.Html.h1(spin_html.Html.text(request.query("name")));
val page = spin_html.Html.document(
    spin_html.Html.html(spin_html.Html.body(title))
);
val Future<void> reply = spin.render_html(rt borrow request, 200, rt borrow page);
await reply;
self.end();
```

See `examples/render.ores` for a full routing + isolated actor example.
`spin.render_html` delegates to the existing single-owner bounded HTTP
response path. It sets `Content-Type: text/html; charset=utf-8` and
`X-Content-Type-Options: nosniff`. It does not launch another actor,
create additional response writers, or bypass request ownership.

## Tests, limits and next gates

The executable `tests/html_render.ores` exercises escaping, nested tags,
Unicode, NUL, and injection attempts. `scripts/test.sh` runs its compiler
check and asserts its golden output against the exact SOURCE_REF, alongside the
existing integration suite. **Adding these checks does not constitute a
successful run**; inspect executed CI steps and exact-head evidence.

The current renderer materializes the entire response as strings. Large
documents are not yet bounded in allocation or render time and must not be
promoted as hard-RT or streaming-safe. Follow-ups: byte-bounded/streamed
serialization with cooperative backpressure, typed attribute/URL policies
and sanitizer tests, compile-time static HTML folding, actor cancellation
tests, and independent Java/LLVM/.NET/Wasm guest execution. LLVM package
execution remains unsupported at Spin's documented pin. Live UI actors
are explicitly out of scope until streaming, transports, and per-session
ownership/cancellation are verified.

No actor may re-enter its handler while awaiting an HTTP response: use
the runtime's non-reentrant mailbox semantics. Pool reuse is optional and
should keep request-local HTML state out of actor fields.
