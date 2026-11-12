#!/usr/bin/env python3
import asyncio
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('sustained',Path(__file__).with_name('sustained-load.py'))
load=importlib.util.module_from_spec(spec);spec.loader.exec_module(load)

class SustainedTests(unittest.IsolatedAsyncioTestCase):
    async def start(self,bad=False,fresh=False):
        self.connections=0;self.requests=0;self.sampled=0
        async def handle(reader,writer):
            self.connections+=1
            try:
                while True:
                    raw=await reader.readuntil(b'\r\n\r\n');self.requests+=1
                    self.sampled+=b'X-Profile: yes\r\n' in raw
                    mode=raw.split(b' ')[1].strip(b'/').decode()
                    body=b'bad' if bad else b'ok\n'
                    identity=f'{mode}-{self.requests}' if fresh else f'{mode}-worker'
                    reuse='no' if fresh else 'yes'
                    writer.write(f'HTTP/1.1 200 OK\r\nContent-Length: 3\r\nX-Actor-Mode: {mode}\r\nX-Worker: {identity}\r\nX-Reused: {reuse}\r\n\r\n'.encode()+body)
                    await writer.drain()
            except (asyncio.IncompleteReadError,ConnectionError):pass
            finally:writer.close();await writer.wait_closed()
        server=await asyncio.start_server(handle,'127.0.0.1',0)
        self.addAsyncCleanup(self.close,server)
        return server.sockets[0].getsockname()[1]
    async def close(self,server):server.close();await server.wait_closed()
    async def test_sustains_requests_on_same_connections(self):
        port=await self.start()
        with tempfile.TemporaryDirectory() as directory:
            result=await load.measure(port,4,.1,.01,1,Path(directory))
        self.assertEqual(self.connections,4)
        self.assertGreater(self.requests,4)
        self.assertEqual(result['retries'],0)
        self.assertEqual(result['failures'],[])
        for mode in ('shared','isolated'):
            self.assertEqual(result['modes'][mode]['distinct_workers_observed'],1)
            self.assertGreater(result['modes'][mode]['reused_responses'],1)
    async def test_sampling_marks_requests_and_counts_them(self):
        port=await self.start()
        with tempfile.TemporaryDirectory() as directory:
            result=await load.measure(port,4,.1,0,1,Path(directory),1)
        self.assertGreater(result['sampled_requests'],0)
        self.assertEqual(result['sampled_requests'],self.sampled)
        self.assertEqual(self.sampled,self.requests)

    async def test_single_actor_mode_does_not_include_other_mode(self):
        for mode in ('shared','isolated'):
            port=await self.start()
            with tempfile.TemporaryDirectory() as directory:
                result=await load.measure(port,4,.1,0,1,Path(directory),0,mode)
            self.assertEqual(set(result['modes']),{mode})
            self.assertEqual(result['connections_opened'],4)

    async def test_fresh_actors_have_unique_ids_and_no_reuse(self):
        port=await self.start(fresh=True)
        with tempfile.TemporaryDirectory() as directory:
            result=await load.measure(port,4,.1,.01,1,Path(directory),0,'shared','fresh')
        row=result['modes']['shared']
        self.assertEqual(row['reused_responses'],0)
        self.assertEqual(row['distinct_workers_with_warmup'],self.requests)

    async def test_fresh_mode_rejects_reused_workers(self):
        port=await self.start()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError,'Fresh actor identity reused'):
                await load.measure(port,2,.1,0,1,Path(directory),0,'shared','fresh')

    def test_fresh_fixture_preserves_telemetry_before_termination(self):
        template=(load.ROOT/'tests/profiled-pooled-server.atto').read_text()
        fresh=load.configure_fixture(template,'fresh',32)
        self.assertNotIn('.pooled(',fresh)
        self.assertEqual(fresh.count('self.end();'),2)
        self.assertEqual(fresh.count('"admission.to_response_continuation"'),2)
        self.assertEqual(load.configure_fixture(template,'pooled',128).count('.pooled(128)'),2)

    def test_fresh_concurrent_fixture_preserves_supervisor_lifecycle(self):
        template=(load.ROOT/'tests/profiled-concurrent-server.atto').read_text()
        fresh=load.configure_fixture(template,'fresh',32)
        self.assertEqual(fresh.count('self.end();'),2)
        self.assertNotIn('self.end();',fresh.split('pub define class ProfileDispatcher')[1])
        self.assertIn('await dispatcher.serve(4);',fresh)

    async def test_bad_response_fails_without_reconnect(self):
        port=await self.start(bad=True)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError,'Sustained test had failures'):
                await load.measure(port,2,.1,0,1,Path(directory))
        self.assertEqual(self.connections,2)
        self.assertEqual(self.requests,2)

if __name__=='__main__':unittest.main()
