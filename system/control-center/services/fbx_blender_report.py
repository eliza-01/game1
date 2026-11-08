"""Shared Blender subprocess boundary used by Real Estate and Location Assets.

No DB writes, mutations or upload. Caller supplies a domain inspector script.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
import subprocess
import tempfile
from blender_runtime import blender_executable


def _blender_failure(diagnostic: str, exit_code: int) -> str:
    """Show an actionable Blender error instead of hiding it behind a generic label."""
    match = re.findall(
        r"^([A-Za-z_][A-Za-z_0-9.]*Error|Exception):\s*(.+)$",
        diagnostic, flags=re.MULTILINE,
    )
    if match:
        kind, message = match[-1]
        if kind in {"ModuleNotFoundError", "ImportError"}:
            return ("Blender publication helper could not be loaded (" + message.strip()
                    + "). Check that the latest project files are installed.")
        return message.strip()
    # A native crash or abrupt termination has no Python traceback.
    lines = [line.strip() for line in diagnostic.splitlines() if line.strip()
             and not line.lstrip().startswith(("File ", "^", "Traceback ", "Blender quit"))]
    last = lines[-1] if lines else "No diagnostic output from Blender"
    return f"Blender could not analyze the FBX (exit code {exit_code}). {last}"


def run_report(root: Path, script: str, arguments: tuple[Path | str, ...],
               *, report_path: Path, label: str, runner=None, executable=None) -> dict:
    """One Blender-to-JSON boundary shared across all FBX workflows.

    The injectable runner/executable preserve existing Real Estate test and
    publication contracts without replicating subprocess/error handling.
    """
    if runner is None:
        runner = subprocess.run
    if executable is None:
        executable = blender_executable
    cmd = [str(executable()), '--background', '--factory-startup',
           '--python-exit-code', '1', '--python',
           str(root / 'system/asset-manager' / script),
           '--', *(str(argument) for argument in arguments)]
    try:
        result = runner(cmd, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=240)
    except subprocess.TimeoutExpired as error:
        raise ValueError(f'{label}: Blender analysis timed out') from error
    if result.returncode or not report_path.is_file():
        diagnostic = (result.stderr or '') + '\n' + (result.stdout or '')
        if diagnostic.strip():
            detail = _blender_failure(diagnostic, result.returncode)[:600]
            raise ValueError(f'{label}: {detail}')
        if result.returncode:
            raise ValueError(f'{label}: Blender exited with status {result.returncode}')
        raise ValueError(f'{label}: Blender {script} finished without a JSON report. '
                         'Verify Blender installation and the FBX file.')
    try:
        return json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f'{label}: Blender returned an invalid JSON report') from error


def inspect_report(root: Path, script: str, source: Path, *, label: str) -> dict:
    source = source.expanduser().resolve()
    if not source.is_file() or source.suffix.casefold() != '.fbx':
        raise ValueError(f'{label}: choose an existing FBX file')
    with tempfile.TemporaryDirectory(prefix='game1-fbx-inspection-') as directory:
        output = Path(directory) / 'analysis.json'
        return run_report(root, script, (source, output), report_path=output, label=label)
