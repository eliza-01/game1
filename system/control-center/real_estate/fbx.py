"""Blender adapter for Real Estate FBX inspection and rig-preserving preparation."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

from blender_runtime import blender_executable
from .contracts import validate_analysis, present_parts
from services.retired_col_mesh import strip_mesh_rows, retired
from services.fbx_blender_report import _blender_failure  # legacy import, shared implementation




def _run(project_root: Path, script: str, arguments: tuple[Path | str, ...], *, report_path: Path) -> dict:
    """Real Estate adapter for the shared Blender report executor."""
    from services.fbx_blender_report import run_report
    return run_report(project_root, script, arguments, report_path=report_path,
                      label='Real Estate FBX', runner=subprocess.run,
                      executable=blender_executable)


def inspect(root: Path, source: Path) -> dict:
    source = source.resolve()
    if source.suffix.lower() != '.fbx' or not source.is_file():
        raise ValueError('choose a valid Real Estate FBX')
    with tempfile.TemporaryDirectory(prefix='game1-real-estate-inspect-') as temp:
        report = Path(temp) / 'analysis.json'
        return validate_analysis(strip_mesh_rows(_run(root, 'analyze_real_estate_fbx.py',
                             (source, report), report_path=report)))


def inspect_selected(root: Path, source: Path, part: str) -> dict:
    """Inspect a named mesh from either a single-mesh or a complete house FBX."""
    if retired(part):
        raise ValueError('COL_* authoring mesh has been retired')
    with tempfile.TemporaryDirectory(prefix='game1-estate-mesh-inspect-') as temp:
        report = Path(temp) / 'analysis.json'
        return _run(root, 'analyze_real_estate_fbx.py',
                    (source, report, part, 'extract'), report_path=report)


def prepare_publication(root: Path, source: Path, target: Path, expected: dict, textures: dict, *, only_part: str | None = None) -> dict:
    """Export every present FBX Model Asset and verify each rig independently."""
    from .contracts import assert_rig_survived
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='game1-real-estate-publish-') as temp:
        config = Path(temp) / 'textures.json'
        config.write_text(json.dumps(textures), encoding='utf-8')
        report_path = Path(temp) / 'report.json'
        report = _run(root, 'prepare_real_estate_publication_fbx.py',
                      (source, target, config, report_path, only_part) if only_part else
                      (source, target, config, report_path), report_path=report_path)
    parts = (only_part,) if only_part else present_parts(expected)
    if report.get('schemaVersion') != 2 or set(report.get('rigAssets', {})) != set(parts):
        raise ValueError('Real Estate preparation did not produce the expected independent rigs')
    for part in parts:
        stage = target / f'{part}.fbx'
        if not stage.is_file():
            raise ValueError(f'missing staged {part} FBX')
        with tempfile.TemporaryDirectory(prefix=f'game1-{part}-inspect-') as temp:
            report_path = Path(temp) / 'analysis.json'
            actual = _run(root, 'analyze_real_estate_fbx.py', (stage, report_path, part),
                          report_path=report_path)
        assert_rig_survived(expected, actual, part)
    return report
