#!/usr/bin/env python3
"""Preflight guard for dangerous leading-parenthesis Luau statements.

Rojo packages source text without parsing it. Roblox Studio then fails at
require() time, which prevents the entire Game1Bridge toolbar from loading.
This intentionally narrow style guard is NOT a full Luau syntax parser.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def ambiguous_leading_parentheses(source: str) -> list[int]:
    """Block casts/calls that start a physical line with '(' in plugin Luau.

    They are especially ambiguous after a previous method/function call and
    Luau reports 'Ambiguous syntax: this looks like an argument list'.
    Use a named local instead; keep parentheses inside expressions.
    """
    return [index for index, line in enumerate(source.splitlines(), 1)
            if line.lstrip().startswith('(')]


def check_plugin(plugin_dir: Path) -> list[str]:
    errors: list[str] = []
    files = sorted(plugin_dir.rglob('*.luau'))
    if not files:
        return [f'No Luau files found in {plugin_dir}']
    for path in files:
        try:
            source = path.read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError) as exc:
            errors.append(f'{path}: unreadable source: {exc}')
            continue
        for number in ambiguous_leading_parentheses(source):
            errors.append(f'{path}:{number}: statement starts with "("; '
                          'introduce a named local to avoid ambiguous Luau syntax')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-dir', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    problems = check_plugin(args.plugin_dir)
    if problems:
        for problem in problems:
            print(f'FAIL: {problem}', file=sys.stderr)
        return 1
    print('OK: Studio Luau leading-parenthesis ambiguity guard')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
