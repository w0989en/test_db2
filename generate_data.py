#!/usr/bin/env python3
"""Generate the same deterministic Db2 DEL file for both benchmark methods."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--output", type=Path, default=Path("data/rows.del"))
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows must be positive")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="ascii", newline="\n", buffering=1024 * 1024) as output:
        for row_id in range(1, args.rows + 1):
            output.write(f"{row_id},payload-{row_id:07d}-abcdefghijklmnop,{row_id % 10000}\n")
    temporary.replace(args.output)
    print(f"generated_rows={args.rows} file={args.output} bytes={args.output.stat().st_size}")


if __name__ == "__main__":
    main()
