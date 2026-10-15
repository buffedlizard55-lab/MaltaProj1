"""Repository-level entry point for the contrarian leaderboard plan checks (session arena/2e2b2e5e).

The real checks live in leaderboard/tests.py so the board's own workflow can run them before it
publishes; this wrapper lets `python -m unittest discover -s tests` include them. Read-only: it never
rebuilds or rewrites any file.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

LEADERBOARD = Path(__file__).resolve().parents[1] / "leaderboard"
sys.path.insert(0, str(LEADERBOARD))
_spec = importlib.util.spec_from_file_location("leaderboard_tests_2e2b2e5e", LEADERBOARD / "tests.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ModelTests = _mod.ModelTests
ParserTests = _mod.ParserTests
PlanTests = _mod.PlanTests
PageTests = _mod.PageTests

if __name__ == "__main__":
    unittest.main(verbosity=2)
