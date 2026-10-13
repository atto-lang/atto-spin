# 100 persistent clients, 10,000 request slots/sec: latency and logging audit

Eight local runs completed 1,634,155 successful measured responses, with zero
response errors, retries, or reconnects. Every response validated body, actor
mode and worker identity. Each run used exactly 32 stable reusable workers,
all measured responses reported reuse, and every server drained to zero active
requests with accepted = completed and no admission rejections.

This target was **not achieved**: integrated throughput was approximately
8,300 requests/sec. Missed scheduled slots are explicit in each result; zero
HTTP errors does not mean the offered target was sustained.

## Method and provenance

Each actor mode runs independently with 100 TCP clients, ten seconds warm-up,
then 30 seconds measured. The same profiled source fixture is used for all runs.
Clients schedule 100 slots/sec each, staggered by 100 microseconds; each keeps
one outstanding request. An overdue slot is skipped without a catch-up burst.
Response and scheduled latency are reported separately; scheduling lag includes
waiting for a prior response and is not solely OS/load-generator CPU lag.
Requests scheduled within the interval can finish just after its end. This
bounds in-flight work rather than building an unbounded queue or pipelining.

Matching GraalVM Community 25.3.4.1; macOS 26.6.2; Mac16,5; 16 logical CPUs;
48 GiB RAM. Server and Rust client shared the workstation with active browser
processes. Runs are sequential, not randomized trials; these are local JVM
measurements, not a production ceiling or Native Image throughput evidence.

