#!/usr/bin/env python3
"""Re-audit public sources using the production privacy and market allowlists.

The original broad exploration is retired. Unrelated leaderboard/account data,
request headers, API keys, and raw page transfer state are never archived here.
See research/research.md for the initial discovery record and limitations.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from collector.runner import collect

if __name__ == "__main__":
    collect(ROOT / ".cache/discovery-audit/latest.json")
