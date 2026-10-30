"""Isolated Blender adapter. No registration or publication policy."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from blender_runtime import blender_executable


def inspect_fbx(root, source, output=None):
    source=Path(source).resolve()
    if not source.is_file() or source.suffix.lower()!='.fbx':
        raise ValueError('choose an existing FBX file')
    script=Path(root)/'system/asset-manager/character_components_fbx.py'
    with tempfile.TemporaryDirectory(prefix='game1-parts-') as temp:
        report=Path(temp)/'report.json'
        args=[str(blender_executable()),'--background','--factory-startup','--python-exit-code','1',
              '--python',str(script),'--',str(source),str(report)]
        if output:
            Path(output).mkdir(parents=True,exist_ok=True);args.append(str(Path(output).resolve()))
        env=dict(os.environ,BLENDER_USER_RESOURCES=str(Path(temp)/'blender_resources'))
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180,env=env)
        if result.returncode or not report.is_file():
            raise ValueError((result.stderr or result.stdout or 'FBX analysis failed')[-4000:])
        return json.loads(report.read_text(encoding='utf8'))
