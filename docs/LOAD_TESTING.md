# Concurrency and actor-admission load tests

`load-matrix.py` runs 100, 1,000, and 10,000 concurrent client attempts against
5, 20, 50, and 300 in-flight request/actor slots, for shared and isolated routes.
Each combination starts a fresh server, warms it with 50 sequential requests,
and runs three simultaneous bursts, with half a second between bursts. There
are 24 combinations, 72 bursts, and 266,400 measured attempts. Both handlers
execute the same response operation and return the same three-byte body.

```sh
export ORESLANG_SOURCE_DIR=/absolute/path/to/pinned/oreslang-source.java
export ORES_JAVA=/absolute/path/to/jdk-25/bin/java
python3 scripts/test-load-matrix.py
python3 scripts/load-matrix.py --output /absolute/path/to/new-results-directory
python3 scripts/summarize-load.py /absolute/path/to/new-results-directory
```

The compiler must be built, clean, and match SOURCE_REF. The router must match
the gitlink. Smaller smoke runs can use `--concurrency 10 --actors 5 --repeats 1`.
The output directory must not already exist. Run locally; the fixture binds only
to loopback on an ephemeral port and exposes a benchmark-only shutdown endpoint.
The driver terminates only its own server process on failure.

## What the dimensions mean

Spin spawns a fresh actor per admitted request. “Actor limit” here means HTTP
listener admission capacity, held until both response and actor finalization
complete. It does not create a reusable pool of exactly N actors or set the
number of scheduler threads. The JVM uses Java actor carriers for a reproducible
baseline. Shared versus isolated means the runtime's actor modes; this benchmark
does not prove physical heap or process isolation.

All client tasks start behind a barrier. Each opens one TCP connection and sends
one request. There are no retries or hidden client-side admission gates. Requests
above the listener's capacity may receive 503. Separate status counts and client
errors prevent fast rejection from being presented as useful throughput.
Maximum observed connected client sockets is reported; requested task concurrency
is not a claim that all requests reached the server simultaneously.

The current HTTP API uses the same capacity for its TCP listen backlog and
request admission. A five-slot run therefore also requests backlog five. macOS
may clamp backlog further (128 on the measured machine). This experiment cannot
independently attribute differences to actor capacity versus connection queueing.

The driver raises `jdk.httpserver.maxConnections` from the runtime default of
1,024 to 20,000, and runs each JVM with `-Xms256m -Xmx2g`. No OS networking limits
are changed. Socket/connect timeouts and local resource exhaustion remain visible.

## Reading the results

- `REPORT.md`, `summary.csv`, and `summary.json`: pooled successful-request
  percentiles, success fraction, rejection/error counts, and successful burst rate.
- `results.jsonl`: each burst, including client launch delay, connection latency,
  header-receipt latency (a TTFB proxy), event-loop lag, and server timing headers.
- `*.samples.json`: every attempt, including status, error, and measured intervals.
- `*.server.json`: server counters including all warm-ups and shutdown requests;
  completed must equal accepted and active must reach zero after shutdown.
- `*.resources.json`: sampled JVM RSS and `ps` CPU readings, including startup.
- `metadata.json`: hardware, file descriptor limit, exact compiler/router commits,
  Java version/options, and hashes of the harness and fixture.

This is a local JVM interpreter burst-overload test, not steady-state capacity,
Graal native-image performance, or a distributed load test. Client and server
compete for the same CPU. High client event-loop lag or launch delay invalidates
interpreting latency as server processing time. Warm-up is deliberately short;
three repeats expose variation but are insufficient for strong actor-mode speed
claims. For steady-state sizing, follow this with persistent connections, a
separate load-generator host, independently configurable backlog, and longer
measurement windows.

Successful-request latency starts when its task resumes after the barrier and
includes connection establishment and full response receipt. The separate burst
latency includes launch delay from the common barrier release; do not subtract
percentiles from each other to estimate server service time.
