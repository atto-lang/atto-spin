#!/usr/bin/env python3
"""Raw-wire HTTP/1.1 rejection probes against the actual Spin listening socket.

Never instantiate a model HTTP server as a substitute for this native test.
The function is called from tests/integration.py after the real server boots.
"""
import re
import socket
import time

_TIMEOUT = 3.25
_STATUS = re.compile(rb'(?:\A|\r\n)HTTP/1\.[01] ([0-9]{3})[ \r]')


def _exchange(port, payload, timeout=_TIMEOUT):
    data = bytearray()
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(payload)
        # Every negative probe has all bytes needed to decide rejection.
        # A deadline is a failure, not an accepted no-response result.
        deadline = time.monotonic() + timeout
        closed = False
        while time.monotonic() < deadline and len(data) < 65536:
            sock.settimeout(max(0.01, deadline - time.monotonic()))
            try:
                chunk = sock.recv(8192)
            except socket.timeout:
                break
            except ConnectionResetError:
                closed = True
                break
            if not chunk:
                closed = True
                break
            data.extend(chunk)
        return bytes(data), closed


def _statuses(data):
    return [int(m.group(1)) for m in _STATUS.finditer(data)]


def assert_rejected(port, name, request):
    """Reject the bad frame and never serve an embedded pipelined request.

    An explicit 4xx followed by close, or an immediate silent close, is valid.
    A hanging connection or 2xx/3xx/5xx response fails the security gate.
    """
    data, closed = _exchange(port, request)
    statuses = _statuses(data)
    if not closed or (statuses and (len(statuses) != 1 or statuses[0] < 400 or statuses[0] > 499)):
        raise AssertionError(f'{name}: expected closed reject connection; status={statuses}, closed={closed}, head={data[:256]!r}')
    if not statuses and data:
        raise AssertionError(f'{name}: unparseable bytes before close: {data[:256]!r}')
    return 1


def run(port):
    """Run exact-byte boundary probes. Return the number of native assertions."""
    sentinel = b'GET /shared HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'
    prefix = b'POST /echo HTTP/1.1\r\nHost: localhost\r\n'
    probes = (
        ('te_and_cl_conflict', prefix + b'Transfer-Encoding: chunked\r\nContent-Length: 4\r\n\r\n0\r\n\r\n' + sentinel),
        ('conflicting_duplicate_cl', prefix + b'Content-Length: 3\r\nContent-Length: 4\r\n\r\nxyz' + sentinel),
        ('invalid_negative_cl', prefix + b'Content-Length: -1\r\n\r\n' + sentinel),
        ('unsupported_transfer_coding', prefix + b'Transfer-Encoding: gzip\r\n\r\n' + sentinel),
        ('invalid_chunk_size', prefix + b'Transfer-Encoding: chunked\r\n\r\nZ\r\n' + sentinel),
        ('duplicate_host', b'GET /shared HTTP/1.1\r\nHost: localhost\r\nHost: attacker.test\r\nConnection: close\r\n\r\n'),
        ('oversized_header', b'GET /shared HTTP/1.1\r\nHost: localhost\r\nX-Oversized: ' + b'x'*12000 + b'\r\nConnection: close\r\n\r\n'),
    )
    checks = 0
    for name, wire in probes:
        checks += assert_rejected(port, name, wire)
    # An otherwise valid request must still work after malformed connections.
    data, _ = _exchange(port, sentinel)
    statuses = _statuses(data)
    if statuses != [200] or b'shared' not in data:
        raise AssertionError(f'listener recovery: expected 200 shared, got status={statuses}: {data[:256]!r}')
    return checks + 1
