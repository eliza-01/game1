"""Temporary model publication staging; no persistence or upload ownership."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import tempfile
from blender_runtime import blender_executable


@contextmanager
def staged_model(project_root: Path, source: Path):
    source = source.resolve()
    if not source.is_file() or source.suffix.lower() != '.fbx':
        raise ValueError('model publication requires an FBX file')
    with tempfile.TemporaryDirectory(prefix='game1-model-publication-') as directory:
        output = Path(directory) / source.name
        report = Path(directory) / 'report.json'
        script = project_root / 'system/asset-manager/prepare_model_publication_fbx.py'
        completed = subprocess.run(
            [str(blender_executable()), '--background', '--factory-startup',
             '--python-exit-code', '1', '--python', str(script), '--',
             str(source), str(output), str(report)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=240,
        )
        if completed.returncode or not output.is_file() or not report.is_file():
            detail = (completed.stderr or completed.stdout or 'missing output').strip()
            raise ValueError('Model publication preparation failed: ' + detail[-1500:])
        result = json.loads(report.read_text(encoding='utf-8'))
        if result.get('schemaVersion') != 1 or result.get('restTransformsChanged') is not False:
            raise ValueError('Invalid model publication preparation report')
        yield output
