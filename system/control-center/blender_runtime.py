"""Blender executable discovery shared by authoring adapters."""
from pathlib import Path
import os
import shutil

def _blender_candidates() -> list[Path]:
    values: list[Path] = []
    explicit = str(os.environ.get("blender_exe") or os.environ.get("BLENDER_EXE") or "").strip()
    if explicit:
        values.append(Path(explicit).expanduser())

    resolved = shutil.which("blender")
    if resolved:
        values.append(Path(resolved))

    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    foundation = program_files / "Blender Foundation"
    if foundation.is_dir():
        for directory in sorted(foundation.glob("Blender *"), reverse=True):
            values.append(directory / "blender.exe")

    seen = set()
    result = []
    for value in values:
        try:
            key = str(value.resolve()).casefold()
        except Exception:
            key = str(value).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def blender_executable() -> Path:
    for candidate in _blender_candidates():
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(
        "blender was not found. install blender or set BLENDER_EXE in .env.local before registering an FBX."
    )



