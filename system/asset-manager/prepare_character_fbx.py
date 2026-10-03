"""compatibility entry point: game1 prepared character FBX preserves source bytes."""

import json
import shutil
import sys
from pathlib import Path


def main(source: Path, output: Path, report_path: Path):
    source = source.resolve()
    output = output.resolve()
    report_path = report_path.resolve()
    if not source.is_file() or source.suffix.lower() != ".fbx":
        raise RuntimeError("character preparation requires an FBX file")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    report_path.write_text(
        json.dumps({"schemaVersion": 2, "mode": "preserve-source-bytes"}, indent=2) + "\n",
        encoding="utf-8",
    )


args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 3:
    raise RuntimeError("usage: prepare_character_fbx.py -- input.fbx output.fbx report.json")
source, output, report = map(Path, args)
main(source, output, report)
