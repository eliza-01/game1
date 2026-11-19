"""Preflight the standalone Game1Bridge Rojo module inventory (M375a)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def check_studio_plugin_manifest(root: Path, err: Callable[[str], None]) -> None:
    """Mirror the install.ps1 module check without requiring Rojo or Studio."""
    plugin = root / "system/studio-plugin"
    project = plugin / "plugin.project.json"
    try:
        data = json.loads(project.read_text(encoding="utf-8"))
        modules = data["tree"]["modules"]
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        err(f"Studio plugin Rojo manifest is unreadable or invalid: {exc}")
        return
    if not isinstance(modules, dict):
        err("Studio plugin Rojo modules tree must be an object")
        return

    declared_local: set[str] = set()
    for name, record in modules.items():
        if name.startswith("$"):
            continue
        if not isinstance(record, dict) or not isinstance(record.get("$path"), str):
            err(f"Studio plugin module has no source path: {name}")
            continue
        source = record["$path"]
        if not (plugin / source).is_file():
            err(f"Studio plugin Rojo manifest references missing module: {name} ({source})")
        if source.startswith("modules/"):
            declared_local.add(name)
            if source != f"modules/{name}.luau":
                err(f"Studio plugin Rojo module name/path mismatch: {name} ({source})")

    for source_file in sorted((plugin / "modules").glob("*.luau")):
        if source_file.stem not in declared_local:
            err(f"Studio plugin module is present but not in Rojo manifest: {source_file.name}")
