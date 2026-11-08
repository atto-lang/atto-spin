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
        # A malformed request may advertise a body larger than the bytes sent.
        # EOF is part of the probe: otherwise the JDK may retain the socket
        # while trying to drain the unread input after sending a 400.
        try:
            sock.shutdown(socket.SHUT_WR)
        except OSError:
            # The HTTP parser may already have closed/rejected the peer.
            # The response and closure checks below still fail closed.
            pass
        # Every negative probe has all bytes needed to decide rejection.
        # A deadline is a failure, not an accepted no-response result.
        deadline = time.monotonic() + timeout
        closed = False
        while time.monotonic() < deadline and len(data) < 65536:
            sock.settimeout(max(0.01, deadline - time.monotonic()))
            try:
                chunk = sock.recv(min(8192, 65536 - len(data)))
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


def _response(data):
    """Parse a complete closed HTTP/1.x response, not text resembling one.

    This is an assertion helper, not a production HTTP client. Fail closed on
    ambiguous response framing, incomplete headers, duplicated lengths and
    trailers/pipelined bytes hidden after a declared body length.
    """
    head, separator, body = data.partition(b'\r\n\r\n')
    if not separator:
        raise AssertionError(f'HTTP response missing complete header terminator: {data[:128]!r}')
    lines = head.split(b'\r\n')
    first = re.fullmatch(rb'HTTP/1\.[01] ([0-9]{3})(?: [\x20-\x7e]*)?', lines[0])
    if first is None:
        raise AssertionError(f'HTTP response status must be first line: {lines[0][:128]!r}')
    headers = {}
    for line in lines[1:]:
        if b':' not in line or line.startswith((b' ', b'\t')):
            raise AssertionError(f'malformed response header: {line[:128]!r}')
        name, value = line.split(b':', 1)
        if (not name or any(c <= 32 or c >= 127 for c in name)
                or any(c in b'()<>@,;:\\"/[]?={}\t' for c in name)):
            raise AssertionError(f'invalid response header name: {name[:128]!r}')
        if any((c < 32 and c != 9) or c == 127 for c in value):
            raise AssertionError('control bytes in HTTP response header value')
        name = name.lower()
        headers.setdefault(name, []).append(value.strip())
    lengths = headers.get(b'content-length', [])
    transfers = headers.get(b'transfer-encoding', [])
    if len(lengths) > 1 or (lengths and transfers):
        raise AssertionError('ambiguous response body framing')
    if lengths:
        if not re.fullmatch(rb'[0-9]+', lengths[0]):
            raise AssertionError('malformed response content-length')
        # _exchange() caps the response at 64 KiB. Reject huge decimal
        # strings before int() to avoid a giant-number parse or ValueError.
        if len(lengths[0]) > 5 or int(lengths[0]) > 65536:
            raise AssertionError('declared response length exceeds capture bound')
        if len(body) != int(lengths[0]):
            raise AssertionError('truncated or surplus HTTP response bytes')
    elif transfers:
        if [value.lower() for value in transfers] != [b'chunked']:
            raise AssertionError('unsupported response transfer framing')
        # Parse chunk boundaries, rather than accepting an arbitrary suffix
        # after a nominal 400. Limit each hex size to 8 digits and the total
        # decoded bytes to the same 64 KiB socket capture budget.
        payload = bytearray()
        position = 0
        while True:
            end = body.find(b'\r\n', position)
            if end < 0 or end - position > 8:
                raise AssertionError('missing or oversized response chunk-size line')
            size_text = body[position:end]
            if not re.fullmatch(rb'[0-9A-Fa-f]{1,8}', size_text):
                raise AssertionError('malformed response chunk size')
            size = int(size_text, 16)
            position = end + 2
            if size == 0:
                # Trailers and second/pipelined responses are not part of the
                # Spin contract. Do not silently accept uninspected bytes.
                if body[position:] != b'\r\n':
                    raise AssertionError('trailing bytes after final HTTP chunk')
                break
            if (size > 65536 - len(payload)
                    or body[position + size:position + size + 2] != b'\r\n'):
                raise AssertionError('truncated or oversized HTTP response chunk')
            payload.extend(body[position:position + size])
            position += size + 2
        body = bytes(payload)
    elif re.search(rb'(?:\A|\r\n)HTTP/1\.[01] [0-9]{3}[ \r]', body):
        # For close-delimited responses a second status-looking line is
        # ambiguous. Fail closed rather than claim only one reply was sent.
        raise AssertionError('unframed extra HTTP response detected')
    return int(first.group(1)), headers, body


