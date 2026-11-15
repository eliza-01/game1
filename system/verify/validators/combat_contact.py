"""M358 active combat contracts. Historical M27–M50 OBB checks are superseded.

Validate explicit ownership boundaries instead of requiring retired Weapon Volume.
"""
from __future__ import annotations
from pathlib import Path
from typing import Callable


def check_combat_contact_contracts(root: Path, report_error: Callable[[str], None], *,
                                  damage_resolver_text: str, hitbox_implementation_text: str) -> None:
    def source(relative: str) -> str:
        path = root / relative
        return path.read_text(encoding='utf-8') if path.is_file() else ''

    attack = source('src/server/combat/AttackService.luau')
    client = source('src/client/combat/AttackController.luau')
    equip = source('src/server/weapon/WeaponEquipService.luau')
    legacy = source('src/shared/combat/WeaponAttackVolume.luau')
    query = source('src/server/combat/MeleeTargetQuery.luau')
    geometry = source('src/shared/combat/MeleeArcGeometry.luau')
    environment = source('src/server/combat/MeleeEnvironmentContact.luau')
    loadout = source('src/client/dev/TestLoadoutController.luau')
    bow = source('src/server/combat/BowHitscanService.luau')
    session = source('src/server/combat/AttackSessionStore.luau')
    config = source('src/shared/combat/AttackConfig.luau')

    for name, text in [('AttackService',attack), ('AttackController',client),
                       ('WeaponEquipService',equip), ('TestLoadoutController',loadout),
                       ('AttackDamageResolver',damage_resolver_text)]:
        if 'WeaponAttackVolume' in text or 'AttackWeaponPose' in text or 'WeaponAttackVolume.Build' in text:
            report_error(f'M358 {name} still depends on legacy weapon volume')

    if 'LEGACY · DEPRECATED · DO NOT USE' not in legacy:
        report_error('M358 weapon volume is not visibly deprecated')
    for required in ['scheduleMeleeArc', 'MeleeEnvironmentContact.Query',
                     'MeleeSampleInterval', 'AttackDamageResolver.Apply',
                     'CharacterAttackWindow.Resolve', 'Begin', 'MeleeAimUpdate']:
        if required not in attack:
            report_error(f'M358 server melee timeline/arc missing {required}')
    for required in ['MeleeAimUpdate', 'publishMeleeAim', 'aimPoseController.GetAimRay',
                     'CharacterAttackWindow.Resolve', 'BowAimUpdate']:
        if required not in client:
            report_error(f'M358 client aim-only / bow contract missing {required}')
    for required in ['MeleeTargetQuery.Find', 'query.hitTargets[model] = true',
                     'headshotTarget', 'aimedHead', 'RaycastAimRegions',
                     'HeadshotDamageMultiplier', 'DamageService.Apply']:
        if required not in damage_resolver_text:
            report_error(f'M358 damage resolver contract missing {required}')
    for required in ['QueryDamageablesInArc(', 'HitboxRuntimeFrames.Refresh',
                     'binding.bodyBoxes', 'binding.headBox', 'Damageable']:
        if required not in hitbox_implementation_text:
            report_error(f'M358 entity hitbox arc query missing {required}')
    for required in ['projectedHull', 'segmentContactInSector', 'pointInPolygon',
                     'minY', 'maxY', 'return table.freeze(MeleeArcGeometry)']:
        if required not in geometry:
            report_error(f'M358 pure arc geometry missing {required}')
    for required in ['IsUnobstructed', 'RespectCanCollide = true',
                     'QueryDamageablesInArc', 'root.CFrame.LookVector']:
        if required not in query:
            report_error(f'M358 server arc / wall checks missing {required}')
    for required in ['EnvironmentAssetService.ResolvePart', 'RealEstateEnvironmentTargets.ResolvePart',
                     'Workspace:Raycast']:
        if required not in environment:
            report_error(f'M358 directional bounce is missing {required}')
    for required in ['meleeArcAngleDegrees', 'MeleeArcAngle', 'purgeLegacyWeaponBox']:
        if required not in equip:
            report_error(f'M358 weapon equip angle migration missing {required}')
    for required in ['MELEE ARC: ON', 'LEGACY VOLUME · DO NOT USE',
                     'MeleeArcGeometry.Contact', 'HeadshotAimRay', 'CombatHitboxDebugData']:
        if required not in loadout:
            report_error(f'M358 Studio debug visualization missing {required}')
    for required in ['HeadshotDamageMultiplier = 2', 'MeleeDefaultArcAngle = 108',
                     'MeleeVerticalPadding = 1.5']:
        if required not in config:
            report_error(f'M358 melee default/config missing {required}')
    if 'sweepState' in session or 'EnsureSweep' in session:
        report_error('M358 retired client-sweep state still in active session store')
    if 'BowHitscanService' not in attack or 'BowHitscanService.Release' not in attack or 'Capture' not in bow:
        report_error('M358 bow release path changed or missing')
