"""Bounded HTTP/1.1 request-head admission oracle for Oreslang transport.

Strictly rejects ambiguous framing. This is not the guest .ores HTTP server,
chunked-body parser or a substitute for end-to-end socket execution.
"""
import re

TOKEN = re.compile(rb"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
REQUEST_LINE = re.compile(rb"^([A-Z]+) ([^\x00-\x20\x7f]+) (HTTP/1\.[01])$")
MAX_HEADERS = 64
MAX_HEAD_BYTES = 16384
MAX_BODY_BYTES = 1 << 20


class FrameError(ValueError):
    pass


def parse_head(head):
    if type(head) is not bytes or len(head) > MAX_HEAD_BYTES:
        raise FrameError("invalid/oversized request header")
    if not head.endswith(b"\r\n\r\n") or b"\n" in head.replace(b"\r\n",b""):
        raise FrameError("incomplete or non-CRLF request header")
    lines = head[:-4].split(b"\r\n")
    if not lines or len(lines[0]) > 8192:
        raise FrameError("missing or oversized request line")
    first = REQUEST_LINE.fullmatch(lines[0])
    if not first:
        raise FrameError("malformed request line")
    if len(lines) - 1 > MAX_HEADERS:
        raise FrameError("too many header fields")
    headers = {}
    for line in lines[1:]:
        if not line or line[:1] in (b" ",b"\t") or b":" not in line:
            raise FrameError("invalid field/obs-fold continuation")
        name, value = line.split(b":",1)
        if not TOKEN.fullmatch(name) or any(x < 32 and x != 9 or x == 127 for x in value):
            raise FrameError("invalid header token or control character")
        normalized = name.lower()
        if normalized in headers and normalized in (b"host", b"content-length", b"transfer-encoding"):
            raise FrameError("duplicate framing or host authority")
        headers.setdefault(normalized,[]).append(value.strip(b" \t"))
    if first.group(3) == b"HTTP/1.1" and (
        b"host" not in headers or len(headers[b"host"]) != 1
        or not headers[b"host"][0]
    ):
        raise FrameError("HTTP/1.1 requires exactly one Host")
    if b"transfer-encoding" in headers:
        # Chunked decoding is not implemented by this oracle. Never fall
        # through to Content-Length or guess a message boundary.
        raise FrameError("transfer-encoding requires audited chunked parser")
    length = 0
    if b"content-length" in headers:
        raw = headers[b"content-length"][0]
        if not raw or not all(48 <= x <= 57 for x in raw) or len(raw) > 10:
            raise FrameError("invalid Content-Length")
        length = int(raw)
        if length > MAX_BODY_BYTES:
            raise FrameError("request body exceeds bounded admission")
    return {"method":first.group(1).decode("ascii"),
            "target":first.group(2).decode("ascii"),
            "version":first.group(3).decode("ascii"),
            "declared_body_bytes":length}


class HeadBuffer:
    def __init__(self):
        self._buffer = bytearray()

    def feed(self, chunk):
        if type(chunk) is not bytes:
            raise FrameError("request bytes required")
        self._buffer.extend(chunk)
        if len(self._buffer) > MAX_HEAD_BYTES:
            raise FrameError("fragmented request head too large")
        marker = self._buffer.find(b"\r\n\r\n")
        if marker == -1:
            return None
        if marker + 4 != len(self._buffer):
            # This narrow oracle deliberately does not consume pipelined data;
            # a production parser must retain exact surplus bytes separately.
            raise FrameError("body/pipelined bytes need separate framed transport")
        return parse_head(bytes(self._buffer))