def assert_rejected(port, name, request):
    """Require a complete explicit error and EOF, not a silent socket drop."""
    data, closed = _exchange(port, request)
    if not closed:
        raise AssertionError(f'{name}: response did not close; prefix={data[:128]!r}')
    status, headers, _ = _response(data)
    expected = {400, 501} if name in ('unsupported_transfer_coding', 'repeated_te') else {400}
    if status not in expected:
        raise AssertionError(
            f'{name}: expected one explicit {sorted(expected)} response; '
            f'actual={status}, prefix={data[:256]!r}')
    if name != 'invalid_chunk_size' and b'x-spin' in headers:
        # Malformed chunk framing may be discovered only after the request
        # entered an actor, unlike header denial before guest dispatch.
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
        ('host_nonnumeric_port', b'GET /shared HTTP/1.1\r\nHost: example.test:abc\r\nConnection: close\r\n\r\n'),
        ('host_empty_authority', b'GET /shared HTTP/1.1\r\nHost: :8080\r\nConnection: close\r\n\r\n'),
        ('host_out_of_range_port', b'GET /shared HTTP/1.1\r\nHost: localhost:65536\r\nConnection: close\r\n\r\n'),
        ('host_invalid_ipv6', b'GET /shared HTTP/1.1\r\nHost: [gggg]\r\nConnection: close\r\n\r\n'),
        ('host_empty_port', b'GET /shared HTTP/1.1\r\nHost: localhost:\r\nConnection: close\r\n\r\n'),
        ('host_unbracketed_ipv6', b'GET /shared HTTP/1.1\r\nHost: ::1\r\nConnection: close\r\n\r\n'),
        ('host_percent_encoded_space', b'GET /shared HTTP/1.1\r\nHost: example.test%20attacker\r\nConnection: close\r\n\r\n'),
        ('host_uri_delimiter', b'GET /shared HTTP/1.1\r\nHost: localhost/other\r\nConnection: close\r\n\r\n'),
        ('oversized_header', b'GET /shared HTTP/1.1\r\nHost: localhost\r\nX-Oversized: ' + b'x'*12000 + b'\r\nConnection: close\r\n\r\n'),
    )
    checks = 0
    for name, wire in probes:
        checks += assert_rejected(port, name, wire)
    # An otherwise valid request must still work after malformed connections.
    data, closed = _exchange(port, sentinel)
    status, headers, body = _response(data)
    if not closed or status != 200 or body != b'shared':
        raise AssertionError(f'listener recovery: expected complete closed 200 shared; '
                             f'status={status}, closed={closed}, body={body[:128]!r}')
    checks += 1
    # Transfer-Encoding: chunked *request* must remain functional. The
    # response is a bounded buffered 200, not a chunked response.
    valid_chunked = (prefix + b'Transfer-Encoding: chunked\r\n'
                     + b'Connection: close\r\n\r\n'
                     + b'3\r\nabc\r\n0\r\n\r\n')
    data, closed = _exchange(port, valid_chunked)
    status, headers, body = _response(data)
    if not closed or status != 200 or body != b'abc':
        raise AssertionError(f'valid chunked request regressed: '
                             f'status={status}, closed={closed}, body={body[:128]!r}')
    return checks + 1
