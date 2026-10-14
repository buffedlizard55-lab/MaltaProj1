#!/usr/bin/env python3
"""scripts/5545dbb8_build.py — one entry point for the executive board pipeline (session arena/5545dbb8).

    python scripts/5545dbb8_build.py --offline   # build from repository captures (no network)
    python scripts/5545dbb8_build.py             # live collect, then build, then verify

CI runs the three steps separately so a failure is attributable: see
.github/workflows/executive-5545dbb8.yml.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(step: str, *args: str) -> int:
    print(f"\n=== {step} ===", flush=True)
    return subprocess.call([sys.executable, *args], cwd=str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true",
                        help="skip live network reads and use this repository's captured inputs")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    collect = ["executive/collect.py"] + (["--offline"] if args.offline else [])
    if run("collect", *collect) != 0:
        return 1
    if run("build", "executive/build.py") != 0:
        return 1
    if not args.skip_tests and run("tests", "executive/tests.py") != 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
