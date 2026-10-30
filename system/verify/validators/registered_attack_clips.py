"""Cross-check registered attack animations against generated timeline clips (M170)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def check_registered_attack_clips(ROOT: Path, err: Callable[[str], None], *, attack_timeline_data_text: str):
    # Every registered attack animation is required to have an authoritative timeline.
    for manifest_name in ["character-animations.json", "monster-animations.json"]:
        manifest_path = ROOT / "assets/manifests" / manifest_name
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for binding in manifest.get("bindings") or []:
            if str(binding.get("slot") or "") != "attack":
                continue
            clip_id = str(binding.get("clipId") or binding.get("clip_id") or "")
            if clip_id and f'["{clip_id}"]' not in attack_timeline_data_text:
                err(f"registered attack clip has no authoritative timeline: {clip_id}")
