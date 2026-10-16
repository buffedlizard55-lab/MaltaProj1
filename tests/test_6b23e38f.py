"""Run the maintained board's source/identity/probability/UI invariants in its own module namespace."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class PrimaryReliability(unittest.TestCase):
    def test_primary_source_probability_archive_and_page_contracts(self):
        result=subprocess.run([sys.executable,'hotspawn/tests.py'],cwd=ROOT,text=True,capture_output=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

    def test_all_primary_rows_reconcile_with_captured_inputs(self):
        result=subprocess.run([sys.executable,'hotspawn/verify.py'],cwd=ROOT,text=True,capture_output=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
