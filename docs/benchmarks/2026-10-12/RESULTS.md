# Spin concurrency / actor-admission experiment — 2026-10-12

Ran **266,400 measured attempts** in 72 bursts across 24 configurations:
100/1,000/10,000 client tasks × 5/20/50/300 admission slots × shared/isolated.
There were **11,305 validated successes, 255,093 HTTP 503s, and two client
timeouts** (10,000-task, five-slot shared run). No retries. All 24 servers drained
to zero active exchanges and completed all admitted requests. The two timeouts
are not successes and are retained in the per-burst samples.

At 300 slots, 100-task bursts achieved 100% success, about 1,286–1,344 successful
burst requests/s, and 81–82 ms p95. At 1,000 tasks, success fell to roughly 31%.
At 10,000 tasks, success was only 5.55–5.70% with 300 slots. Fast 503 responses
must not be counted as useful request throughput.

**These measurements do not establish a server throughput ceiling.** This is
an overload burst test with new TCP connections, not sustained keep-alive load.
The five-slot listener also requests a TCP backlog of five. Long connection
queueing/retransmission delays dominate several five-slot measurements. At
10,000 tasks, connection p95 is approximately 824–920 ms; the load generator's
per-run p99 event-loop delay reaches 519–620 ms. It reaches up to 10,000 connected
client sockets, but cannot deliver or time them without substantial scheduling
delay. Server RSS peaks between 231 and 729 MiB across configurations, including
startup. There is no basis here to declare shared or isolated intrinsically faster.

Environment: macOS ARM64, 18 logical CPUs, 48 GiB RAM; Temurin JDK 25; Java actor
carriers; JVM interpreter; 2 GiB heap ceiling. Transport maximum connections was
raised to 20,000 for this experiment. OS backlog maximum was 128, ephemeral port
range 49152–65535, process FD limit 1,048,575. Client and server shared the host.

The next useful experiment is sustained keep-alive traffic from a separate
load-generator process/host, with TCP backlog decoupled from actor admission.
Do not tune production limits from these overload bursts alone.

See [reproduction and methodology](../../LOAD_TESTING.md). Exact pins, JVM flags,
and harness hashes are in [metadata.json](metadata.json); extended connection,
client scheduling, memory, and success metrics are in [summary.csv](summary.csv).
The table pools three repeats per configuration. Raw samples and logs are kept
in the local experiment output, not committed to this repository.

| Concurrent attempts | Actor limit | Mode | Success % | 503 | Client errors | Success req/s | p50 ms | p95 ms | p99 ms | Peak RSS MiB |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 5 | shared | 8.0 | 276 | 0 | 11.65 | 20.1 | 1017.81 | 1019.38 | 231.4 |
| 100 | 5 | isolated | 6.0 | 282 | 0 | 17.04 | 17.7 | 1013.47 | 1013.47 | 242.9 |
| 100 | 20 | shared | 20.0 | 240 | 0 | 597.61 | 24.74 | 32.64 | 33.47 | 266.0 |
| 100 | 20 | isolated | 20.33 | 239 | 0 | 579.85 | 24.65 | 39.71 | 42.43 | 256.9 |
| 100 | 50 | shared | 50.33 | 149 | 0 | 939.64 | 36.16 | 55.07 | 59.24 | 273.9 |
| 100 | 50 | isolated | 50.0 | 150 | 0 | 928.22 | 36.02 | 52.35 | 55.01 | 276.9 |
| 100 | 300 | shared | 100.0 | 0 | 0 | 1344.09 | 45.79 | 80.77 | 86.71 | 305.9 |
| 100 | 300 | isolated | 100.0 | 0 | 0 | 1285.9 | 48.36 | 81.82 | 88.29 | 307.9 |
| 1000 | 5 | shared | 2.53 | 2924 | 0 | 18.6 | 109.19 | 1029.15 | 2027.0 | 284.3 |
| 1000 | 5 | isolated | 2.33 | 2930 | 0 | 22.8 | 109.55 | 1020.09 | 1020.67 | 289.7 |
| 1000 | 20 | shared | 3.27 | 2902 | 0 | 258.1 | 116.78 | 125.51 | 125.95 | 303.8 |
| 1000 | 20 | isolated | 3.13 | 2906 | 0 | 247.17 | 117.71 | 126.65 | 127.81 | 309.2 |
| 1000 | 50 | shared | 6.1 | 2817 | 0 | 475.82 | 123.38 | 128.18 | 128.74 | 311.3 |
| 1000 | 50 | isolated | 6.13 | 2816 | 0 | 448.02 | 125.42 | 134.0 | 136.73 | 313.3 |
| 1000 | 300 | shared | 31.27 | 2062 | 0 | 1415.85 | 148.44 | 257.97 | 268.26 | 385.5 |
| 1000 | 300 | isolated | 30.53 | 2084 | 0 | 1429.69 | 142.72 | 243.04 | 257.33 | 392.1 |
| 10000 | 5 | shared | 2.34 | 29296 | 2 | 21.07 | 1211.72 | 4128.05 | 11128.95 | 675.6 |
| 10000 | 5 | isolated | 2.06 | 29382 | 0 | 45.17 | 1275.64 | 4120.77 | 5194.32 | 656.4 |
| 10000 | 20 | shared | 2.28 | 29317 | 0 | 153.65 | 1296.55 | 1439.42 | 1467.44 | 707.8 |
| 10000 | 20 | isolated | 2.14 | 29358 | 0 | 144.51 | 1301.88 | 1434.03 | 1503.96 | 729.0 |
| 10000 | 50 | shared | 2.59 | 29223 | 0 | 168.91 | 1349.34 | 1422.84 | 1512.88 | 675.7 |
| 10000 | 50 | isolated | 2.95 | 29116 | 0 | 196.57 | 1326.32 | 1410.39 | 1482.02 | 657.3 |
| 10000 | 300 | shared | 5.55 | 28335 | 0 | 365.4 | 1378.51 | 1521.74 | 1544.81 | 646.9 |
| 10000 | 300 | isolated | 5.7 | 28289 | 0 | 371.44 | 1424.54 | 1494.85 | 1498.06 | 708.8 |
