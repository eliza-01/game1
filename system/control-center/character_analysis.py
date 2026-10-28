from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import tempfile


class CharacterAnalysisError(RuntimeError):
    pass


from blender_runtime import blender_executable


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


def prepare_character_publication_fbx(project_root: Path, source: Path, output: Path) -> dict:
    """Build a temporary FBX for Roblox Open Cloud without moving rest bones.

    Roblox's automated Model FBX import does not expose Studio Importer's
    "Keep Zero Influence Bones" switch. The Blender preparation script therefore
    strengthens only weak skin influences, then this function re-analyzes the
    exported FBX so the caller can verify the skeleton before upload.
    """
    source = source.resolve()
    output = output.resolve()
    if not source.is_file() or source.suffix.lower() != ".fbx":
        raise CharacterAnalysisError("character publication preparation requires an FBX file")

    preparer = project_root / "system" / "asset-manager" / "prepare_character_publication_fbx.py"
    if not preparer.is_file():
        raise CharacterAnalysisError(f"character publication preparer is missing: {preparer}")

    blender = blender_executable()
    with tempfile.TemporaryDirectory(prefix="game1-character-publication-") as tmp:
        report_path = Path(tmp) / "publication-preparation.json"
        command = [
            str(blender),
            "--background",
            "--factory-startup",
            "--python",
            str(preparer),
            "--",
            str(source),
            str(output),
            str(report_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=240)
        if completed.returncode != 0 or not output.is_file() or not report_path.is_file():
            detail = (completed.stderr or completed.stdout or "blender publication preparation failed").strip()
            raise CharacterAnalysisError(detail[-5000:])
        preparation = json.loads(report_path.read_text(encoding="utf-8"))

    analysis = analyze_character_fbx(project_root, output)
    uncovered = [str(mesh.get('name') or 'mesh') for mesh in analysis.get('meshes', [])
                 if int(mesh.get('unweightedVertices') or 0) > 0]
    if uncovered:
        raise CharacterAnalysisError('publication FBX contains unweighted vertices: '
                                     + ', '.join(uncovered))
    over_limit = [
        str(mesh.get("name") or "mesh")
        for mesh in (analysis.get("meshes") or [])
        if int(mesh.get("maxInfluences") or 0) > 4
    ]
    if over_limit:
        raise CharacterAnalysisError(
            "publication FBX still has more than four bone influences: " + ", ".join(over_limit)
        )
    expected = {str(bone.get("name") or "") for bone in (analysis.get("bones") or [])}
    survived = {
        str(name)
        for mesh in (analysis.get("meshes") or [])
        for name in (mesh.get("influencedBones") or [])
    }
    missing = sorted(expected - survived)
    if missing:
        raise CharacterAnalysisError(
            "publication FBX contains bones without skin influence: " + ", ".join(missing)
        )
    return {"preparation": preparation, "analysis": analysis}
