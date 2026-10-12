#!/usr/bin/env python3
"""Check pinned compiler provenance and execute the declared backend contract."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def git(directory, *args):
    return subprocess.check_output(['git', '-C', str(directory), *args], text=True).strip()

def require_source(variable, pin):
    raw = os.environ.get(variable)
    if not raw:
        raise RuntimeError(f'Set {variable} to the pinned compiler checkout')
    source = Path(raw).resolve()
    expected = (ROOT / pin).read_text().strip()
    if not re.fullmatch('[0-9a-f]{40}', expected):
        raise RuntimeError(f'Invalid {pin}')
    if Path(git(source, 'rev-parse', '--show-toplevel')).resolve() != source:
        raise RuntimeError('Compiler directory must be its own Git checkout')
    if git(source, 'rev-parse', 'HEAD') != expected:
        raise RuntimeError(f'Compiler revision differs from {pin}')
    if git(source, 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError('Compiler checkout must be clean')
    return source

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend', choices=['java', 'llvm'])
    args = parser.parse_args()
    contract = json.loads((ROOT / 'BACKENDS.json').read_text())
    if args.backend == 'java':
        require_source('ORESLANG_SOURCE_DIR', 'SOURCE_REF')
        env = dict(os.environ)
        env.setdefault('ORESLANG_COMPILER', str(ROOT / 'scripts/compiler.sh'))
        env.setdefault('ORESLANG_BIN', env['ORESLANG_COMPILER'])
        return subprocess.run(['bash', str(ROOT / 'scripts/test.sh')], cwd=ROOT, env=env, timeout=180).returncode
    source = require_source('ORESLANG_LLVM_SOURCE_DIR', 'LLVM_SOURCE_REF')
    compiler = Path(os.environ.get('ORESLANG_LLVM_COMPILER', str(source / 'build/oreslang-llvmc'))).resolve()
    if not compiler.is_file() or not os.access(compiler, os.X_OK):
        raise RuntimeError(f'Build oreslang-llvmc first: {compiler}')
    with tempfile.TemporaryDirectory(prefix='ores-backend-') as directory:
        baseline = Path(directory) / 'baseline.ores'
        baseline.write_text('pub fnc main(): int { return 42; }\n')
        positive = subprocess.run([str(compiler), str(baseline)], capture_output=True, text=True, timeout=30)
        if positive.returncode or 'define i64 @main(' not in positive.stdout:
            raise RuntimeError('LLVM positive control failed; rejection is not evidence of compatibility: ' + positive.stderr)
        for relative in contract['llvm']['rejection_probes']:
            entry = ROOT / relative
            if not entry.is_file():
                raise RuntimeError(f'Missing LLVM rejection probe: {relative}')
            result = subprocess.run([str(compiler), str(entry)], capture_output=True, text=True, timeout=30)
            if result.returncode != 1 or result.stdout.strip() or not result.stderr.startswith('oreslang-llvmc: '):
                raise RuntimeError(f'Expected unsupported source rejection without IR: {relative}\n{result.stderr}')
            print(f'LLVM rejected {relative}: {result.stderr.strip()}')
    print('LLVM rejection contract: PASS (package execution remains unsupported)')
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.SubprocessError) as failure:
        raise SystemExit(f'backend check failed: {failure}')
