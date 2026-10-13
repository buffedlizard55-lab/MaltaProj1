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
    try:
        collect(arguments.output)
    except Exception as error:
        # Keep the actionable failure in GitHub's check annotations as well as
        # the log. Only error type/record-field names, never raw payloads/headers.
        message = f"{type(error).__name__}: {error}".replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=Primary evidence validation failed::{message}", flush=True)
        raise
