#!/usr/bin/env python3
"""Preflight guard for dangerous leading-parenthesis Luau statements.

Rojo packages source text without parsing it. Roblox Studio then fails at
require() time, which prevents the entire Game1Bridge toolbar from loading.
This intentionally narrow style guard is NOT a full Luau syntax parser.
"""
from __future__ import annotations

import argparse
import json
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


def missing_place_registry_row_separator(source: str) -> list[int]:
    """Catch the M342R regression: deleting a table branch removed its comma.

    Only checks the known multi-line row transition, not the full Luau grammar.
    A complete Luau parser is still needed for general syntax validation.
    """
    lines = source.splitlines()
    errors = []
    for index, line in enumerate(lines):
        if 'or (root and root:GetAttribute("Game1DecoAssetSlug")~=entry.slug)' not in line:
            continue
        next_index = index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            next_index += 1
        if (next_index < len(lines)
                and lines[next_index].strip().startswith('duplicateId=')
                and not line.rstrip().endswith(',')):
            errors.append(index + 1)
    return errors


def check_plugin(plugin_dir: Path) -> list[str]:
    errors: list[str] = []
    files = sorted(plugin_dir.rglob('*.luau'))
    # A Rojo alias may point to a deliberately shared Luau module outside
    # system/studio-plugin. Validate those sources too before installation.
    manifest = plugin_dir / 'plugin.project.json'
    if manifest.is_file():
        try:
            spec = json.loads(manifest.read_text(encoding='utf-8'))
            for module in spec['tree']['modules'].values():
                if isinstance(module, dict) and '$path' in module:
                    resolved = (plugin_dir / module['$path']).resolve()
                    if resolved.suffix == '.luau' and resolved.is_file() and resolved not in files:
                        files.append(resolved)
        except (OSError, KeyError, ValueError, TypeError) as exc:
            return [f'Invalid Studio plugin Rojo manifest: {exc}']
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
        for number in missing_place_registry_row_separator(source):
            errors.append(f'{path}:{number}: missing comma before duplicateId '
                          'in Place Registry row table (M342R regression)')
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
