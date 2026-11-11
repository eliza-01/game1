"""One-time M276 Character atlas naming migration. Run from the game1 root.

Default is a read-only preview; pass --apply to commit after a DB backup.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.character_atlas_migration import migrate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--apply', action='store_true', help='perform the reviewed migration')
    actions.add_argument('--dry-run', action='store_true', help='print migration plan without changes (default)')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2],
                        help='game1 project directory')
    args = parser.parse_args()
    try:
        print(json.dumps(migrate(args.root, apply=args.apply), indent=2, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'M276 atlas migration blocked: {exc}\n')


if __name__ == '__main__':
    main()
