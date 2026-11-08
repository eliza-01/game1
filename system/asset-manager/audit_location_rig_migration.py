"""Read-only full Location Asset migration inventory, never publishes or edits Place.

Usage: python system/asset-manager/audit_location_rig_migration.py ROOT OUT.json
All slugs are reported, including incomplete registrations and missing sources.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys


def audit(root: Path) -> dict:
    root = root.resolve()
    db_path = root / '.control-center/game1.db'
    if not db_path.is_file():
        raise ValueError('Location Asset registry database not found')
    with sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        assets = [dict(row) for row in db.execute(
            'SELECT slug,name_en,category,model_path,model_sha256,model_asset_id,'
            'model_published_sha256 FROM location_assets ORDER BY slug')]
        publications = [dict(row) for row in db.execute(
            "SELECT asset_slug,kind,asset_id,sha256 FROM location_asset_publications "
            "WHERE kind='model' ORDER BY id")]
        has_manifest = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                  "AND name='location_asset_rig_manifests'").fetchone() is not None
        manifests = ([dict(row) for row in db.execute(
            'SELECT asset_slug,model_asset_id,manifest_json FROM location_asset_rig_manifests')]
                     if has_manifest else [])
    versions = {}
    for row in publications:
        versions.setdefault(row['asset_slug'], []).append(row['asset_id'])
    current_manifests = {(row['asset_slug'], row['model_asset_id']):
                         json.loads(row['manifest_json']) for row in manifests}
    result = []
    for row in assets:
        source = root / (row['model_path'] or '')
        current = str(row['model_asset_id'] or '')
        manifest = current_manifests.get((row['slug'], current))
        source_present = source.is_file() if row['model_path'] else False
        if not source_present:
            status = 'source_missing'
        elif not manifest:
            analysis_path = root / 'assets/manifests/location-assets-fbx' / (row['slug'] + '.json')
            analysis = None
            if analysis_path.is_file():
                try:
                    record = json.loads(analysis_path.read_text(encoding='utf-8'))
                    if record.get('sourceSha256') == row['model_sha256']:
                        analysis = record.get('analysis')
                except (OSError, UnicodeError, ValueError):
                    pass
            meshes = analysis.get('meshes') if isinstance(analysis, dict) else None
            inspected_static = (isinstance(meshes, list) and bool(meshes)
                and not analysis.get('unassignedArmatures')
                and not any(part.get('bones') or str(part.get('name','')).casefold() == 'rig_carrier'
                            for part in meshes))
            if inspected_static and current and row['model_sha256'] == row['model_published_sha256']:
                status = 'legacy_static__studio_validation_required'
            elif inspected_static:
                status = 'static_fbx__publication_if_model_changed'
            elif isinstance(meshes, list) and any(part.get('bones') for part in meshes):
                status = 'skinned_needs_carrier_and_publication'
            else:
                status = 'fbx_inspection_required'
        elif manifest.get('schemaVersion') != 2:
            status = 'invalid_manifest'
        else:
            status = 'publication_v2_recorded__studio_validation_required'
        result.append({
            'slug':row['slug'], 'category':row['category'], 'status':status,
            'modelAssetId':current,'previousModelIds':versions.get(row['slug'],[]),
            'sourcePath':row['model_path'], 'sourcePresent':source_present,
            'manifestVersion':manifest.get('schemaVersion') if manifest else None,
            'rigKind':manifest.get('rigKind') if manifest else ('static' if status.startswith(('legacy_static','static_fbx')) else None),
            'structuralHash':manifest.get('structuralHash') if manifest else None,
        })
    return {'schemaVersion':2,'scope':'location_assets_only','readOnly':True,
            'totalRegistered':len(result),'sourceAvailable':sum(r['sourcePresent'] for r in result),
            'publishedCarrierManifests':sum(r['manifestVersion']==2 and r['rigKind']!='static' for r in result),
            'publishedStaticManifests':sum(r['manifestVersion']==2 and r['rigKind']=='static' for r in result),
            'inspectedLegacyStatic':sum(r['status']=='legacy_static__studio_validation_required' for r in result),
            'items':result,
            'blockers':['Requires actual authored FBX, Blender, Open Cloud and live Studio',
                        'No Place mutations or publication occur during this audit']}


def main(argv):
    if len(argv) != 2:
        raise SystemExit('Usage: audit_location_rig_migration.py PROJECT_ROOT REPORT.json')
    report = audit(Path(argv[0]))
    destination = Path(argv[1]).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Location Assets: {report['totalRegistered']} · source available: "
          f"{report['sourceAvailable']} · rig v2 manifests: {report['publishedCarrierManifests']}")


if __name__ == '__main__':
    main(sys.argv[1:])
