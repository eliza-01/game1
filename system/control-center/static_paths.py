"""Resolve public static files strictly inside the configured document root.

The HTTP proxy has a separate /api/* branch. This module never reads
outside the static directory, including symlinks and encoded traversal.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit


def resolve_static_file(root: Path, request_target: str) -> Path | None:
    try:
        requested = unquote(urlsplit(request_target).path)
        if "\x00" in requested or "\\" in requested:
            return None
        relative = requested.lstrip("/") or "index.html"
        resolved_root = root.resolve()
        candidate = (resolved_root / relative).resolve()
        if not candidate.is_relative_to(resolved_root):
            return None
        if not candidate.is_file():
            return None
        return candidate
    except (OSError, ValueError):
        return None
