"""Non-mutating character animation discovery and explicit, checksum-guarded registration.

The snapshot does not write files, mutate SQLite, export registry or publish.
Published clips must enter the separate manual-reimport workflow.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from .common import ANIMATION_EXTENSIONS, MAX_SCAN_FILES, _clip_id, _now, classify_animation
from .documents import is_animation_source, read_document, document_digest
from .documents import document_path
from .package_files import rollback_files


class AnimationScanReviewMixin:
    def _review_files(self, character_id: str, folder: str) -> dict:
        character = self._character(character_id)  # Read-only SELECT; unlike _profile.
        root = Path(str(folder or "")).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("choose an existing animation folder")
        files = sorted((p.resolve() for p in root.rglob("*") if p.is_file()
                        and is_animation_source(p)
                        and not self._is_managed_animation_path(p.resolve())),
                       key=lambda p: p.as_posix().casefold())
        if len(files) > MAX_SCAN_FILES:
            raise ValueError(f"animation scan found more than {MAX_SCAN_FILES} files; choose a narrower folder")
        with self.connect() as connection:
            documents={(r['clip_id'],r['animation_sha256']):r['document_sha256'] for r in connection.execute('SELECT clip_id,animation_sha256,document_sha256 FROM animation_clip_documents')}
            existing = {row["id"]: dict(row) for row in connection.execute(
                "SELECT id,asset_id,sha256,published_sha256 FROM animation_clips WHERE character_id=?",
                (character_id,))}
        seen = {}
        items, unassigned = [], []
        for path in files:
            binding = classify_animation(path, character_id)
            if binding is None:
                unassigned.append({"filename": path.name, "path": str(path), "reason": "имя не соответствует семантическому слоту"})
                continue
            coordinate = (binding["scope"], binding["weaponSet"], binding["slot"], int(binding["variant"]))
            if coordinate in seen:
                raise ValueError(f"animation scan is ambiguous: {seen[coordinate]} and {path.name} map to the same slot")
            seen[coordinate] = path.name
            clip_id = _clip_id(character_id, *coordinate)
            sha = self._sha256(path)
            document=read_document(path,None if path.name.endswith('.animation.json') else sha)
            doc_sha=document_digest(path) if document else ''
            old = existing.get(clip_id)
            if not old:
                status = "NEW"
            elif old["sha256"] == sha:
                status = "UNCHANGED"
            elif old.get("asset_id"):
                status = "REPLACE_REQUIRED"
            else:
                status = "LOCAL_UPDATE"
            document_key='procedural' if path.name.endswith('.animation.json') else sha
            if status=='UNCHANGED' and doc_sha and documents.get((clip_id,document_key))!=doc_sha:status='DOCUMENT_UPDATE'
            items.append({"path": str(path), "filename": path.name, "sha256": sha,
                          "documentSha256":doc_sha,
                          "clipId": clip_id, "assetId": str((old or {}).get("asset_id") or ""),
                          "status": status, "selectable": status in ("NEW", "LOCAL_UPDATE", "DOCUMENT_UPDATE"),
                          **binding})
        return {"characterId": character_id, "rootPath": str(root),
                "filesScanned": len(files), "items": items, "unassigned": unassigned,
                "recognized": len(items), "characterVisualMode": str(character.get("visual_mode") or "model")}

    def preview_folder(self, character_id: str, folder: str) -> dict:
        return self._review_files(character_id, folder)

    def register_selected(self, character_id: str, folder: str, selections: list) -> dict:
        if not isinstance(selections, list) or len(selections) > MAX_SCAN_FILES:
            raise ValueError("invalid animation selection")
        review = self._review_files(character_id, folder)
        valid = {row["path"]: row for row in review["items"] if row["selectable"]}
        requested = []
        for value in selections:
            if not isinstance(value, dict):
                raise ValueError("invalid animation selection")
            path, sha = str(value.get("path") or ""), str(value.get("sha256") or "")
            row = valid.get(path)
            if row is None or not sha or row["sha256"] != sha or str(value.get('documentSha256') or '')!=row.get('documentSha256','') or any(x["path"] == path for x in requested):
                raise ValueError("animation selection changed since preview; scan again")
            requested.append(row)
        character = self._character(character_id)
        now = _now()
        items = []
        with tempfile.TemporaryDirectory(prefix='game1-animation-input-') as directory:
            staged=[];destinations=[]
            for index,row in enumerate(requested):
                source=Path(row['path']);copy=Path(directory)/str(index)/source.name
                copy.parent.mkdir();shutil.copy2(source,copy)
                if document_path(source).is_file() and document_path(source)!=source:
                    shutil.copy2(document_path(source),document_path(copy))
                if self._sha256(copy)!=row['sha256'] or document_digest(copy)!=row.get('documentSha256',''):
                    raise ValueError('animation file changed during registration; scan again')
                binding={key:row[key] for key in ('scope','weaponSet','slot','variant','looped','priority')}
                suffix='.animation.json' if copy.name.endswith('.animation.json') else copy.suffix.lower()
                canonical,_=self._canonical_paths(character,binding,suffix)
                destinations.extend([canonical,document_path(canonical)])
                staged.append((copy,binding))
            with rollback_files(destinations),self.connect() as connection:
                for source,binding in staged:
                    outcome,item=self._register_source(connection,character,source,binding,now)
                    items.append({'outcome':outcome,**item})
                if items:
                    connection.execute('UPDATE animation_profiles SET scan_root=?,updated_at=? WHERE character_id=?',
                                       (review['rootPath'],now,character_id))
        if items:
            self.export()
        return {"characterId": character_id, "registered": items, "count": len(items)}

    def stage_manual_replacement(self, clip_id: str, source_path: str) -> dict:
        clip = self.clip(clip_id)
        if not str(clip.get("asset_id") or ""):
            raise ValueError("Replace is only for already published animations")
        source = Path(str(source_path or "")).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in ANIMATION_EXTENSIONS or self._is_managed_animation_path(source):
            raise ValueError("choose an external .rbxm/.rbxmx animation file")
        character = self._character(clip["character_id"])
        binding = {"scope": clip["scope"], "weaponSet": clip["weapon_set"],
                   "slot": clip["slot"], "variant": int(clip["variant"]),
                   "looped": bool(clip["looped"]), "priority": clip["priority"]}
        with self.connect() as connection:
            outcome, item = self._register_source(connection, character, source, binding, _now())
        if outcome != "unchanged":
            self.export()
        result = self.clip(clip_id)
        return {"outcome": outcome, "clipId": clip_id, "assetId": result["asset_id"],
                "status": result["status"], "item": item}
