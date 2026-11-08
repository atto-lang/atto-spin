#!/usr/bin/env python3
"""Source-only assertions for Spin's raw-wire client, NOT native guest proof."""
import socket
import threading
import unittest
from unittest.mock import patch
import transport_security as ts


class WireHarnessTests(unittest.TestCase):
    def case(self, status=b'HTTP/1.1 400 Bad Request', name='duplicate_host',
             closed=True, headers=b'', tail=b''):
        reply = status + b'\r\n' + headers + b'Content-Length: 0\r\n\r\n' + tail
        with patch.object(ts, '_exchange', return_value=(reply, closed)):
            return ts.assert_rejected(1, name, b'bad request')

    def test_status_parse_ignores_body_digits(self):
        self.assertEqual(ts._statuses(b'HTTP/1.1 400 Bad Request\r\nContent-Length: 6\r\n\r\n200!!!'), [400])
        self.assertEqual(ts._statuses(b'garbage HTTP/1.1 200 OK'), [])
        self.assertEqual(ts._statuses(b'HTTP/1.1 400 Bad\r\n\r\nHTTP/1.1 200 OK\r\n'), [400, 200])

    def test_explicit_400_then_close_is_required(self):
        self.assertEqual(self.case(), 1)

    def test_silent_close_not_a_success(self):
        with patch.object(ts, '_exchange', return_value=(b'', True)):
            with self.assertRaises(AssertionError):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_unsupported_transfer_coding_allows_exact_501(self):
        self.assertEqual(self.case(b'HTTP/1.1 501 Not Implemented',
                                   name='unsupported_transfer_coding'), 1)
        with self.assertRaises(AssertionError):
            self.case(b'HTTP/1.1 501 Not Implemented', name='te_and_cl_conflict')

    def test_open_malformed_success_or_server_error_cannot_pass(self):
        for status, closed in (
            (b'', False),
            (b'HTTP/1.1 400 Bad Request', False),
            (b'HTTP/1.1 200 OK', True),
            (b'HTTP/1.1 404 Not Found', True),
            (b'HTTP/1.1 500 Internal Server Error', True),
            (b'garbage', True)):
            with self.subTest(status=status, closed=closed):
                with self.assertRaises(AssertionError):
                    self.case(status, closed=closed)

    def test_second_pipelined_status_fails(self):
        with self.assertRaises(AssertionError):
            self.case(tail=b'\r\nHTTP/1.1 200 OK\r\n\r\n')

    def test_rejected_header_must_not_enter_guest_middleware(self):
        with self.assertRaises(AssertionError):
            self.case(headers=b'X-Spin: test\r\n')

    def test_guest_middleware_may_run_before_malformed_body_fails(self):
        self.assertEqual(self.case(name='invalid_chunk_size',
                                   headers=b'X-Spin: test\r\n'), 1)

    def test_bounded_response_body_is_allowed(self):
        body = b'error from JDK parser'
        reply = (b'HTTP/1.1 400 Bad Request\r\n'
                 + b'Content-Type: text/plain\r\n'
                 + b'Content-Length: ' + str(len(body)).encode() + b'\r\n\r\n'
                 + body)
        with patch.object(ts, '_exchange', return_value=(reply, True)):
            self.assertEqual(ts.assert_rejected(1, 'duplicate_host', b'bad request'), 1)

    def test_rejects_status_line_not_at_offset_zero(self):
        with self.assertRaises(AssertionError):
            self.case(status=b'junk\r\nHTTP/1.1 400 Bad Request')

    def test_rejects_missing_final_header_terminator(self):
        with patch.object(ts, '_exchange', return_value=(b'HTTP/1.1 400 Bad Request\r\n', True)):
            with self.assertRaises(AssertionError):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_rejects_truncated_response_body(self):
        with patch.object(ts, '_exchange', return_value=(
                b'HTTP/1.1 400 Bad Request\r\nContent-Length: 99\r\n\r\nshort', True)):
            with self.assertRaises(AssertionError):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_rejects_surplus_bytes_after_declared_body(self):
        with self.assertRaises(AssertionError):
            self.case(tail=b'extra bytes after Content-Length 0')

    def test_rejects_duplicate_response_content_lengths(self):
        with self.assertRaises(AssertionError):
            self.case(headers=b'Content-Length: 0\r\n')

    def test_rejects_response_transfer_encoding_and_content_length(self):
        with self.assertRaises(AssertionError):
            self.case(headers=b'Transfer-Encoding: chunked\r\n')

    def test_rejects_malformed_response_header(self):
        with self.assertRaises(AssertionError):
            self.case(headers=b'Not-A-Header\r\n')

    def test_rejects_folded_response_header(self):
        with self.assertRaises(AssertionError):
            self.case(headers=b'X-Info: okay\r\n continuation\r\n')

    def test_rejects_invalid_response_header_name(self):
        with self.assertRaises(AssertionError):
            self.case(headers=b'X Test: bad\r\n')

    def test_rejects_nonnumeric_response_content_length(self):
        with patch.object(ts, '_exchange', return_value=(
                b'HTTP/1.1 400 Bad Request\r\nContent-Length: +1\r\n\r\nx', True)):
            with self.assertRaises(AssertionError):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_exact_length_error_body_is_allowed(self):
        with patch.object(ts, '_exchange', return_value=(
                b'HTTP/1.1 400 Bad Request\r\nContent-Length: 5\r\n\r\nerror', True)):
            self.assertEqual(ts.assert_rejected(1, 'duplicate_host', b'bad'), 1)

    def test_false_success_from_embedded_status_is_rejected(self):
        with patch.object(ts, '_exchange', return_value=(
                b'error-body\r\nHTTP/1.1 400 Bad Request\r\n\r\n', True)):
            with self.assertRaises(AssertionError):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_jdk_21_unsupported_transfer_501_with_body(self):
        body = b'<h1>501 Not Implemented</h1>Unsupported Transfer-Encoding value'
        self.assertEqual(len(body), 63)
        reply = (b'HTTP/1.1 501 Not Implemented\r\n'
                 b'Content-Length: 63\r\nContent-Type: text/html\r\n'
                 b'Connection: close\r\n\r\n' + body)
        with patch.object(ts, '_exchange', return_value=(reply, True)):
            self.assertEqual(ts.assert_rejected(1, 'unsupported_transfer_coding', b'bad'), 1)
            with self.assertRaises(AssertionError):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_jdk_21_conflicting_cl_400_with_body(self):
        body = b'<h1>400 Bad Request</h1>Conflicting or malformed headers detected'
        self.assertEqual(len(body), 65)
        reply = (b'HTTP/1.1 400 Bad Request\r\n'
                 b'Content-Length: 65\r\nContent-Type: text/html\r\n'
                 b'Connection: close\r\n\r\n' + body)
        with patch.object(ts, '_exchange', return_value=(reply, True)):
            self.assertEqual(ts.assert_rejected(1, 'te_and_cl_conflict', b'bad'), 1)

    def test_jdk_21_parser_accepts_missing_host_but_spin_must_deny_it(self):
        # JDK default handler responds 200 to missing Host. Spin's own
        # admission guard must convert that to HTTP 400 before guest dispatch.
        reply = (b'HTTP/1.1 200 OK\r\nContent-length: 0\r\n\r\n')
        with patch.object(ts, '_exchange', return_value=(reply, True)):
            with self.assertRaises(AssertionError):
                ts.assert_rejected(1, 'missing_host', b'bad')

    def test_excessively_long_response_length_is_bounded_before_int_parse(self):
        reply = (b'HTTP/1.1 400 Bad Request\r\nContent-Length: '
                 + b'9' * 5000 + b'\r\n\r\n')
        with patch.object(ts, '_exchange', return_value=(reply, True)):
            with self.assertRaisesRegex(AssertionError, 'capture bound'):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_content_length_body_with_http_status_looking_text_is_valid(self):
        body = b'client text\r\nHTTP/1.1 200 OK\r\nnot another response'
        raw = (b'HTTP/1.1 400 Bad Request\r\nContent-Length: '
               + str(len(body)).encode() + b'\r\n\r\n' + body)
        with patch.object(ts, '_exchange', return_value=(raw, True)):
            self.assertEqual(ts.assert_rejected(1, 'duplicate_host', b'bad'), 1)

    def test_close_delimited_fake_second_response_is_rejected(self):
        raw = (b'HTTP/1.1 400 Bad Request\r\n\r\n'
               b'hello\r\nHTTP/1.1 200 OK\r\n\r\n')
        with patch.object(ts, '_exchange', return_value=(raw, True)):
            with self.assertRaises(AssertionError):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_valid_chunked_response_is_decoded(self):
        raw = (b'HTTP/1.1 400 Bad Request\r\nTransfer-Encoding: chunked\r\n\r\n'
               b'5\r\nerror\r\n0\r\n\r\n')
        with patch.object(ts, '_exchange', return_value=(raw, True)):
            self.assertEqual(ts.assert_rejected(1, 'duplicate_host', b'bad'), 1)
            self.assertEqual(ts._response(raw)[2], b'error')

    def test_chunked_response_case_insensitive_coding(self):
        raw = (b'HTTP/1.1 400 Bad Request\r\nTransfer-Encoding: Chunked\r\n\r\n'
               b'0\r\n\r\n')
        with patch.object(ts, '_exchange', return_value=(raw, True)):
            self.assertEqual(ts.assert_rejected(1, 'duplicate_host', b'bad'), 1)

    def test_chunked_response_malformed_size_fails(self):
        raw = (b'HTTP/1.1 400 Bad Request\r\nTransfer-Encoding: chunked\r\n\r\n'
               b'Z\r\nabc\r\n0\r\n\r\n')
        with patch.object(ts, '_exchange', return_value=(raw, True)):
            with self.assertRaisesRegex(AssertionError, 'chunk size'):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_chunked_response_truncated_data_fails(self):
        raw = (b'HTTP/1.1 400 Bad Request\r\nTransfer-Encoding: chunked\r\n\r\n'
               b'5\r\nabc\r\n0\r\n\r\n')
        with patch.object(ts, '_exchange', return_value=(raw, True)):
            with self.assertRaisesRegex(AssertionError, 'chunk'):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_chunked_response_pipelined_reply_fails(self):
        raw = (b'HTTP/1.1 400 Bad Request\r\nTransfer-Encoding: chunked\r\n\r\n'
               b'0\r\n\r\nHTTP/1.1 200 OK\r\n\r\n')
        with patch.object(ts, '_exchange', return_value=(raw, True)):
            with self.assertRaisesRegex(AssertionError, 'trailing'):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_chunked_response_trailers_fail_closed(self):
        raw = (b'HTTP/1.1 400 Bad Request\r\nTransfer-Encoding: chunked\r\n\r\n'
               b'0\r\nX-Extra: injected\r\n\r\n')
        with patch.object(ts, '_exchange', return_value=(raw, True)):
            with self.assertRaisesRegex(AssertionError, 'trailing'):
                ts.assert_rejected(1, 'duplicate_host', b'bad')

    def test_response_header_value_control_byte_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'control bytes'):
            self.case(headers=b'X-Attacker: good\x00bad\r\n')

    def test_response_header_value_del_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'control bytes'):
            self.case(headers=b'X-Attacker: good\x7fbad\r\n')

    def test_socket_client_reads_full_reply(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        def serve():
            try:
                client, _ = listener.accept()
                with client:
                    client.recv(1024)
                    client.sendall(b'HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n')
            finally:
                listener.close()
        worker = threading.Thread(target=serve)
        worker.start()
        try:
            self.assertEqual(ts.assert_rejected(port, 'socket', b'bad'), 1)
        finally:
            worker.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
