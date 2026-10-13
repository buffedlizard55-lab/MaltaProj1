#!/usr/bin/env python3
"""Collect verified public evidence without any manual match/odds input."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from collector.runner import collect

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/snapshot/latest.json")
    arguments = parser.parse_args()
    collect(arguments.output)
