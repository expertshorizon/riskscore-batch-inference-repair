#!/usr/bin/env python3
import argparse
from pathlib import Path

from riskscore_engine.pipeline import run_batch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", default="/app/fixtures")
    parser.add_argument("--output", default="/app/output")
    args = parser.parse_args()
    run_batch(Path(args.fixtures), Path(args.output))


if __name__ == "__main__":
    main()
