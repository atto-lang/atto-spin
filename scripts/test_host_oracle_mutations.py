#!/usr/bin/env python3
"""Fail-closed, host-only mutation gate for Spin's raw HTTP response oracle.

Only this raw-wire helper is modified inside temporary directories. The
AttoLang compiler, native Spin server and their tests are not exercised here.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'tests' / 'transport_security.py'
TEST = ROOT / 'tests' / 'test_transport_security.py'

# Every mutation must be killed by a named behavior assertion, not an ImportError
# or syntax failure. Matching anchors exactly once avoids vacuous tests.
MUTATIONS = (
    ('length-framing',
     'if len(body) != int(lengths[0]):', 'if False:',
     'test_rejects_truncated_response_body'),
    ('guest-marker',
     "if name != 'invalid_chunk_size' and b'x-spin' in headers:",
     'if False:', 'test_rejected_header_must_not_enter_guest_middleware'),
    ('connection-close',
     'if not closed:', 'if False:',
     'test_open_malformed_success_or_server_error_cannot_pass'),
    ('strict-status',
     'if status not in expected:', 'if False:',
     'test_unsupported_transfer_coding_allows_exact_501'),
    ('chunk-terminator',
     "if body[position:] != b'\\r\\n':", 'if False:',
     'test_chunked_response_pipelined_reply_fails'),
    ('header-controls',
     'if any((c < 32 and c != 9) or c == 127 for c in value):',
     'if False:', 'test_response_header_value_control_byte_is_rejected'),
    ('no-length-pipelining',
     "elif re.search(rb'(?:\\A|\\r\\n)HTTP/1\\.[01] [0-9]{3}[ \\r]', body):",
     'elif False:', 'test_close_delimited_fake_second_response_is_rejected'),
)


def run_case(label, source):
    with tempfile.TemporaryDirectory(prefix='spin-oracle-mutation-') as tmp:
        tests = Path(tmp) / 'tests'
        tests.mkdir()
        (tests / 'transport_security.py').write_text(source, encoding='utf-8')
        shutil.copyfile(TEST, tests / 'test_transport_security.py')
        completed = subprocess.run(
            [sys.executable, '-B', '-m', 'unittest', 'discover', '-s',
             str(tests), '-p', 'test_transport_security.py', '-v'],
            capture_output=True, text=True, timeout=20, check=False,
        )
        return completed


def main():
    source = SRC.read_text(encoding='utf-8')
    baseline = run_case('baseline', source)
    if baseline.returncode != 0 or 'Ran 36 tests' not in baseline.stderr:
        raise SystemExit(f'baseline must run all 36 host-only tests: {baseline.stderr[-2500:]}')
    print('PASS: baseline 36/36 host-only tests')
    for label, old, new, expected_test in MUTATIONS:
        if source.count(old) != 1:
            raise SystemExit(f'FAIL: {label} source mutation anchor count={source.count(old)}')
        mutant = run_case(label, source.replace(old, new, 1))
        failure = f'FAIL: {expected_test} '
        if (mutant.returncode == 0 or 'Ran 36 tests' not in mutant.stderr
                or failure not in mutant.stderr):
            raise SystemExit(f'FAIL: {label} mutation survived or failed without targeted '
                             f'assertion: {mutant.stderr[-2500:]}')
        print(f'PASS: {label} killed by {expected_test}')
    print(f'PASS: {len(MUTATIONS)}/{len(MUTATIONS)} targeted host-only mutants killed')


if __name__ == '__main__':
    main()
