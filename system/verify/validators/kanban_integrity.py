"""Read-only Kanban contract gate; reuse the production KanbanStore SHA checks."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def check_kanban_integrity(root: Path, err) -> None:
    path = Path(root) / 'system' / 'control-center' / 'kanban_store.py'
    try:
        spec = importlib.util.spec_from_file_location('game1_kanban_verify_store', path)
        if spec is None or spec.loader is None:
            raise RuntimeError('kanban_store.py could not be loaded')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        store = module.KanbanStore(root)
        cards = store.list_cards()['cards']
        if not cards:
            raise ValueError('no Kanban cards found')
    except (OSError, ValueError, RuntimeError, TypeError) as problem:
        err(f'Kanban spec/card mismatch: {problem}')
