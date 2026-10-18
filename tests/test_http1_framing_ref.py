import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from http1_framing_ref import FrameError, HeadBuffer, parse_head


def head(*fields, request=b"GET / HTTP/1.1"):
    return request+b"\r\n"+b"\r\n".join(fields)+b"\r\n\r\n"


class FramingTests(unittest.TestCase):
    def test_basic_request_and_fragmented_delivery(self):
        message=head(b"Host: example.test")
        buffered=HeadBuffer()
        for byte in message[:-1]:
            self.assertIsNone(buffered.feed(bytes([byte])))
        self.assertEqual(buffered.feed(message[-1:])["declared_body_bytes"],0)

    def test_cl_exact_and_bounded(self):
        v=parse_head(head(b"Host: example.test",b"Content-Length: 5"))
        self.assertEqual(v["declared_body_bytes"],5)
        for raw in (b"-1",b"+5",b"5, 5",b"10000000",b"nan",b""):
            with self.subTest(raw=raw), self.assertRaises(FrameError):
                parse_head(head(b"Host: example.test",b"Content-Length: "+raw))

    def test_reject_duplicate_content_length_and_te_cl_smuggling(self):
        for fields in (
            (b"Host: a",b"Content-Length: 3",b"Content-Length: 3"),
            (b"Host: a",b"Content-Length: 3",b"Content-Length: 9"),
            (b"Host: a",b"Transfer-Encoding: chunked",b"Content-Length: 0"),
            (b"Host: a",b"Transfer-Encoding: chunked"),
        ):
            with self.subTest(fields=fields), self.assertRaises(FrameError):
                parse_head(head(*fields))

    def test_host_authority_and_obs_fold_fail_closed(self):
        for fields in (
            (b"Host: a",b"Host: b"),
            (b"X: a",),
            (b"Host: a",b" folded"),
            (b"Host: a",b"Bad Name: x"),
            (b"Host: a",b"X: x\x00y"),
        ):
            with self.subTest(fields=fields), self.assertRaises(FrameError):
                parse_head(head(*fields))

    def test_wrong_line_endings_and_pipelined_surplus_rejected(self):
        with self.assertRaises(FrameError):
            parse_head(b"GET / HTTP/1.1\nHost: a\n\n")
        b=HeadBuffer()
        with self.assertRaises(FrameError):
            b.feed(head(b"Host: a")+head(b"Host: b"))

    def test_header_and_field_limits(self):
        with self.assertRaises(FrameError):
            parse_head(head(*([b"Host: example.test"]+[b"X: x"]*65)))
        with self.assertRaises(FrameError):
            HeadBuffer().feed(b"x"*16385)


if __name__=="__main__":
    unittest.main()
