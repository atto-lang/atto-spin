# Spin HTTP framing and backend promotion gates

The `tests/transport_security.py` probe suite runs **against the actual
listener started by `tests/integration.py`**. It sends exact HTTP/1.1 bytes,
not `http.client`-normalized headers. The 7 rejection cases cover:

- overlapping Transfer-Encoding and Content-Length followed by a pipelined GET;
- conflicting duplicate Content-Length values followed by a pipelined GET;
- negative Content-Length and unsupported transfer coding, each with a sentinel GET;
- invalid chunk-size encoding with a sentinel GET;
- duplicate Host headers; and
- a 12-KiB header exceeding the server's declared ingress bound.

A malformed request must receive at most one 4xx response and close, or close
immediately. A 2xx response (including one for a smuggled second request),
an open socket, or an unparseable partial response fails. A final valid GET
confirms the listener remains healthy after the rejected traffic.

Run `python3 -B -m unittest discover -s tests -p 'test_transport_security.py' -v`
for **harness-only** tests. These tests use a synthetic loopback server to
exercise the *test client*; they do not validate any Oreslang compiler or HTTP
transport. Only an executed `scripts/ci-native.sh` run at a verified Spin
commit + pinned compiler + router can establish a native pass.

## Backend inventory

`BACKENDS.json` now enumerates exactly five requested backends:

| Backend | Declared Spin HTTP execution | Verification gate |
| --- | --- | --- |
| Java | supported by existing pinned native suite | Fresh JDK 25 compiler and guest HTTP integration on the exact source/tree SHA |
| LLVM | unsupported | Positive compiler control and exact diagnostic negative probes; not execution |
| Wasm | unverified | Implement actor/HTTP transport then compiler-backed listener tests |
| Cranelift | unverified | Implement actor/HTTP transport then compiler-backed listener tests |
| .NET | unverified | Implement actor/HTTP transport then compiler-backed listener tests |

`scripts/check-backend.py` rejects `wasm`, `cranelift` and `net` requests
with a nonzero exit until an explicitly reviewed native-execution gate
replaces each `unverified` entry. Their source repositories exist; repository
existence or compiler smoke tests do not establish framework parity.
The companion negative-contract suite forbids spoofing these entries to
`supported` or adding fake evidence fields.

No backend's source, compiler, transport, or allocator was changed by this
PR. Java-native framing probes are **new acceptance requirements**, not
passing runtime evidence; cross-backend parity remains unestablished.
