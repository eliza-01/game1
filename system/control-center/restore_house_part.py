"""Operator-controlled recovery of one house part's prior published revision."""
import argparse
import json
from pathlib import Path
from real_estate.publication_restore import restore_visual_part


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--house', required=True)
    parser.add_argument('--part', required=True)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--current-id', required=True)
    parser.add_argument('--restore-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = restore_visual_part(root, slug=args.house, part=args.part,
        snapshot=args.snapshot, current_id=args.current_id, restore_id=args.restore_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
