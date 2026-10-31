"""Convert native XML animation to Roblox binary using the project's Rojo tool.

The source and its sidecar keep their identity. Conversion is upload transport only.
No Studio interaction, asset upload or registry writes are owned here.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

def rojo_binary():
    configured=os.environ.get('GAME1_ROJO_BINARY','')
    if configured:
        if not Path(configured).is_file():raise ValueError('GAME1_ROJO_BINARY does not exist')
        return configured
    # Prefer the installed executable to a Rokit shim, including restricted shells.
    candidates=list((Path.home()/'.rokit/tool-storage/rojo-rbx/rojo').glob('*/rojo.exe'))
    if candidates:
        def version(path):
            try:return tuple(int(v) for v in path.parent.name.split('.'))
            except ValueError:return (0,)
        return str(max(candidates,key=version))
    found=shutil.which('rojo')
    if not found:raise ValueError('Rojo is required for native animation publication; set GAME1_ROJO_BINARY')
    return found

@contextmanager
def animation_upload_file(source):
    source=Path(source).resolve()
    if source.suffix.lower()=='.rbxm':
        yield source
        return
    if source.stat().st_size>20*1024*1024:raise ValueError('animation exceeds 20 MiB')
    raw=source.read_bytes()
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('XML declarations are not allowed')
    root=ET.fromstring(raw)
    sequences=root.findall('Item')
    if root.tag!='roblox' or len(sequences)!=1 or sequences[0].get('class')!='KeyframeSequence':
        raise ValueError('animation XML must contain one KeyframeSequence')
    if any(item.get('class') not in {'KeyframeSequence','Keyframe','Pose','KeyframeMarker'} for item in root.iter('Item')):
        raise ValueError('animation XML contains unsupported instances')
    with tempfile.TemporaryDirectory(prefix='game1-animation-native-') as directory:
        directory=Path(directory)
        project=directory/'animation.project.json'
        project.write_text(json.dumps({'name':'animation_native','tree':{'$path':str(source)}}),encoding='utf8')
        output=directory/'animation.rbxm'
        result=subprocess.run([rojo_binary(),'build',str(project),'-o',str(output)],capture_output=True,text=True,
                              encoding='utf8',errors='replace',timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode or not output.is_file():raise ValueError('native animation conversion failed: '+result.stderr[-1500:])
        if not output.read_bytes().startswith(b'<roblox!'):raise ValueError('Rojo did not produce binary RBXM')
        yield output
