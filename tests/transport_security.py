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
    """Require an explicit HTTP client error and close, never a silent drop.

    Pre-admission header faults must also bypass guest middleware (X-Spin).
    A deliberate server-side 4xx is not proven by a closed socket alone.
    """
    data, closed = _exchange(port, request)
    statuses = _statuses(data)
    expected = {400, 501} if name == 'unsupported_transfer_coding' else {400}
    if not closed or len(statuses) != 1 or statuses[0] not in expected:
        raise AssertionError(
            f'{name}: expected one explicit {sorted(expected)} response and EOF; '
            f'statuses={statuses}, closed={closed}, head={data[:256]!r}')
    if name != 'invalid_chunk_size':
        # Invalid body framing can be discovered by the already admitted
        # request actor, but Host/TE/CL/header rejection must happen before
        # that actor or its middleware is ever called.
        header_block = data.partition(b'\r\n\r\n')[0].lower()
        if b'\r\nx-spin:' in header_block:
            raise AssertionError(f'{name}: guest middleware ran for a rejected request')
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
        ('mixed_case_duplicate_host', b'GET /shared HTTP/1.1\r\nHost: localhost\r\nhOsT: attacker.test\r\nConnection: close\r\n\r\n'),
        ('joined_host', b'GET /shared HTTP/1.1\r\nHost: localhost,attacker.test\r\nConnection: close\r\n\r\n'),
        ('blank_host', b'GET /shared HTTP/1.1\r\nHost:   \r\nConnection: close\r\n\r\n'),
        ('missing_host', b'GET /shared HTTP/1.1\r\nConnection: close\r\n\r\n'),
        ('duplicate_equal_cl', prefix + b'Content-Length: 0\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'),
        ('joined_cl', prefix + b'Content-Length: 0,0\r\nConnection: close\r\n\r\n'),
        ('signed_cl', prefix + b'Content-Length: +1\r\nConnection: close\r\n\r\n'),
        ('repeated_te', prefix + b'Transfer-Encoding: chunked\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n0\r\n\r\n'),
        ('host_uri_delimiter', b'GET /shared HTTP/1.1\r\nHost: localhost/other\r\nConnection: close\r\n\r\n'),
        ('oversized_header', b'GET /shared HTTP/1.1\r\nHost: localhost\r\nX-Oversized: ' + b'x'*12000 + b'\r\nConnection: close\r\n\r\n'),
    )
    checks = 0
    for name, wire in probes:
        checks += assert_rejected(port, name, wire)
    # An otherwise valid request must still work after malformed connections.
    data, closed = _exchange(port, sentinel)
    statuses = _statuses(data)
    if not closed or statuses != [200] or b'shared' not in data:
        raise AssertionError(f'listener recovery: expected closed 200 shared, got status={statuses}, closed={closed}: {data[:256]!r}')
    checks += 1
    # Transfer-Encoding: chunked must remain functional after strict denial.
    valid_chunked = (prefix + b'Transfer-Encoding: chunked\r\n'
                     + b'Connection: close\r\n\r\n'
                     + b'3\r\nabc\r\n0\r\n\r\n')
    data, closed = _exchange(port, valid_chunked)
    statuses = _statuses(data)
    if not closed or statuses != [200] or not data.endswith(b'abc'):
        raise AssertionError(f'valid chunked body regressed: statuses={statuses}, closed={closed}, tail={data[-256:]!r}')
    return checks + 1
