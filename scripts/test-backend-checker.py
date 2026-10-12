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
                             {'path': 'probe.ores', 'diagnostic': 'oreslang-llvmc: expected fnc or routine at byte 0'}]}}
    def load(self):
        (self.root/'BACKENDS.json').write_text(json.dumps(self.contract))
        return checker.load_contract()
    def test_valid_contract(self):
        self.assertEqual(self.load(), self.contract)
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

if __name__ == '__main__': unittest.main()
