"""Blender adapter for Real Estate FBX inspection and rig-preserving preparation."""
from __future__ import annotations

import json
import re
from pathlib import Path
import subprocess
import tempfile

from character_analysis import blender_executable
from .contracts import validate_analysis, present_parts


def _blender_failure(diagnostic: str, exit_code: int) -> str:
    """Show an actionable Blender error instead of hiding it behind a generic label."""
    match = re.findall(
        r"^([A-Za-z_][A-Za-z_0-9.]*Error|Exception):\s*(.+)$",
        diagnostic, flags=re.MULTILINE,
    )
    if match:
        kind, message = match[-1]
        if kind in {"ModuleNotFoundError", "ImportError"}:
            return ("Real Estate Blender helper could not be loaded (" + message.strip()
                    + "). Check that the latest project files are installed.")
        return message.strip()
    # A native crash or abrupt termination has no Python traceback.
    lines = [line.strip() for line in diagnostic.splitlines() if line.strip()
             and not line.lstrip().startswith(("File ", "^", "Traceback ", "Blender quit"))]
    last = lines[-1] if lines else "No diagnostic output from Blender"
    return f"Blender could not analyze the FBX (exit code {exit_code}). {last}"


def _run(project_root: Path, script: str, arguments: tuple[Path | str, ...], *, report_path: Path) -> dict:
    """Run Blender with its CLI arguments and an explicit JSON report destination.

    Rig inspection ends with the part name (house/door), not the report filename.
    Never infer the report path from the last CLI argument.
    """
    args = [str(blender_executable()), '--background', '--factory-startup',
            '--python-exit-code', '1',
            '--python', str(project_root / 'system/asset-manager' / script),
            '--', *(str(argument) for argument in arguments)]
    run = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=240)
    if run.returncode:
        diagnostic = (run.stderr or '') + '\n' + (run.stdout or '')
        raise ValueError('Real Estate FBX: ' + _blender_failure(diagnostic, run.returncode)[:500])
    if not report_path.is_file():
        diagnostic = (run.stderr or '') + '\n' + (run.stdout or '')
        raise ValueError('Real Estate FBX: ' + _blender_failure(diagnostic, run.returncode)[:500]
                         if diagnostic.strip() else
                         f'Real Estate FBX: Blender {script} finished without a JSON report. '
                         'Verify Blender installation and the FBX file.')
    try:
        return json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Real Estate FBX: Blender produced an invalid analysis report') from exc


def inspect(root: Path, source: Path) -> dict:
    source = source.resolve()
    if source.suffix.lower() != '.fbx' or not source.is_file():
        raise ValueError('choose a valid Real Estate FBX')
    with tempfile.TemporaryDirectory(prefix='game1-real-estate-inspect-') as temp:
        report_path = Path(temp) / 'analysis.json'
        analysis = _run(root, 'analyze_real_estate_fbx.py', (source, report_path),
                        report_path=report_path)
    return validate_analysis(analysis)


def inspect_selected(root: Path, source: Path, part: str) -> dict:
    """Inspect a named mesh from either a single-mesh or a complete house FBX."""
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
