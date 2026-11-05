#!/usr/bin/env python3
"""Negative contracts for backend admission; never substitutes for package tests."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('checker', Path(__file__).with_name('check-backend.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

class BackendChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.patch = patch.object(checker, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.root/'suite.sh').write_text('exit 0\n')
        (self.root/'probe.ores').write_text('import unsupported;\n')
        self.contract = {'java': {'pin': 'SOURCE_REF', 'suite': 'suite.sh', 'execution': 'supported'},
                         'llvm': {'pin': 'LLVM_SOURCE_REF', 'execution': 'unsupported', 'rejection_probes': [
                             {'path': 'probe.ores', 'diagnostic': 'oreslang-llvmc: expected fnc or routine at byte 0'}]},
                         'wasm': {'source_repo': 'oreslang-source.wasm', 'execution': 'unverified', 'evidence': 'none'},
                         'cranelift': {'source_repo': 'oreslang-source.cranelift', 'execution': 'unverified', 'evidence': 'none'},
                         'net': {'source_repo': 'oreslang-source.net', 'execution': 'unverified', 'evidence': 'none'}}
    def load(self):
        (self.root/'BACKENDS.json').write_text(json.dumps(self.contract))
        return checker.load_contract()
    def test_valid_contract(self):
        self.assertEqual(self.load(), self.contract)
    def test_five_backend_manifest_cannot_silently_promote(self):
        self.assertEqual(set(self.load()), {'java', 'llvm', 'wasm', 'cranelift', 'net'})
        for backend in ('wasm', 'cranelift', 'net'):
            for field, bad in (('execution', 'supported'), ('execution', 'partial'),
                               ('source_repo', 'oreslang-source.java'), ('evidence', 'unit-tests-only')):
                with self.subTest(backend=backend, field=field, bad=bad):
                    original = self.contract[backend][field]
                    self.contract[backend][field] = bad
                    with self.assertRaises(RuntimeError): self.load()
                    self.contract[backend][field] = original

    def test_missing_or_invented_backend_fails_closed(self):
        for backend in ('wasm', 'cranelift', 'net'):
            value = self.contract.pop(backend)
            with self.subTest(missing=backend), self.assertRaises(RuntimeError): self.load()
            self.contract[backend] = value
        self.contract['forge'] = {'execution': 'supported'}
        with self.assertRaises(RuntimeError): self.load()

    def test_unverified_backend_requires_specific_schema(self):
        for backend in ('wasm', 'cranelift', 'net'):
            self.contract[backend]['fake_receipt'] = 'pass'
            with self.subTest(backend=backend), self.assertRaises(RuntimeError): self.load()
            del self.contract[backend]['fake_receipt']

    def test_unverified_backend_cli_never_returns_success(self):
        self.load()
        for backend in ('wasm', 'cranelift', 'net'):
            with self.subTest(backend=backend):
                with patch.object(sys, 'argv', ['check-backend.py', backend]):
                    with self.assertRaisesRegex(RuntimeError, 'is unverified'):
                        checker.main()

    def test_specific_actor_boundary_diagnostic(self):
        self.contract['llvm']['rejection_probes'][0]['diagnostic'] = 'oreslang-llvmc: actor requires at least one scalar field at byte 151'
        self.assertEqual(self.load(), self.contract)
        self.contract['llvm']['rejection_probes'][0]['diagnostic'] = 'oreslang-llvmc: internal compiler error'
        with self.assertRaises(RuntimeError): self.load()
    def test_specific_native_field_boundary(self):
        self.contract['llvm']['rejection_probes'][0]['diagnostic'] = 'oreslang-llvmc: native class field supports only scalar int or mut Array<int> at byte 289'
        self.assertEqual(self.load(), self.contract)
        self.contract['llvm']['rejection_probes'][0]['diagnostic'] = 'oreslang-llvmc: native class internal compiler error'
        with self.assertRaises(RuntimeError): self.load()
    def test_bool_field_boundary_requires_precise_offset(self):
        prefix = 'oreslang-llvmc: native class field supports only scalar int/bool or mut Array<int> at byte '
        self.contract['llvm']['rejection_probes'][0]['diagnostic'] = prefix + '289'
        self.assertEqual(self.load(), self.contract)
        for suffix in ('nope', '289 additional error', ''):
            self.contract['llvm']['rejection_probes'][0]['diagnostic'] = prefix + suffix
            with self.subTest(suffix=suffix), self.assertRaises(RuntimeError): self.load()
    def test_empty_probes_rejected(self):
        self.contract['llvm']['rejection_probes'] = []
        with self.assertRaises(RuntimeError): self.load()
    def test_duplicate_probes_rejected(self):
        self.contract['llvm']['rejection_probes'] *= 2
        with self.assertRaises(RuntimeError): self.load()
    def test_missing_probe_rejected(self):
        (self.root/'probe.ores').unlink()
        with self.assertRaises(RuntimeError): self.load()
    def test_escape_paths_rejected(self):
        for path in ('../outside', str(self.root/'probe.ores')):
            with self.subTest(path=path), self.assertRaises(RuntimeError): checker.local_file(path)
    def test_symlink_escape_rejected(self):
        (self.root/'escape').symlink_to('/etc/hosts')
        with self.assertRaises(RuntimeError): checker.local_file('escape')
    def test_changed_execution_status_rejected(self):
        self.contract['llvm']['execution'] = 'supported'
        with self.assertRaises(RuntimeError): self.load()
    def test_malformed_contract_rejected(self):
        for value in ([], None, {'java': None, 'llvm': []}):
            self.contract = value
            with self.subTest(value=value), self.assertRaises(RuntimeError): self.load()
    def test_internal_error_not_expected_rejection(self):
        probe=self.contract['llvm']['rejection_probes'][0]
        for code,out,err in [(0,'',probe['diagnostic']), (1,'IR',probe['diagnostic']),
                             (1,'','oreslang-llvmc: internal compiler error'), (-11,'',probe['diagnostic']),
                             (1,'',probe['diagnostic']+'\nadditional failure')]:
            with self.subTest(code=code,out=out,err=err), self.assertRaises(RuntimeError):
                checker.check_rejection(subprocess.CompletedProcess([],code,out,err),probe)
        checker.check_rejection(subprocess.CompletedProcess([],1,'',probe['diagnostic']+'\n'),probe)
    def test_native_os_entrypoint_control(self):
        valid = 'define i32 @main() {\n  ret i32 42\n}\n'
        checker.check_positive(subprocess.CompletedProcess([], 0, valid, ''))
        for code, output in ((1, valid), (-11, valid), (0, ''), (0, 'define i64 @main() { ret i64 42 }')):
            with self.subTest(code=code, output=output), self.assertRaises(RuntimeError):
                checker.check_positive(subprocess.CompletedProcess([], code, output, 'failure'))
    def test_provenance_fails_closed(self):
        source=self.root/'source'
        source.mkdir()
        def git(*args):
            return subprocess.check_output(['git','-C',str(source),*args],text=True).strip()
        git('init','-q')
        (source/'tracked').write_text('original')
        git('add','tracked')
        git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture')
        pin=self.root/'SOURCE_REF'
        pin.write_text(git('rev-parse','HEAD'))
        with patch.dict(os.environ, {'BACKEND_TEST_SOURCE':str(source)}):
            self.assertEqual(checker.require_source('BACKEND_TEST_SOURCE','SOURCE_REF'),source)
            for revision in ('main','0'*40):
                pin.write_text(revision)
                with self.assertRaises(RuntimeError): checker.require_source('BACKEND_TEST_SOURCE','SOURCE_REF')
            pin.write_text(git('rev-parse','HEAD'))
            (source/'untracked').write_text('dirty')
            with self.assertRaises(RuntimeError): checker.require_source('BACKEND_TEST_SOURCE','SOURCE_REF')
            (source/'untracked').unlink()
            (source/'tracked').write_text('changed')
            with self.assertRaises(RuntimeError): checker.require_source('BACKEND_TEST_SOURCE','SOURCE_REF')
            with patch.object(checker,'git',side_effect=subprocess.CalledProcessError(128,['git'])):
                with self.assertRaises(subprocess.CalledProcessError): checker.require_source('BACKEND_TEST_SOURCE','SOURCE_REF')

    def test_java_suite_and_llvm_probe_cannot_escape_checkout_root(self):
        self.contract['java']['suite'] = '../../foreign.sh'
        with self.assertRaises(RuntimeError):
            self.load()
        self.contract['java']['suite'] = 'suite.sh'
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / 'foreign.ores').write_text('pub fnc main() {}\n')
            (self.root / 'outside-linked').symlink_to(outside, target_is_directory=True)
            self.contract['llvm']['rejection_probes'][0]['path'] = 'outside-linked/foreign.ores'
            with self.assertRaises(RuntimeError):
                self.load()

    def test_nonsemantic_process_failure_cannot_imitate_precise_llvm_rejection(self):
        probe = self.contract['llvm']['rejection_probes'][0]
        for code in (0, 2, 125, 255, -9):
            with self.subTest(exit_code=code), self.assertRaises(RuntimeError):
                checker.check_rejection(
                    subprocess.CompletedProcess([], code, '', probe['diagnostic'] + '\n'),
                    probe,
                )
        for diagnostic in ('', 'unrelated parser error', probe['diagnostic'] + '\nsecond error'):
            with self.subTest(diagnostic=diagnostic), self.assertRaises(RuntimeError):
                checker.check_rejection(
                    subprocess.CompletedProcess([], 1, '', diagnostic),
                    probe,
                )

    def test_invalid_java_source_pin_cannot_use_an_unversioned_branch_name(self):
        (self.root / 'SOURCE_REF').write_text('main\n')
        with patch.dict(os.environ, {'ORESLANG_SOURCE_DIR': str(self.root)}):
            with self.assertRaisesRegex(RuntimeError, 'Invalid SOURCE_REF'):
                checker.require_source('ORESLANG_SOURCE_DIR', 'SOURCE_REF')

if __name__ == '__main__': unittest.main()
