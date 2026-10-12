#!/usr/bin/env python3
import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('load_matrix',Path(__file__).with_name('load-matrix.py'))
load=importlib.util.module_from_spec(spec);spec.loader.exec_module(load)

class LoadTests(unittest.IsolatedAsyncioTestCase):
    async def serve(self,response):
        self.calls=0
        async def handler(reader,writer):
            self.calls+=1
            await reader.readuntil(b'\r\n\r\n')
            if response is not None:writer.write(response);await writer.drain()
            else:await reader.read()
            writer.close()
            await writer.wait_closed()
        server=await asyncio.start_server(handler,'127.0.0.1',0)
        self.addAsyncCleanup(self.close_server,server)
        return server.sockets[0].getsockname()[1]
    async def close_server(self,server):
        server.close();await server.wait_closed()
    async def test_success_validates_body_mode_and_timing(self):
        port=await self.serve(b'HTTP/1.1 200 OK\r\nX-Actor-Mode: shared\r\nServer-Timing: actor-startup;dur=0.25\r\nContent-Length: 3\r\n\r\nok\n')
        result,samples=await load.burst(port,'shared',4,1)
        self.assertEqual(result['successes'],4)
        self.assertEqual(result['status_counts'],{'200':4})
        self.assertEqual(self.calls,4)
        self.assertEqual(result['actor_startup']['p50_ms'],.25)
    async def test_rejections_are_not_successes_or_retried(self):
        port=await self.serve(b'HTTP/1.1 503 Unavailable\r\nContent-Length: 0\r\n\r\n')
        result,_=await load.burst(port,'shared',5,1)
        self.assertEqual(result['successes'],0)
        self.assertEqual(result['success_latency']['p50_ms'],None)
        self.assertEqual(result['status_counts'],{'503':5})
        self.assertEqual(result['retries'],0)
        self.assertEqual(self.calls,5)
    async def test_wrong_body_is_failure_even_with_200(self):
        port=await self.serve(b'HTTP/1.1 200 OK\r\nX-Actor-Mode: shared\r\n\r\nbad')
        result,_=await load.burst(port,'shared',1,1)
        self.assertEqual(result['successes'],0)
        self.assertEqual(sum(result['errors'].values()),1)
    async def test_timeout_counted_without_retry(self):
        port=await self.serve(None)
        result,_=await load.burst(port,'shared',2,.03)
        self.assertEqual(result['successes'],0)
        self.assertEqual(sum(result['errors'].values()),2)
        self.assertEqual(self.calls,2)
    def test_nearest_rank_percentile(self):
        self.assertEqual(load.percentile([1,2,3,4],.5),2)
        self.assertEqual(load.percentile([1,2,3,4],.95),4)
        self.assertIsNone(load.percentile([],.95))

if __name__=='__main__':unittest.main()
