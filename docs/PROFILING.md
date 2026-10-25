# Profiling reusable HTTP actors

Use the standard-library core flight recorder together with the native
`oreslang-otel` JSON Lines exporter. Telemetry is an explicitly pinned test
submodule; normal Spin applications do not import it automatically.

Build the runtime at `SOURCE_REF` and export `ORESLANG_SOURCE_DIR` and
`ORES_JAVA` as described in `REUSABLE_ACTORS.md`. Initialize submodules first:

```sh
git submodule update --init --recursive
# Run separately, on an otherwise idle host. Each output directory must be new.
python3 scripts/sustained-load.py --concurrency 100 --seconds 180 \
  --output /tmp/spin-baseline
python3 scripts/sustained-load.py --concurrency 100 --seconds 180 \
  --sample-every 1000 --core-perf --output /tmp/spin-profile
python3 scripts/summarize-profile.py /tmp/spin-profile
```

Sampling uses a fixed-seed Bernoulli draw with probability 1/N, only for requests
submitted after warm-up. Requests carry a diagnostic header to the fixture;
production clients cannot enable profiling in ordinary Spin applications.
Both runs use 32 shared and 32 isolated workers, equal client counts per mode,
persistent connections, no retries, and a ten-second warm-up. The profiled
fixture also performs timestamp/header reads, so the baseline comparison
includes those costs as well as sampled exports and core recording.

`stdout.log` contains correlated `oreslang-otel.v1` metrics with request IDs and
Unix timestamps, a structured drained log, and a standard-library stdout log.
Actor metrics identify shared/isolated mode through their service name.
`stderr.log` contains the core recorder's numeric phase timings. Metrics are
JSONL, not an OTLP exporter or W3C trace propagation implementation.

Warm sampled boundaries:

| Metric | Meaning |
|---|---|
| `admission.to_dispatch` | HTTP admission through supervisor dequeue and dispatch entry; includes queueing |
| `routing.dispatch` | Synchronous Spin routing, route preparation, middleware, and actor dispatch |
| `admission.to_claim` | Admission through the worker's claim and sampling-header read |
| `mailbox.move_to_claim` | Ownership move through worker claim, measured by core timestamps |
| `actor.prepare` | Claim timestamp through response invocation, including response headers |
| `response.await` | Response invocation through guest continuation resumption; includes async I/O and scheduling |
| `admission.to_response_continuation` | Admission through that continuation, before exporting metrics |

Intervals overlap: do not sum them. These are elapsed times, not CPU time.
The guest continuation can run after bytes reach the client. Actor metric
exports happen after response completion; they can still delay the worker's
next mailbox turn. Supervisor exports happen after dispatch and can delay the
next accept. Sampling overhead therefore affects even unsampled requests.
The summarizer rejects missing or incomplete sampled request records.

Core recording retains only its first 8,192 completed phases, then saturates.
It is a cold diagnostic sample, not a full-run or warm percentile distribution.
It exports on clean JVM shutdown, separately from guest telemetry. Do not
compare its cold mean directly with warm sampled means. For CPU attribution,
run a separate Java Flight Recorder diagnostic; do not include that run in the
instrumentation-overhead comparison.

The client and server share this host. Client event-loop lag and server resource
samples are retained; this is a closed-loop saturation experiment, not an
independent-client production capacity guarantee.

## Accept queue versus supervisor resumption (profile schema 2)

Warm profiles now require eleven correlated metrics per sampled request. The
original seven remain; four new disjoint intervals decompose
`admission.to_dispatch` exactly:

- `http.admission_to_queue`: admission bookkeeping up to the pending-accept handoff.
- `http.queue`: time waiting in the HTTP pending queue; zero when an accept Future
  is already waiting and receives the request directly.
- `accept.ready_to_resume`: accept delivery readiness to the first source timestamp
  after await. Includes Future completion, scheduler waiting, interpreter resumption
  and timestamp-call overhead; it is not pure scheduler queue time.
- `supervisor.prepare`: source resumption to dispatch, including request inspection
  and profiling metadata reads.

The summarizer validates all eleven metrics, nonnegative component intervals,
and exact component sum per trace. Archived seven-metric profiles remain supported
when no schema-2 marker is present. Core `http.accept.queue` is buffered and exported
on shutdown; the sampled otel intervals cover warm traffic using request IDs.
These additions are instrumentation, not a dispatcher optimization. Comparing
throughput against older fixtures must account for the extra timestamp/property
reads. No request headers or bodies are added to logs.
