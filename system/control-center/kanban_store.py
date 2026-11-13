"""Git-backed development planning; independent from game state and SQLite."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

CARD_ID = re.compile(r"KBN-[0-9]{4}\Z")
STATUSES = frozenset({"PROPOSED", "READY", "IN_PROGRESS", "CODE_COMPLETE", "VALIDATING", "DONE", "BLOCKED", "ON_HOLD"})
TEST_STATUSES = frozenset({"NOT_RUN", "PASS", "FAIL", "BLOCKED"})
MAX_SPEC = 200_000


class KanbanError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_atomic(path: Path, data: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.kanban-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class KanbanStore:
    """One document and one card per ID; card revision protects every write.

    Sources are project-tracked JSON/Markdown. Local backups are outside Git.
    The API never accepts a path from a browser or creates a new card.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.folder = self.root / 'docs' / 'kanban'
        self.cards = self.folder / 'cards'
        self.specs = self.folder / 'specs'
        self.history = self.folder / 'history'
        self.backups = self.root / '.control-center' / 'backups' / 'kanban'
        self._lock = RLock()

    def _paths(self, identifier):
        if not isinstance(identifier, str) or CARD_ID.fullmatch(identifier) is None:
            raise KanbanError('invalid card ID')
        return self.cards / f'{identifier}.json', self.specs / f'{identifier}.md', self.history / f'{identifier}.jsonl'

    def _load(self, identifier):
        card_file, spec_file, _ = self._paths(identifier)
        if not card_file.is_file() or not spec_file.is_file():
            raise KanbanError('card not found', 404)
        try:
            card = json.loads(card_file.read_text(encoding='utf-8'))
            spec = spec_file.read_text(encoding='utf-8')
        except (OSError, UnicodeError, ValueError) as error:
            raise KanbanError(f'cannot load card: {error}', 500) from error
        if not isinstance(card, dict) or card.get('id') != identifier or card.get('schemaVersion') != 1:
            raise KanbanError('invalid card contract', 500)
        if card.get('specPath') != f'docs/kanban/specs/{identifier}.md':
            raise KanbanError('invalid documentation path', 500)
        if card.get('specSha256') != _digest(spec):
            raise KanbanError('documentation differs from card revision; reconcile Git changes first', 409)
        return card, spec

    def list_cards(self):
        with self._lock:
            results = []
            for path in sorted(self.cards.glob('KBN-????.json')):
                card, _ = self._load(path.stem)
                results.append(card)
            return {'schemaVersion': 1, 'cards': results}

    def detail(self, identifier):
        with self._lock:
            card, spec = self._load(identifier)
            return {'card': card, 'spec': spec}

    def history_for(self, identifier):
        with self._lock:
            self._load(identifier)
            _, _, path = self._paths(identifier)
            if not path.is_file():
                return {'events': []}
            lines = path.read_text(encoding='utf-8').splitlines()
            return {'events': [json.loads(line) for line in lines[-100:][::-1]]}

    def export(self):
        with self._lock:
            cards = self.list_cards()['cards']
            lines = ['# Eyesland — Development Kanban', '', 'Снимок текущего состояния (не заменяет спецификации).', '']
            for card in cards:
                checked = sum(task['done'] for task in card['tasks'])
                lines.extend([f"## {card['id']} · {card['title']}",
                              f"Статус: {card['status']} · Приоритет: {card['priority']} · Ответственный: {card['owner']}",
                              f"Документ: {card['specPath']} · Ревизия: {card['revision']} · Чек-лист: {checked}/{len(card['tasks'])}", ''])
                for task in card['tasks']:
                    lines.append(f"- [{'x' if task['done'] else ' '}] {task['title']}")
                for item in card['acceptance']:
                    lines.append(f"- Тест [{item['status']}]: {item['title']}" + (f" — {item.get('evidence','')}" if item.get('evidence') else ''))
                lines.append('')
            return {'markdown': '\n'.join(lines)}

    def create(self, payload):
        if not isinstance(payload, dict):
            raise KanbanError('expected JSON object')
        title = payload.get('title')
        domain = payload.get('domain', 'Tooling')
        owner = payload.get('owner', 'Owner + Codex')
        priority = payload.get('priority', 'P1')
        if not isinstance(title, str) or not 4 <= len(title.strip()) <= 160:
            raise KanbanError('title must contain 4–160 characters')
        if not isinstance(domain, str) or not 1 <= len(domain) <= 64 or not re.fullmatch(r'[\w +–-]+', domain):
            raise KanbanError('invalid domain')
        if not isinstance(owner, str) or not 1 <= len(owner) <= 80:
            raise KanbanError('invalid owner')
        if not isinstance(priority, str) or priority not in ('P0', 'P1', 'P2', 'P3'):
            raise KanbanError('invalid priority')
        with self._lock:
            existing = self.list_cards()['cards']
            number = max((int(x['id'][4:]) for x in existing), default=0) + 1
            if number > 9999:
                raise KanbanError('card ID namespace exhausted')
            identifier = f'KBN-{number:04d}'
            card_file, spec_file, _ = self._paths(identifier)
            if card_file.exists() or spec_file.exists():
                raise KanbanError('card ID collision; refresh and retry', 409)
            doc = (f'# {identifier} — {title.strip()}\n\n'
                   '**Статус:** PROPOSED. Контракт не утверждён.\n\n'
                   '## Цель и границы\n\nОписать назначение механики и то, чего она не меняет.\n\n'
                   '## Архитектура и поведение\n\nОписать существующий код, предлагаемое изменение, входы/выходы, инварианты.\n\n'
                   '## Порядок реализации\n\nРасписать этапы и зависимости до перехода READY.\n\n'
                   '## Проверки и критерии приёмки\n\nУказать Studio, устройство, логи, регрессионные тесты.\n\n'
                   '## Миграция и откат\n\nНазначить резервные копии и порядок возврата.\n')
            card = {'schemaVersion': 1, 'id': identifier, 'title': title.strip(),
                    'domain': domain, 'status': 'PROPOSED', 'priority': priority, 'owner': owner,
                    'specPath': f'docs/kanban/specs/{identifier}.md', 'specSha256': _digest(doc),
                    'dependsOn': [], 'revision': 1,
                    'updatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    'tasks': [{'id': f'{identifier}-T01', 'title': 'Составить и согласовать план реализации', 'done': False}],
                    'acceptance': [{'id': f'{identifier}-A01', 'title': 'Пройти согласованные проверки',
                                    'status': 'NOT_RUN', 'evidence': ''}]}
            try:
                _write_atomic(spec_file, doc)
                _write_atomic(card_file, json.dumps(card, ensure_ascii=False, indent=2) + '\n')
            except Exception:
                card_file.unlink(missing_ok=True)
                spec_file.unlink(missing_ok=True)
                raise
            return {'card': card, 'spec': doc}

    def update(self, identifier, payload):
        if not isinstance(payload, dict):
            raise KanbanError('expected JSON object')
        with self._lock:
            card, spec = self._load(identifier)
            expected = payload.get('expectedRevision')
            if type(expected) is not int or expected != card['revision']:
                raise KanbanError(f"stale revision; current is {card['revision']}", 409)
            action = payload.get('action')
            if card['status'] == 'DONE' and action != 'status':
                raise KanbanError('reopen DONE card before changing its tasks, tests or contract', 409)
            new_spec = spec
            previous = json.dumps(card, ensure_ascii=False, indent=2) + '\n'
            updated = json.loads(previous)
            detail = ''
            if action in ('task-add', 'acceptance-add'):
                title = payload.get('title')
                if not isinstance(title, str) or not 4 <= len(title.strip()) <= 300:
                    raise KanbanError('item title must contain 4–300 characters')
                is_task = action == 'task-add'
                items = updated['tasks' if is_task else 'acceptance']
                suffix = 'T' if is_task else 'A'
                ordinal = max((int(x['id'].rsplit('-', 1)[-1][1:]) for x in items), default=0) + 1
                item_id = f'{identifier}-{suffix}{ordinal:02d}'
                entry = {'id': item_id, 'title': title.strip()}
                entry.update({'done': False} if is_task else {'status': 'NOT_RUN', 'evidence': ''})
                items.append(entry)
                detail = f'added {item_id}'
            elif action == 'item-title':
                title = payload.get('title')
                if not isinstance(title, str) or not 4 <= len(title.strip()) <= 300:
                    raise KanbanError('item title must contain 4–300 characters')
                item = next((x for x in updated['tasks'] + updated['acceptance'] if x['id'] == payload.get('itemId')), None)
                if item is None:
                    raise KanbanError('item not found')
                if updated['status'] == 'DONE':
                    raise KanbanError('reopen a DONE card before editing requirements', 409)
                item['title'] = title.strip()
                detail = f'edited title {item["id"]}'
            elif action == 'task':
                if type(payload.get('done')) is not bool:
                    raise KanbanError('done must be a boolean')
                task = next((x for x in updated['tasks'] if x['id'] == payload.get('itemId')), None)
                if task is None:
                    raise KanbanError('task not found')
                task['done'] = payload['done']
                detail = f"{task['id']}: {task['done']}"
            elif action == 'acceptance':
                test = next((x for x in updated['acceptance'] if x['id'] == payload.get('itemId')), None)
                if test is None or not isinstance(payload.get('status'), str) or payload['status'] not in TEST_STATUSES:
                    raise KanbanError('invalid test or test status')
                evidence = payload.get('evidence', '')
                if not isinstance(evidence, str) or len(evidence) > 2000:
                    raise KanbanError('evidence must be text up to 2000 chars')
                if payload['status'] == 'PASS' and not evidence.strip():
                    raise KanbanError('PASS requires concrete verification evidence')
                test['status'] = payload['status']
                test['evidence'] = evidence.strip()
                detail = f"{test['id']}: {test['status']}"
            elif action == 'status':
                status = payload.get('status')
                if not isinstance(status, str) or status not in STATUSES:
                    raise KanbanError('invalid status')
                if status == 'DONE' and (not updated['tasks'] or not updated['acceptance'] or not all(t['done'] for t in updated['tasks']) or
                                          not all(t['status'] == 'PASS' and t.get('evidence') for t in updated['acceptance'])):
                    raise KanbanError('DONE requires completed tasks and verified acceptance evidence')
                if status == 'DONE':
                    outstanding = [dep for dep in updated.get('dependsOn', []) if self._load(dep)[0]['status'] != 'DONE']
                    if outstanding:
                        raise KanbanError('DONE requires completed dependencies: ' + ', '.join(outstanding))
                if status == 'READY' and not spec.strip():
                    raise KanbanError('READY requires documentation')
                updated['status'] = status
                detail = f"status: {card['status']} -> {status}"
            elif action == 'spec':
                new_spec = payload.get('spec')
                reason = payload.get('reason')
                if not isinstance(new_spec, str) or not 0 < len(new_spec.encode('utf-8')) <= MAX_SPEC:
                    raise KanbanError('documentation must be 1–200000 UTF-8 bytes')
                if not isinstance(reason, str) or len(reason.strip()) < 8 or len(reason) > 1000:
                    raise KanbanError('documentation change requires a reason of 8–1000 characters')
                if card['status'] not in ('PROPOSED', 'ON_HOLD') and payload.get('confirmPolicyChange') is not True:
                    raise KanbanError('approved/in-progress contract requires explicit confirmation', 409)
                updated['specSha256'] = _digest(new_spec)
                detail = f'documentation: {reason.strip()}'
            else:
                raise KanbanError('unknown action')
            if updated == card and new_spec == spec:
                return {'card': card, 'spec': spec}
            updated['revision'] += 1
            updated['updatedAt'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            now = datetime.now(timezone.utc)
            event = {'revision': updated['revision'], 'time': now.isoformat(timespec='seconds'),
                     'action': action, 'detail': detail, 'beforeSha256': _digest(previous),
                     'afterSha256': _digest(json.dumps(updated, ensure_ascii=False, sort_keys=True))}
            card_file, spec_file, history_file = self._paths(identifier)
            backup_dir = self.backups / identifier / f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-r{card['revision']}"
            backup_dir.mkdir(parents=True, exist_ok=False)
            shutil.copy2(card_file, backup_dir / card_file.name)
            shutil.copy2(spec_file, backup_dir / spec_file.name)
            if history_file.is_file():
                shutil.copy2(history_file, backup_dir / history_file.name)
            old_history = history_file.read_text(encoding='utf-8') if history_file.is_file() else ''
            try:
                if new_spec != spec:
                    _write_atomic(spec_file, new_spec)
                _write_atomic(card_file, json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
                _write_atomic(history_file, old_history + json.dumps(event, ensure_ascii=False) + '\n')
            except Exception:
                shutil.copy2(backup_dir / card_file.name, card_file)
                shutil.copy2(backup_dir / spec_file.name, spec_file)
                if (backup_dir / history_file.name).is_file():
                    shutil.copy2(backup_dir / history_file.name, history_file)
                else:
                    history_file.unlink(missing_ok=True)
                raise
            return {'card': updated, 'spec': new_spec}
