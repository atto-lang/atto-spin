# Reusable actors: sustained HTTP load

**1,681,479 measured responses succeeded.** Zero errors, admission rejections, or retries. Each run used 32 shared and 32 isolated workers; stable worker IDs and reuse headers verified reuse for every measured response. All servers completed every admitted request and drained to zero active exchanges.

| Total concurrent clients | Mode | Seconds | Responses | Mean ms | p95 ms | p99 ms | Completed req/s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | shared | 180.0 | 285996 | 31.415 | 35.63 | 44.011 | 1588.59 |
| 100 | isolated | 180.0 | 285996 | 31.415 | 35.633 | 43.983 | 1588.59 |
| 1000 | shared | 180.0 | 286855 | 313.687 | 357.753 | 431.234 | 1590.86 |
| 1000 | isolated | 180.0 | 286860 | 313.687 | 357.54 | 431.338 | 1590.89 |
| 10000 | shared | 180.0 | 267963 | 3358.911 | 4912.684 | 6966.239 | 1460.91 |
| 10000 | isolated | 180.0 | 267809 | 3359.069 | 4891.889 | 7096.561 | 1460.05 |

Each concurrency is a **mixed run**: half the keep-alive connections target each mode. Rates in the table are per mode; sum them for total throughput. Ten-second warm-up and TCP setup are excluded. Latencies cover requests started within the 180-second window, including their final drain; rate counts only measured requests completed inside the window.

The workload continually replaces each completed request on the same connection. This is closed-loop load, not an open-loop arrival-rate/SLA experiment. Client and server share the local macOS host; the server uses the JVM interpreter and Java carriers. No LLVM/native-image or physical isolation claim is made.

Do not attribute differences from the earlier short bursts solely to actor reuse: connection reuse, warm-up, and workload shape also changed. See summary.csv for RSS, client scheduling lag, and drain time. Raw result/metadata, numeric latency samples, progress logs, resource samples, and server counters remain in the individual run directories.

## Transport correction and limits

The initial 10,000-client pilot failed during warm-up with 271 client EOF errors;
it produced no measured-window samples. JDK 25 defaults to only 200 idle
keep-alive connections and closes surplus idle connections. The successful
10,000-client run used `-Dsun.net.httpserver.maxIdleConnections=20000` in addition
to the 20,000 total-connection limit. The 100- and 1,000-client runs used the
200-idle default and passed. The failed pilot is preserved in local outputs;
it is not included in the successful-run totals. The harness now sets the larger
idle limit explicitly for reproducibility. No runtime production defaults changed.

At 100 clients sampled RSS was approximately 372 MiB early and 376 MiB late;
this is a three-minute observation, not a proof of absence of long-term leaks.
Consult summary.csv for all resource measurements. Pools retain actor fields
across requests; application request state should remain local or be cleared.
A timeout/abort can terminate its worker and fail other requests queued to it.
Existing fresh-actor behavior remains the default; pooling is opt-in.

See [usage and methodology](../../../REUSABLE_ACTORS.md). Each result file
records its exact configuration and compiler/router commits. Warm-up/setup are
excluded, and each concurrency was measured once for 180 seconds. Results are
not directly comparable to earlier new-connection bursts, and are not a claim
that actor reuse alone caused a particular speedup.
