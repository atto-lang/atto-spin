#!/usr/bin/env python3
"""Hermetic smoke tests for the sustained benchmark protocol."""
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'sustained-client.py'
spec = importlib.util.spec_from_file_location('sustained_client', SCRIPT)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

class ClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.connections = 0
        async def handle(reader, writer):
            self.connections += 1
            try:
                while True:
                    header = await reader.readuntil(b'\r\n\r\n')
                    if not header: break
                    writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\nX-Actor-Mode: shared\r\nConnection: keep-alive\r\n\r\nok\n')
                    await writer.drain()
            except (asyncio.IncompleteReadError,ConnectionResetError,BrokenPipeError):
                pass
            finally:
                writer.close()
                try: await writer.wait_closed()
                except Exception: pass
        self.server = await asyncio.start_server(handle, '127.0.0.1', 0)
        self.port=self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def test_persistent_connections_and_validity(self):
        args=SimpleNamespace(host='127.0.0.1',port=self.port,path='/shared',
                             mode='shared',duration=.25,concurrency=4,timeout=2)
        result=await client.benchmark(args)
        self.assertGreater(result['attempts'],4)
        self.assertEqual(result['successes'],result['attempts'])
        self.assertGreater(result['reused_connections'],0)
        self.assertEqual(result['errors'],{})
        self.assertEqual(result['status'],{'200':result['attempts']})
        self.assertLessEqual(result['connections'],4)

    async def test_invalid_mode_fails_closed(self):
        args=SimpleNamespace(host='127.0.0.1',port=self.port,path='/isolated',
                             mode='isolated',duration=.1,concurrency=2,timeout=2)
        result=await client.benchmark(args)
        self.assertEqual(result['successes'],0)
        self.assertEqual(result['errors'].get('invalid_response'),result['attempts'])
        self.assertEqual(result['success_rate'],0)

if __name__=='__main__':
    unittest.main()
