"""Rollback canonical package files if the matching SQLite transaction fails."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile

@contextmanager
def rollback_files(paths):
    with tempfile.TemporaryDirectory(prefix='game1-animation-rollback-') as directory:
        previous=[]
        for index,path in enumerate(dict.fromkeys(paths)):
            path=Path(path)
            backup=Path(directory)/str(index) if path.is_file() else None
            if backup:shutil.copy2(path,backup)
            previous.append((path,backup))
        try:yield
        except Exception:
            for path,backup in reversed(previous):
                if backup:
                    path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(backup,path)
                elif path.is_file():path.unlink()
            raise
