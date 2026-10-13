# Reusable request actors

Spin accepts both fresh-per-request handlers and explicitly pooled handlers:

```ores
val handler = http.handler("Worker").pooled(32);
val registration = builder.get(rt borrow path, handler);
registration.unwrap();
```

The pooled worker receives each request through its ordinary mailbox and claims
that request's single-use token. Shared `actor` and isolated `isoactor` declarations
both work. Await the response, then return; **omit `self.end()`** to reuse the worker.
Actor fields persist; keep request-specific data local and clear any application
state that should not survive a request. No direct invocation bypasses mailboxes.

Each pool creates at most its configured number of current workers lazily and
selects them round-robin. The runtime prevents overlapping receive callbacks,
including while a callback awaits I/O. Exchange authority closes with the response;
a prior request's wrapper/token cannot operate on a later request. A crashed
worker's outstanding requests fail, and later dispatch can replace it after its
termination completes. An aborted/timed-out request cancels its worker and may
fail other queued requests assigned to that worker. There are no hidden retries.

Pool size is independent of HTTP listener admission, mailbox capacity, and carrier
thread count. Admission must remain bounded; this first API maps failed mailbox
dispatch to 500. The default unpooled handler still spawns one actor per request.
Pools live until their runtime/context closes. Server shutdown drains exchanges;
context closure also stops idle workers.

## Sustained test

```sh
export ORESLANG_SOURCE_DIR=/absolute/path/to/pinned/compiler
export ORES_JAVA=/absolute/path/to/jdk-25/bin/java
python3 scripts/sustained-load.py --concurrency 100 --seconds 180 --output /absolute/path/to/new-result-directory
# Repeat with --concurrency 1000 and 10000, each using a new output directory.
```

Each run establishes the requested number of HTTP/1.1 keep-alive connections,
warms up for ten seconds, then measures 180 seconds of closed-loop traffic. Each
client sends another request after receiving its previous response. Half the
clients target shared actors and half target isolated actors. The fixture has
32 workers per mode (64 total), listener capacity 20,000, and a three-byte body.
Worker IDs and reuse headers verify reuse; worker replacement/churn fails the
identity-count check. Response errors fail the run; there is no retry/reconnect.

Average/percentile response latency is measured from request send through complete
body receipt. Connection setup and warm-up are excluded. Requests started during
the window are allowed to drain and included in the latency distribution;
throughput counts those completed during the 180-second window. Mode results are
from a mixed workload, not separate full-concurrency runs per mode. This differs
from the earlier single-burst/new-connection experiment, so differences cannot
be attributed solely to actor reuse.

The harness saves result/metadata JSON, per-request numeric latency samples,
30-second progress snapshots, worker identity counts, final admission counters,
and sampled server RSS/CPU. A local Python client and a JVM interpreter server
share the host. No native-image, LLVM execution, or physical isolation performance
claim follows from these measurements.

The high-concurrency keep-alive run also needs
`-Dsun.net.httpserver.maxIdleConnections=20000`, in addition to
`-Djdk.httpserver.maxConnections=20000`. The JDK default permits only 200 idle
connections; the first 10,000-client attempt failed during warm-up when idle
connections were closed. The harness now supplies both limits explicitly. This
is benchmark configuration, not a change to the runtime's production defaults.
