from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile


class CharacterAnalysisError(RuntimeError):
    pass


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
    raise CharacterAnalysisError(
        "blender was not found. install blender or set BLENDER_EXE in .env.local before registering an FBX."
    )



def prepare_character_fbx(project_root: Path, source: Path, output: Path) -> dict:
    source = source.resolve()
    output = output.resolve()
    if not source.is_file() or source.suffix.lower() != ".fbx":
        raise CharacterAnalysisError("character preparation requires an FBX file")

    # The published FBX is already authored in the correct Roblox orientation.
    # Registration must not rebake rotation/scale: Studio builds the stable
    # character wrapper and canonical RootPart without touching mesh transforms.
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    return {
        "schemaVersion": 2,
        "mode": "preserve-source-bytes",
    }

def analyze_character_fbx(project_root: Path, source: Path) -> dict:
    source = source.resolve()
    if not source.is_file() or source.suffix.lower() != ".fbx":
        raise CharacterAnalysisError("character registration requires an FBX file")

    analyzer = project_root / "system" / "asset-manager" / "analyze_character_fbx.py"
    if not analyzer.is_file():
        raise CharacterAnalysisError(f"character analyzer is missing: {analyzer}")

    blender = blender_executable()
    with tempfile.TemporaryDirectory(prefix="game1-character-analysis-") as tmp:
        output = Path(tmp) / "analysis.json"
        command = [
            str(blender),
            "--background",
            "--factory-startup",
            "--python",
            str(analyzer),
            "--",
            str(source),
            str(output),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if completed.returncode != 0 or not output.is_file():
            detail = (completed.stderr or completed.stdout or "blender analysis failed").strip()
            raise CharacterAnalysisError(detail[-5000:])
        value = json.loads(output.read_text(encoding="utf-8"))

    if not isinstance(value, dict):
        raise CharacterAnalysisError("character analyzer returned invalid output")
    if int(value.get("boneCount") or 0) <= 0:
        raise CharacterAnalysisError("character FBX has no bones")
    if int(value.get("meshCount") or 0) <= 0:
        raise CharacterAnalysisError("character FBX has no mesh")
    if int(value.get("skinnedMeshCount") or 0) <= 0:
        raise CharacterAnalysisError("character FBX mesh is not skinned to its armature")
    return value
