"""Exact static FBX vertices for MNPC native import alignment (authoring only)."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from analyze_mnpc_lod_fbx import analyze

if __name__=='__main__':
    source,output=sys.argv[sys.argv.index('--')+1:]
    Path(output).write_text(json.dumps(analyze(Path(source),include_points=True),allow_nan=False),encoding='utf-8')
