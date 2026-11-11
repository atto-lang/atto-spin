#!/usr/bin/env python3
"""Black-box HTTP checks against native Oreslang actors; no simulated compiler."""
import contextlib, concurrent.futures, http.client, json, os, pathlib, queue, socket, subprocess, threading, time
import transport_security

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPILER = os.environ.get('ORESLANG_COMPILER', 'oreslang-compiler')

def main():
    subprocess.run([COMPILER, '--check', '--platform=server', str(ROOT/'tests/server.ores')], check=True, cwd=ROOT)
    with subprocess.Popen([COMPILER, '--platform=server', '--allow-net=127.0.0.1:0', str(ROOT/'tests/server.ores')], cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as server:
        lines, errors = queue.Queue(), []
        threading.Thread(target=lambda: [lines.put(line.strip()) for line in server.stdout], daemon=True).start()
        threading.Thread(target=lambda: [errors.append(line) for line in server.stderr], daemon=True).start()
        try:
            assert lines.get(timeout=15) == 'true', 'builder must reject a second build'
            port = int(lines.get(timeout=5))
            def req(path, method='GET', body=None, headers=None, connection=None):
                conn = connection or http.client.HTTPConnection('127.0.0.1', port, timeout=8)
                try:
                    conn.request(method, path, body=body, headers=headers or {})
                    response = conn.getresponse()
                    return response.status, dict((k.lower(), v) for k,v in response.getheaders()), response.read()
                finally:
                    if connection is None: conn.close()
            checks = 0
            def check(ok, label):
                nonlocal checks
                assert ok, label
                checks += 1
            status, headers, body = req('/shared')
            check((status, body, headers['x-actor-mode']) == (200,b'shared','shared'), 'shared route')
            check(headers['x-spin'] == 'test' and len(headers['x-request-id']) == 36, 'middleware and request ID')
            check(req('/private')[2] == b'private', 'isolated route')
            check(req('/echo', 'POST', 'private-body')[2] == b'private-body', 'body and helper Future flattening')
            check(req('/binary', 'POST', bytes(range(256)))[2] == bytes(range(256)), 'binary body and response streaming')
            check(req('/users/a%2Fb?q=a+b', headers={'Cookie':'session=abc'})[2] == b'a/b|a b|abc', 'captures/query/cookies')
            check(req('/files/a%2Fb/c')[2] == b'a/b|c', 'wildcard preserves encoded slash')
            check(req('/shared/')[0] == 404, 'strict trailing slash')
            check(req('/shared//')[0] == 404, 'strict repeated slash')
            check(req('/missing')[0] == 404, 'not found')
            check(req('/missing')[1].get('x-route-outcome') == 'spin.404',
                  '404 middleware sees selected framework outcome')
            check(req('/shared', 'POST')[1].get('x-route-outcome') == 'spin.405',
                  '405 middleware sees selected framework outcome')
            check(req('/shared', 'OPTIONS')[1].get('x-route-outcome') == 'spin.204',
                  'automatic OPTIONS middleware sees selected framework outcome')
            for method in ('GET','POST','OPTIONS'):
                path = '/missing' if method == 'GET' else '/shared'
                check(req(path, method)[1].get('x-spin-responder') == 'actor', 'framework reply owns exchange in actor')
            for value in ('first','second','first'):
                response = req('/users/alice?q='+value, headers={'Cookie':'session='+value})
                check(response[2] == ('alice|'+value+'|'+value).encode(), 'repeated route retains no request query/cookie state')
            for index in range(40):
                check(req('/users/user'+str(index)+'?q=q', headers={'Cookie':'session=v'})[2] == ('user'+str(index)+'|q|v').encode(), 'distinct requests preserve path captures')
            check(req('/shared')[0] == 200, 'literal route still responds after dynamic requests')
            check(req('/shared', headers={'X-Fail':'yes'})[0] == 500, 'middleware failure contained')
            check(req('/shared')[0] == 200, 'supervisor survives middleware failure')
            status, headers, _ = req('/shared', 'POST')
            check(status == 405 and headers['allow'] == 'GET, HEAD, OPTIONS', 'method not allowed')
            status, headers, body = req('/shared', 'HEAD')
            check(status == 200 and body == b'' and headers['content-length'] == '6', 'HEAD suppression')
            status, headers, body = req('/shared', 'OPTIONS', headers={'Origin':'https://example.test'})
            check(status == 204 and headers['allow'] == 'GET, HEAD, OPTIONS' and headers['access-control-allow-origin'] == 'https://example.test', 'OPTIONS and middleware')
            check(req('/auth')[0] == 401 and req('/auth', headers={'Authorization':'Bearer test'})[0] == 200, 'route pipeline auth')
            check(req('/stream')[2] == b'data: one\n\ndata: two\n\n', 'response streaming')
            check(req('/stream', 'HEAD')[2] == b'', 'HEAD suppresses streamed writes')
            check(req('/echo', 'POST', 'x'*2048)[0] == 413, 'body limit')
            check(req('/echo', 'POST', iter([b'a'*600,b'b'*600]))[0] == 413, 'chunked body limit')
            check(req('/users/%C0%AF')[0] == 400, 'invalid UTF-8 path')
            checks += transport_security.run(port)  # real raw-wire protocol and post-rejection recovery
            check(req('/crash')[0] == 500, 'actor crash cleanup')
            check(req('/startup-failure')[0] == 500, 'actor startup failure cleanup')
            check(req('/timeout')[0] == 504, 'deadline cleanup')
            with contextlib.closing(http.client.HTTPConnection('127.0.0.1', port, timeout=8)) as conn:
                for path in ['/shared','/private','/shared']:
                    check(req(path, connection=conn)[0] == 200, 'keep-alive across actor kinds')
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda i: req('/shared' if i%2 == 0 else '/private'), range(80)))
            check(all(r[0] == 200 for r in results), 'concurrent mixed actor requests')
            ids = [r[1]['x-request-id'] for r in results if 'x-request-id' in r[1]]
            check(len(ids) == len(set(ids)), 'fresh request actor identities')
            # Hold all admission slots with live actors. Additional requests must fail promptly.
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
                held = [pool.submit(req, '/timeout') for _ in range(16)]
                time.sleep(0.2)
                check(req('/shared')[0] == 503, 'bounded overload')
                check(all(f.result()[0] == 504 for f in held), 'deadline releases every admission slot')
            check(req('/shared')[0] == 200, 'recovery after overload')
            for _ in range(16): check(req('/linger')[0] == 200, 'response before actor end')
            check(req('/shared')[0] == 503, 'completed response retains actor admission')
            time.sleep(2.1)
            check(req('/shared')[0] == 200, 'deadline retires actors that omit self.end')
            # Client disconnect must not poison the listener; deadline closes abandoned work.
            abandoned = socket.create_connection(('127.0.0.1',port))
            abandoned.sendall(b'POST /echo HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nx')
            abandoned.close()
            check(req('/shared')[0] == 200, 'recovery after disconnect')
            check(req('/linger')[0] == 200, 'live actor before shutdown')
            check(req('/__stop')[0] == 200, 'graceful shutdown request')
            server.wait(timeout=10)
            check(server.returncode == 0, 'clean process exit: '+''.join(errors[-20:]))
            check(lines.get(timeout=5) == '0', 'zero active exchanges after shutdown')
            print(json.dumps({'checks': checks, 'result':'PASS'}))
        except Exception:
            print(''.join(errors[-50:]))
            raise
        finally:
            if server.poll() is None:
                server.terminate()
                try: server.wait(timeout=5)
                except subprocess.TimeoutExpired: server.kill(); server.wait()

if __name__ == '__main__': main()
