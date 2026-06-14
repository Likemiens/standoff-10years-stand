from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.config import load_config
from app.content_resolver import ContentResolver


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Standoff content files")
    parser.add_argument("--config", default="config.json", help="Path to config JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    resolver = ContentResolver(config)
    result = resolver.check_content()

    print(f"Content dir: {result.content_dir}")
    print(f"Status: {'OK' if result.ok else 'ERROR'} ({result.summary})")

    if result.missing:
        print("\nMissing:")
        for file_name in result.missing:
            print(f"  - {file_name}")

    if result.empty:
        print("\nEmpty:")
        for file_name in result.empty:
            print(f"  - {file_name}")

    if result.unreadable:
        print("\nUnreadable:")
        for file_name in result.unreadable:
            print(f"  - {file_name}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
