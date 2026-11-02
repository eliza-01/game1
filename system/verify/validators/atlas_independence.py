"""M203 architectural invariants: no model may own an Image Asset."""
from pathlib import Path
from typing import Callable


def check_atlas_independence(root: Path, report_error: Callable[[str], None]) -> None:
    control = root / 'system/control-center'
    files = {
        'location': control / 'location_asset_store.py',
        'estate': control / 'real_estate/store.py',
        'registry': control / 'services/texture_atlas_registry.py',
        'upgrade': control / 'services/atlas_independence_migration.py',
        'retirement': control / 'services/shared_asset_retirement.py',
        'cli': control / 'migrate.py',
    }
    contents = {}
    for role, path in files.items():
        if not path.is_file():
            report_error(f'm203 atlas independence module missing: {path.relative_to(root)}')
            return
        contents[role] = path.read_text(encoding='utf-8')
    for role in ('location', 'estate'):
        source = contents[role]
        for forbidden in ('create_image_asset(', 'update_image_asset(',
                          'retained_textures.retain', 'RetainedTextures('):
            if forbidden in source:
                report_error(f'm203 {role} cannot own image publication: {forbidden}')
        if '.atlases.bind(' not in source or '.atlases.ensure_published(' not in source:
            report_error(f'm203 {role} must bind and publish through AtlasRegistry')
    for removed in ('legacy_atlas_migration.py', 'retained_textures.py'):
        if (control / 'services' / removed).exists():
            report_error(f'm203 obsolete atlas owner implementation remains: {removed}')
    if 'AtlasIndependenceMigration' not in contents['estate']:
        report_error('m203 Real Estate startup must run independent atlas migration')
    if 'RealEstateStore(ROOT, location_assets=location_assets)' not in contents['cli']:
        report_error('m203 migrate CLI must run cross-store atlas migration')
    for necessary in ('DROP TABLE IF EXISTS retained_shared_textures',
                      'ALTER TABLE location_assets DROP COLUMN',
                      'texture_atlas_bindings', 'assets/source/texture-atlases',
                      'before_m203_atlas_independence_'):
        if necessary not in contents['upgrade']:
            report_error(f'm203 migration missing guarantee: {necessary}')
    if 'retained_textures' in contents['retirement']:
        report_error('m203 deletion must not retain atlas owner records')
    if 'create_image_asset(' not in contents['registry']:
        report_error('m203 only AtlasRegistry may publish image assets')