Baseline compiler: `62646c4372244723813ab06f2d122a6b2f5c0995` (#851).
Integrated compiler measured here: `1e099518d1a7438abf0f5426f63a3b971bd5c357`
(#875): #851/#862 semantically merged with main's indexed method lookup, plus
sampled core capture. Metadata records each built-JAR hash and dependency SHA.
OTel: `5fe62a3447e77072cfd30850a96ef654a18008f7` (native Oreslang JSONL).
Later #875 adds `http.admission.to_handler`; that phase is not present in these
original eight captures. Preserve this distinction when comparing revisions.

## Results

| Configuration | Mode | Achieved RPS | Response p50 ms | p95 ms | p99 ms | Missed target slots / 300,000 |
|---|---|---:|---:|---:|---:|---:|
| Baseline, logging disabled | shared | 2258.8 | 43.841 | 45.237 | 46.503 | 232237 |
| Baseline, logging disabled | isolated | 2233.8 | 44.545 | 45.950 | 47.304 | 232987 |
| Integrated, logging disabled | shared | 8309.6 | 11.923 | 12.734 | 13.701 | 50712 |
| Integrated, logging disabled | isolated | 8365.0 | 11.768 | 12.548 | 13.362 | 49049 |
| Integrated, core 1/1024 phases | shared | 8389.2 | 11.814 | 12.621 | 13.368 | 48323 |
| Integrated, core 1/1024 phases | isolated | 8358.8 | 11.890 | 12.620 | 13.036 | 49236 |
| Integrated, core + OTel 1/1000 requests | shared | 8295.5 | 11.959 | 12.773 | 13.249 | 51135 |
| Integrated, core + OTel 1/1000 requests | isolated | 8261.1 | 12.002 | 12.805 | 13.373 | 52166 |

The integration improved throughput 3.68x shared / 3.74x isolated and reduced
p99 about 70.5% / 71.8%. The baseline comparison includes newer mainline changes;
it does not isolate #862's contribution. Shared and isolated throughput differ
less than 1% on the integrated disabled pair. Here isolated means source
`isoactor` ownership/message-copy semantics; it is not physical heap isolation.

Core-only throughput differs from disabled by +0.96% shared / -0.075% isolated.
Adding sampled OTel to core differs by -1.12% / -1.17%. This small sequential
sample does not establish precise overhead ratios. Core collects primitive
numeric rows with formatting and I/O deferred to shutdown; OTel constructs
correlated JSON in guest code and writes stdout. Sampling budgets differ:
1/1024 phases versus 1/1000 requests, each producing seven guest metric rows.

## Bottleneck evidence

All four core captures retained 2615–2640 rows and reported `saturated:false`.
Core warm summaries exclude the first 15 seconds from recorder configuration,
independently of the client's warm-up clock. Both OTel runs exported exactly
248 complete traces, with all seven expected metrics exactly once per ID.

| Warm OTel boundary, mean ms | Shared | Isolated |
|---|---:|---:|
| Admission to supervisor dispatch | 11.8115 | 11.8630 |
| Routing and native dispatch | 0.1106 | 0.1115 |
| Mailbox transfer to claim | 0.0135 | 0.0132 |
| Actor response preparation | 0.0064 | 0.0061 |
| Response await | 0.0286 | 0.0254 |

In the shared core-only run, I/O queue mean was 0.00764 ms and work mean
0.00899 ms, versus request lifetime mean 11.877 ms. The dominant elapsed
interval is before supervisor dispatch. A single supervisor spends roughly
0.11 ms per route dispatch, leaving little room for a 0.10 ms/request target.
The causal inference is serial supervisor routing saturation under this load;
this is not evidence of filesystem blocking in these minimal no-FS handlers.
Boundaries overlap and must not be added as exclusive CPU time.

Follow-up: reduce or shard the supervisor routing path while preserving
one-callback-per-actor, request capability ownership, overload admission and
cancellation. Preserve routing policy in Oreslang; move static resolution out of
the serving path where compiler evidence supports it. Separate worker mode from
routing throughput before attributing improvements to actor isolation.

## LLVM boundary

LLVM main `8607da453bbee42e27572a5b84ebf32f40a8863c` plus build fix #352
builds with LLVM 16 and 21. The supported shared integer guest handler emits
verified IR, compiles through Clang, and exits 43. The actual pooled Spin fixture
rejects with exit 1, diagnostic `expected fnc or routine at byte 0`, and zero IR.
Both LLVM/shared and LLVM/isolated HTTP matrix cells are unsupported. No host
HTTP adapter is mislabeled as LLVM Spin execution or equivalent throughput.

## Reproduce

Build Rust with `cargo build --release --locked --manifest-path tools/load/Cargo.toml`.
Build a clean matching compiler checkout with Maven and set ORES_JAVA to the
matching GraalVM executable. The explicit audit runner accepts that checkout;
normal package SOURCE_REF/provenance checks are not silently overridden.

```sh
scripts/run-paced-load.sh my-core-shared /absolute/core-checkout shared core 30
scripts/run-paced-load.sh my-otel-isolated /absolute/core-checkout isolated both 30
tools/load/target/release/summarize .cache/latency-20261013/my-core-shared
```

Each output directory must be new. Core uses `--core-perf
--core-perf-sample-every=1024`; use `--no-core-perf` to disable. The sampler
alone does not enable recording. Native userland logs remain `oreslang-otel.v1`
JSONL, not an OTLP collector integration.

## Admission phase validation and native execution

Final admission phase revision `703bbe971f26b7188b9a855f0c0f5be9921b0fbe`
passed 1877 Maven tests (zero failures/errors, one skip). A separate ten-second
measurement after warm-up validated the new core boundary against live shared
HTTP traffic: 84,737 successful responses, 55 warmed admission-to-handler
samples, mean 11.702 ms, p95 12.182 ms. Its separate receipts are retained;
it is not pooled into the original eight-run overhead comparison.

AOT, hybrid and polyglot-isolate images built successfully. The actual
native-core-library.ores program returned the expected exact-integer vectors
in AOT, hybrid and strict-isolate execution. AOT and hybrid each exported eight
core phases. The strict-isolate host recorder exported zero guest phases:
flag propagation/export across the physical isolate boundary remains a known
observability gap. Successful guest execution is not evidence that guest
phases were captured there. These smoke checks are not native HTTP throughput.
