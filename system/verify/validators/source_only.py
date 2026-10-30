"""M52/M53 source-only storage invariants used by the one-command verifier.

This validation is read-only: it never runs migrations, edits manifests, or
creates database files. It reports diagnostics through an injected sink so the
CLI owns formatting and failure policy.
"""

import json
from pathlib import Path
from typing import Callable


def check_source_only_contract(
    root: Path,
    report_error: Callable[[str], None],
    *,
    location_asset_store_text: str,
    deco_assets_js_text: str,
    host_agent_text: str,
    character_js_text: str,
    ui_html: str,
) -> None:
    """Check legacy M52/M53 contracts without changing files or databases."""
    location_asset_manifest_path = root / "assets/manifests/location-assets.json"
    # m52 Location Assets: source-only canonical storage. The one-off Location
    # Asset migration was retired by m53 after the project-wide source-only
    # migration became authoritative.
    for required in [
        "model_path TEXT NOT NULL DEFAULT ''",
        "texture_path TEXT NOT NULL DEFAULT ''",
        'self.root / "assets/source/location-assets"',
    ]:
        if required not in location_asset_store_text:
            report_error(f"m52 source-only LocationAssetStore missing {required}")
    for forbidden in [
        "assets/prepared/location-assets",
        "model_source_path",
        "model_prepared_path",
        "texture_source_path",
        "texture_prepared_path",
    ]:
        if forbidden in location_asset_store_text:
            report_error(f"m52 active LocationAssetStore still contains legacy storage field/path {forbidden}")

    if location_asset_manifest_path.is_file():
        location_asset_manifest = json.loads(location_asset_manifest_path.read_text(encoding="utf-8"))
        if location_asset_manifest.get("schemaVersion") != 4:
            report_error("m52 Location Asset manifest schema must be 4")
        for row in location_asset_manifest.get("items") or []:
            if not str(row.get("model_path") or "").startswith("assets/source/location-assets/"):
                report_error(f"m52 Location Asset model path is not canonical source-only: {row.get('slug')}")
            if not str(row.get("texture_reference_slug") or ""):
                # Atlas Registry owns canonical shared sources independently of the
                # Location Asset model folder (m125+). Both live under assets/source.
                expected_prefix = ("assets/source/texture-atlases/" if row.get("atlasVariantId")
                                   else "assets/source/location-assets/")
                if not str(row.get("texture_path") or "").startswith(expected_prefix):
                    report_error(f"m52 owned Location Asset texture path is not canonical source-only: {row.get('slug')}")
            for legacy_field in ("model_source_path", "model_prepared_path", "texture_source_path", "texture_prepared_path"):
                if legacy_field in row:
                    report_error(f"m52 manifest still exports legacy field {legacy_field}: {row.get('slug')}")

    if "row.texture_path" not in deco_assets_js_text or "row.texture_source_path" in deco_assets_js_text:
        report_error("m52 Location Assets UI must use source-only texture_path")

    # m53 project-wide source-only storage. Active asset bytes live only in
    # assets/source. Compatibility DB columns may remain for old query shapes,
    # but both aliases must resolve to the same canonical source path and no active
    # subsystem may recreate assets/prepared.
    source_only_module = root / "system/control-center/source_only_assets.py"
    source_only_text = source_only_module.read_text(encoding="utf-8") if source_only_module.is_file() else ""
    if not source_only_module.is_file():
        report_error("m53 project-wide source-only migration module is missing")
    if (root / "system/control-center/location_asset_source_only_migration.py").exists():
        report_error("m53 obsolete Location Asset-only source migration must be removed")
    for required in [
        "def migrate_source_only_assets",
        '"game1-source-only-assets-v1"',
        '"assets/prepared/"',
        '"assets/source/"',
        '"prepared-wins"',
        '"source-wins"',
        '"prepared-before"',
    ]:
        if required not in source_only_text:
            report_error(f"m53 source-only migration contract missing {required}")
    if 'migrate_source_only_assets(ROOT, ROOT / ".control-center" / "game1.db")' not in host_agent_text:
        report_error("m53 Control Center startup does not run source-only migration before stores")
    migrate_text = (root / "system/control-center/migrate.py").read_text(encoding="utf-8")
    if 'migrate_source_only_assets(ROOT, ROOT / ".control-center" / "game1.db")' not in migrate_text:
        report_error("m53 migrate.py does not run project-wide source-only migration")

    legacy_prepared_root = root / "assets/prepared"
    if legacy_prepared_root.exists():
        legacy_files = [path for path in legacy_prepared_root.rglob("*") if path.is_file()]
        if legacy_files:
            report_error(f"m53 source-only migration incomplete: assets/prepared still has {len(legacy_files)} file(s)")
        else:
            report_error("m53 source-only migration incomplete: empty assets/prepared tree still exists")

    active_manifest_stale = []
    for manifest_path in (root / "assets/manifests").glob("*.json"):
        if "assets/prepared/" in manifest_path.read_text(encoding="utf-8", errors="replace"):
            active_manifest_stale.append(manifest_path.name)
    if active_manifest_stale:
        report_error("m53 manifests still reference assets/prepared: " + ", ".join(sorted(active_manifest_stale)))

    for active_store in [
        root / "system/control-center/character_store.py",
        root / "system/control-center/character_core/identity.py",
        root / "system/control-center/animation_core/storage.py",
        root / "system/control-center/weapon_store.py",
        root / "system/control-center/monster_store.py",
        root / "system/control-center/monster_animation_store.py",
    ]:
        active_text = active_store.read_text(encoding="utf-8")
        if 'self.root / "assets/prepared' in active_text or 'self.root / "assets" / "prepared"' in active_text:
            report_error(f"m53 active store can still create assets/prepared: {active_store.relative_to(root)}")

    if "<b>prepared</b>" in character_js_text or "source/prepared copies" in ui_html:
        report_error("m53 Asset Manager still exposes the removed Source/Prepared dual-storage UI")

    # Validate compatibility aliases in the live SQLite DB. They remain only so old
    # query shapes keep working; both values must point at the exact same assets/source file.
    import sqlite3 as _sqlite3_m53
    _db_m53 = root / ".control-center/game1.db"
    if _db_m53.is_file():
        _con_m53 = _sqlite3_m53.connect(_db_m53)
        _con_m53.row_factory = _sqlite3_m53.Row
        _pairs_m53 = [
            ("characters", "source_path", "prepared_path"),
            ("animation_clips", "source_path", "prepared_path"),
            ("weapons", "model_source_path", "model_prepared_path"),
            ("weapon_textures", "source_path", "prepared_path"),
            ("monsters", "model_source_path", "model_prepared_path"),
            ("monster_textures", "source_path", "prepared_path"),
            ("monster_animation_clips", "source_path", "prepared_path"),
        ]
        _tables_m53 = {str(row[0]) for row in _con_m53.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for _table, _source_col, _prepared_col in _pairs_m53:
            if _table not in _tables_m53:
                continue
            _cols = {str(row[1]) for row in _con_m53.execute(f"PRAGMA table_info({_table})")}
            if not {_source_col, _prepared_col}.issubset(_cols):
                continue
            for _row in _con_m53.execute(f"SELECT {_source_col},{_prepared_col} FROM {_table}"):
                _source_value = str(_row[0] or "").replace("\\", "/")
                _prepared_value = str(_row[1] or "").replace("\\", "/")
                if _source_value != _prepared_value:
                    report_error(f"m53 {_table} still has split Source/Prepared paths")
                    break
                if _source_value and not _source_value.startswith("assets/source/"):
                    report_error(f"m53 {_table} canonical path is outside assets/source: {_source_value}")
                    break
        _con_m53.close()
