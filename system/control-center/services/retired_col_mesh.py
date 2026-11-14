"""M342: retired COL meshes; only input filtering and cleanup may recognize these names.

COL_ meshes are never an Asset Manager role or part of a published house.
Names are compared case-insensitively; authored FBX files are immutable input.
"""
from __future__ import annotations
import re

_RETIRED = re.compile(r"(?:^|_)col(?:_|$)", re.IGNORECASE)


def retired(name: object) -> bool:
    return isinstance(name, str) and bool(_RETIRED.search(name))


def strip_mesh_rows(analysis: dict) -> dict:
    if not isinstance(analysis, dict):
        return analysis
    rows = analysis.get('meshes')
    if not isinstance(rows, list):
        return analysis
    return {**analysis, 'meshes': [row for row in rows if not retired(row.get('name'))]}


def strip_options(options: dict | None) -> dict:
    return {key: ({subkey: subval for subkey, subval in val.items()
                   if subkey not in ('collisionMesh', 'destructible')} if isinstance(val, dict) else val)
            for key, val in (options or {}).items() if not retired(key)}
