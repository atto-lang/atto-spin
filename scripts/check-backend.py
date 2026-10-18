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

def local_file(relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise RuntimeError('Contract paths must be relative to this repository')
    path = (ROOT / relative).resolve()
    if ROOT.resolve() not in path.parents or not path.is_file():
        raise RuntimeError(f'Missing or outside-repository contract file: {relative}')
    return path

def load_contract():
    contract = json.loads((ROOT / 'BACKENDS.json').read_text())
    if not isinstance(contract, dict) or set(contract) != {'java', 'llvm'}:
        raise RuntimeError('Expected java and llvm backend contracts')
    java, llvm = contract['java'], contract['llvm']
    if not isinstance(java, dict) or not isinstance(llvm, dict):
        raise RuntimeError('Backend contracts must be objects')
    if java.get('pin') != 'SOURCE_REF' or llvm.get('pin') != 'LLVM_SOURCE_REF':
        raise RuntimeError('Unexpected compiler pin files')
    if java.get('execution') not in ('supported', 'partial') or llvm.get('execution') != 'unsupported':
        raise RuntimeError('Unsupported execution contract; update the checker with the tests')
    local_file(java.get('suite'))
    probes = llvm.get('rejection_probes')
    if not isinstance(probes, list) or not probes:
        raise RuntimeError('LLVM rejection probes must be nonempty')
    seen = set()
    for probe in probes:
        if not isinstance(probe, dict) or set(probe) != {'path', 'diagnostic'}:
            raise RuntimeError('Each probe needs a path and exact diagnostic')
        path = local_file(probe['path'])
        if path in seen:
            raise RuntimeError('Duplicate LLVM rejection probe')
        seen.add(path)
        diagnostic = probe['diagnostic']
        if not isinstance(diagnostic, str) or not diagnostic.startswith(('oreslang-llvmc: expected ', 'oreslang-llvmc: actor requires ', 'oreslang-llvmc: native class field supports only scalar int or mut Array<int> at byte ')) or '\n' in diagnostic:
            raise RuntimeError('Expected a specific unsupported-syntax diagnostic')
    return contract

def check_rejection(result, probe):
    if result.returncode != 1 or result.stdout.strip() or result.stderr.strip() != probe['diagnostic']:
        raise RuntimeError(f"Unexpected rejection result for {probe['path']}: exit={result.returncode}\n{result.stderr}")

def check_positive(result):
    # Current native ABI has an OS i32 entrypoint around the guest i64 main.
    if result.returncode or not re.search(r'^define i32 @main\(\)', result.stdout, re.MULTILINE):
        raise RuntimeError('LLVM positive control failed; rejection is not evidence of compatibility: ' + result.stderr)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend', choices=['java', 'llvm'])
    args = parser.parse_args()
    contract = load_contract()
    if args.backend == 'java':
        require_source('ORESLANG_SOURCE_DIR', 'SOURCE_REF')
        env = dict(os.environ)
        env.setdefault('ORESLANG_COMPILER', str(ROOT / 'scripts/compiler.sh'))
        env.setdefault('ORESLANG_BIN', env['ORESLANG_COMPILER'])
        return subprocess.run(['bash', str(local_file(contract['java']['suite']))], cwd=ROOT, env=env, timeout=180).returncode
    source = require_source('ORESLANG_LLVM_SOURCE_DIR', 'LLVM_SOURCE_REF')
    compiler = Path(os.environ.get('ORESLANG_LLVM_COMPILER', str(source / 'build/oreslang-llvmc'))).resolve()
    if not compiler.is_file() or not os.access(compiler, os.X_OK):
        raise RuntimeError(f'Build oreslang-llvmc first: {compiler}')
    with tempfile.TemporaryDirectory(prefix='ores-backend-') as directory:
        baseline = Path(directory) / 'baseline.ores'
        baseline.write_text('pub fnc main(): int { return 42; }\n')
        positive = subprocess.run([str(compiler), str(baseline)], capture_output=True, text=True, timeout=30)
        check_positive(positive)
        for probe in contract['llvm']['rejection_probes']:
            entry = local_file(probe['path'])
            result = subprocess.run([str(compiler), str(entry)], capture_output=True, text=True, timeout=30)
            check_rejection(result, probe)
            print(f"LLVM rejected {probe['path']}: {result.stderr.strip()}")
    print('LLVM rejection contract: PASS (package execution remains unsupported)')
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as failure:
        raise SystemExit(f'backend check failed: {failure}')
