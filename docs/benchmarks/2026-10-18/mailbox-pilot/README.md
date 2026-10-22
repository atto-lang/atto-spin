# Independent mailbox admission: pilot

A 20-second measurement after 10 seconds of warmup completed 789,874 responses
within the measured window: 39,493.7 requests/sec, no failures or retries.
Client request/response mean was 1.338 ms (p95 1.858 ms). The server accepted and
completed all 1,214,535 exchanges including warmup and shutdown, with zero
admission rejections and a peak of 100 admitted exchanges.

This is a **pilot, not the required 180-second validation**. It uses 100 persistent
closed-loop clients, one application and immutable route table, four supervisor
dispatch lanes/control carriers, and 128 reusable shared actors. Each actor's
source execution remains exclusive; thread-policy drafts enabling multiple
physical actor turns are not integrated here. This does not test process-isolated
actors or the LLVM backend.

745 randomly sampled measured requests have complete correlated Oreslang-OTel
metrics, retained in `metrics.jsonl.gz`. Mean HTTP pending queue wait was
0.135019 ms (p95 0.309958 ms); accept-ready to supervisor callback was
0.008183 ms; mailbox transfer to claim was 0.026119 ms. See `phases.json` for
exact results, and `metadata.json` for source commits, fixture/driver hashes and
machine configuration. Metadata intentionally records the dirty Spin fixture
used in this exploratory run; do not reinterpret it as clean-head CI evidence.

The concurrency-one-per-client driver reports latency inside its HTTP exchange
coroutine. Client task scheduling and statistics outside that coroutine are not
included in that number; throughput includes their cost. The client event-loop
lag p99 was 2.199 ms, so the client may limit peak throughput.

## What changed

A live thread dump showed control threads blocked in actor sends behind the
runtime lifecycle lock, with the active sender waiting on the fair global channel
select coordinator. The actor inbox and continuation inbox now use runtime-private
buffered channels with per-mailbox synchronization. These channels cannot be
exposed as guest multi-channel-select cases. Ordinary guest channels retain the
existing atomic select coordinator, quotas, rendezvous and cancellation semantics.

Additional changes replace JDK HTTP stream I/O with a Netty NIO transport,
correct internal Future unwrapping, avoid redundant guard scans when runtime
resource accounting proves no guards/pending acquisitions exist, and remove
shared monitors from immutable interpreter-analysis cache hits.

Actors now await response completion in the profiled fixtures, so `response.await`
measures the continuation after transport completion instead of registration time.
The request/response path has no socket stream I/O. Existing filesystem/socket
legacy APIs elsewhere in the runtime have not all been migrated; this report does
not claim all standard-library I/O is non-blocking.

## Reproduce

Build the pinned Java runtime, including its refreshed dependency classpath:

```sh
cd "$ORESLANG_SOURCE_DIR"
mvn -q -DskipTests package dependency:build-classpath -Dmdep.outputFile=target/classpath.txt
```

From the Spin checkout, with `ORESLANG_SOURCE_DIR` pointing to that clean pinned
runtime and `ORES_JAVA` to Java 25:

```sh
JAVA_TOOL_OPTIONS=-Dores.runtime.control.parallelism=4 \
  python3 scripts/sustained-load.py --concurrency 100 --seconds 180 \
  --actor-mode shared --pool-size 128 --dispatch-lanes 4 \
  --sample-every 1000 --output /tmp/spin-shared-180s
python3 scripts/summarize-profile.py /tmp/spin-shared-180s
```

Repeat with `--actor-mode isolated` and a separate output directory. The latter
means private actors in this JVM runtime, not separate OS processes/heaps.
