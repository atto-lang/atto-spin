# Actor-owned HTTP responses and comparable load tests

Every successful load-test response must carry an actor mode, stable worker ID,
and reuse marker. The client rejects a missing/wrong marker or body; it never
retries. A pooled actor claims the unique exchange transfer token and responds
while owning that exchange. Each actor still executes one callback at a time,
including its await continuation; separate actors can execute concurrently.

Framework 404, 405, 414, automatic OPTIONS and caught-failure replies now use a
bounded shared response-actor pool. Middleware that calls a buffered core HTTP
`respond`/`respond_bytes` from the supervisor transfers its exchange into a
one-shot shared response actor. That call revokes the supervisor handle; capture
`request.completion` before responding if it is needed. Supervisor streaming
`start` is rejected: streaming must take place inside the owning actor.

Transport-level parse errors, admission rejection and deadline/crash cleanup
remain runtime safety paths. An invalid or unadmitted connection does not get an
application actor; overload must not allocate an unbounded number of actors.
The request/response ownership guarantee applies to admitted application replies,
not to every byte or rejection the HTTP transport can emit.

## Fixed-load comparison

The requested workload is **100 connected clients, one request in flight per
client**, sustaining at least 10,000 requests/sec. It is not 10,000 simultaneous
requests. A 4 ms mean at 100 continuously active clients implies roughly 25,000
completions/sec. Run modes separately and retain the existing 180-second window:

```sh
python3 scripts/sustained-load.py --concurrency 100 --seconds 180 \
  --actor-mode shared --sample-every 1000 --core-perf --output /tmp/spin-shared
python3 scripts/sustained-load.py --concurrency 100 --seconds 180 \
  --actor-mode isolated --sample-every 1000 --core-perf --output /tmp/spin-isolated
```

Both modes use 32 workers and the same request/response bodies, persistent HTTP
connections, ten-second warm-up and sampling policy. `mixed` remains the default
and uses half the clients per actor kind. The current JVM isolated actor mode
is an ownership/runtime boundary, not proof of separate OS address spaces.

