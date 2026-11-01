#!/usr/bin/env python3
"""Unit tests for the raw-wire client (not evidence about native Spin)."""
import socket
import threading
import unittest
from unittest.mock import patch
import transport_security as ts


class WireHarnessTests(unittest.TestCase):
    def test_status_parse_ignores_body_digits(self):
        self.assertEqual(ts._statuses(b'HTTP/1.1 400 Bad Request\r\nContent-Length: 6\r\n\r\n200!!!'), [400])
        self.assertEqual(ts._statuses(b'garbage HTTP/1.1 200 OK'), [])
        self.assertEqual(ts._statuses(b'HTTP/1.1 400 Bad\r\n\r\nHTTP/1.1 200 OK\r\n'), [400, 200])

    def test_closed_reject_is_accepted(self):
        with patch.object(ts, '_exchange', return_value=(b'HTTP/1.1 400 Bad Request\r\n\r\n', True)):
            self.assertEqual(ts.assert_rejected(1, 'case', b'wire'), 1)
        with patch.object(ts, '_exchange', return_value=(b'', True)):
            self.assertEqual(ts.assert_rejected(1, 'case', b'wire'), 1)

    def test_unsupported_transfer_coding_allows_exact_501(self):
        with patch.object(ts, '_exchange', return_value=(b'HTTP/1.1 501 Not Implemented\\r\\n\\r\\n', True)):
            self.assertEqual(ts.assert_rejected(1, 'unsupported_transfer_coding', b'wire'), 1)
            with self.assertRaises(AssertionError):
                ts.assert_rejected(1, 'te_and_cl_conflict', b'wire')

    def test_open_or_malformed_or_success_rejected(self):
        for response, closed in ((b'', False), (b'HTTP/1.1 400 Bad Request\r\n', False),
                                 (b'HTTP/1.1 200 OK\r\n', True),
                                 (b'HTTP/1.1 500 Internal Server Error\r\n', True),
                                 (b'HTTP/1.1 400 Bad\r\n\r\nHTTP/1.1 200 OK\r\n', True),
                                 (b'garbage', True)):
            with self.subTest(response=response, closed=closed):
                with patch.object(ts, '_exchange', return_value=(response, closed)):
                    with self.assertRaises(AssertionError):
                        ts.assert_rejected(1, 'case', b'wire')

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
