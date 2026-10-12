#!/usr/bin/env python3
import asyncio
import importlib.machinery
from pathlib import Path
import unittest

client=importlib.machinery.SourceFileLoader("spin_sustained",str(Path(__file__).with_name("sustained-client.py"))).load_module()

class SustainedTests(unittest.IsolatedAsyncioTestCase):
    async def test_keep_alive_validates_many_responses_without_reconnecting(self):
        sockets=0
        calls=0
        async def serve(reader,writer):
            nonlocal sockets,calls
            sockets+=1
            try:
                while True:
                    try:await reader.readuntil(b"\r\n\r\n")
                    except asyncio.IncompleteReadError:break
                    calls+=1
                    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nX-Actor-Mode: shared\r\n\r\nok\n")
                    await writer.drain()
            finally:
                writer.close()
        server=await asyncio.start_server(serve,"127.0.0.1",0)
        try:
            result=await client.sustained("127.0.0.1",server.sockets[0].getsockname()[1],"/shared","shared",3,1)
            self.assertEqual(result["failures"],{})
            self.assertEqual(result["success_responses"],calls)
            self.assertGreater(calls,3)
            self.assertEqual(sockets,3)
            self.assertEqual(result["retries"],0)
        finally:
            server.close();await server.wait_closed()

if __name__=="__main__":unittest.main()
