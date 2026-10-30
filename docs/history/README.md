# Исторические документы game1 — каталог

> Это **снимки решений прошлых этапов**, сохранённые для аудита и воспроизводимости. Они могут противоречить современному runtime. Действующие требования: [current spec](../spec/CURRENT_PROJECT_SPEC_RU.md), [architecture](../architecture/CURRENT_ARCHITECTURE_RU.md).

Срез каталога: 30.10.2026. Отчёты содержат исходные результаты тестов своего времени, а не нынешние общие счётчики.

## Первый milestone и исходное ТЗ

- [GAME1 — отчёт по реализации M1](milestone-1/IMPLEMENTATION_REPORT_M1_RU.md)
- [Milestone 1 implementation](milestone-1/MILESTONE_1_IMPLEMENTATION.md)
- [ТЗ — НОВЫЙ ROBLOX PLACE НА ЧИСТОЙ БАЗЕ С ИНФРАСТРУКТУРОЙ ПО ОБРАЗЦУ ROBLOXLINEAGE](milestone-1/PROJECT_SPEC_MILESTONE_1_RU.md)

## Декомпозиция архитектуры M85–M105

- [M85 · Contract / Bootstrap · этап 1 декомпозиции](refactor-m85-m105/ARCHITECTURE_REFACTOR_M85_RU.md)
- [M88 — декомпозиция Host Agent: POST/DELETE](refactor-m85-m105/ARCHITECTURE_REFACTOR_M88_RU.md)
- [M89 — Host Agent: независимые Studio / файл-сервисы](refactor-m85-m105/ARCHITECTURE_REFACTOR_M89_RU.md)
- [M90 — первый этап декомпозиции MonsterSpawnerService](refactor-m85-m105/ARCHITECTURE_REFACTOR_M90_RU.md)
- [M91 — Monster Wander / Death Lifecycle и владение runtime-подписками](refactor-m85-m105/ARCHITECTURE_REFACTOR_M91_RU.md)
- [M92 — Monster Idle / Combat Animation Presentation](refactor-m85-m105/ARCHITECTURE_REFACTOR_M92_RU.md)
- [M93 — Monster Population / Spawn Slots / Respawn Scheduler](refactor-m85-m105/ARCHITECTURE_REFACTOR_M93_RU.md)
- [M94 — NPC Locomotion / Combat Recovery](refactor-m85-m105/ARCHITECTURE_REFACTOR_M94_NPC_LOCOMOTION_RU.md)
- [M96 — Декомпозиция AnimationSpeedScaling](refactor-m85-m105/ARCHITECTURE_REFACTOR_M96_ANIMATION_SCALING_RU.md)
- [M97 — Декомпозиция серверной атаки](refactor-m85-m105/ARCHITECTURE_REFACTOR_M97_COMBAT_RU.md)
- [M98 — Состояние атакующей сессии](refactor-m85-m105/ARCHITECTURE_REFACTOR_M98_ATTACK_SESSION_RU.md)
- [M99 · EntityHitboxService — разделение обязанностей](refactor-m85-m105/ARCHITECTURE_M99_ENTITY_HITBOX_RU.md)
- [M100 — Studio Game1Bridge: выделение команд и настроек](refactor-m85-m105/ARCHITECTURE_REFACTOR_M100_STUDIO_BRIDGE_RU.md)
- [M101 — Studio Timeline: разделение обязанностей](refactor-m85-m105/ARCHITECTURE_REFACTOR_M101_STUDIO_TIMELINE_RU.md)
- [M102 — Monster AI: разделение выбора целей и боевого состояния](refactor-m85-m105/ARCHITECTURE_REFACTOR_M102_MONSTER_AI_RU.md)
- [M103 — декомпозиция атаки и анимаций Monster AI](refactor-m85-m105/ARCHITECTURE_REFACTOR_M103_MONSTER_ATTACK_RU.md)
- [M104 — выделение существующей навигации Chase из MonsterAIService](refactor-m85-m105/ARCHITECTURE_REFACTOR_M104_MONSTER_CHASE_RU.md)
- [M105 — жизненный цикл агентов Monster AI](refactor-m85-m105/ARCHITECTURE_REFACTOR_M105_MONSTER_AGENT_LIFECYCLE_RU.md)

## Actors, NPC/Monster, combat, анимации и оружие

- [NPC subsystem · M59 (1hs)](actors-combat-animation/NPC_ARCHITECTURE_M59_RU.md)
- [M66 · Целостность скелета NPC при публикации и загрузке в Studio](actors-combat-animation/NPC_BONE_SURVIVAL_M66_RU.md)
- [M67 · NPC Equipment & Animation Subtypes](actors-combat-animation/NPC_EQUIPMENT_ANIMATION_M67_RU.md)
- [M68 — NPC combat: monster-like, server authoritative](actors-combat-animation/NPC_COMBAT_M68_RU.md)
- [M69 — реактивный NPC, возврат домой и политика физических тел](actors-combat-animation/NPC_RETALIATION_COLLISION_M69_RU.md)
- [M70 · Принципы Monster Attack и возврат NPC](actors-combat-animation/NPC_ATTACK_RETURN_M70_RU.md)
- [M71 — непрерывные атаки NPC и общие правила скорости анимаций](actors-combat-animation/NPC_ATTACK_LOOP_SHARED_ANIMATION_SPEED_M71_RU.md)
- [M72 · Трекинг цели и преследование во время атаки](actors-combat-animation/NPC_MONSTER_ATTACK_TRACKER_M72_RU.md)
- [M73 — физический поворот к цели и направление ног](actors-combat-animation/ACTOR_FACING_PURSUIT_M73_RU.md)
- [M74 — Custom Animation Scaling](actors-combat-animation/CUSTOM_SCALING_M74_RU.md)
- [M77 · NPC Animation Compatibility / Unarmed](actors-combat-animation/NPC_ANIMATION_COMPATIBILITY_M77_RU.md)
- [M78 · Remove / Scan Folder · жизненный цикл регистрации анимаций](actors-combat-animation/ANIMATION_REMOVE_RESCAN_M78_RU.md)
- [M93 Hotfix — индивидуальный респавн и визуальное появление монстров](actors-combat-animation/M93_HOTFIX_MONSTER_RESPAWN_REVEAL_RU.md)
- [M94 — отскок оружия только в мирном состоянии (после проверки контакта)](actors-combat-animation/M94_WEAPON_BOUNCE_POST_CONTACT_RU.md)
- [game1 character animation system](actors-combat-animation/character-animation-system.md)
- [game1 weapon system](actors-combat-animation/weapon-system.md)

## Location Assets и общие атласы

- [M94 Hotfix — Workspace-wide Location Assets / WeaponBounce по факту контакта](atlases-location-assets/M94_HOTFIX_WORKSPACE_LOCATION_BOUNCE_RU.md)
- [M117 · Alpha-aware texture binding](atlases-location-assets/ASSET_TEXTURE_ALPHA_M117_RU.md)
- [M118 · Location Assets → Sync Studio](atlases-location-assets/LOCATION_ASSETS_STUDIO_SYNC_M118_RU.md)
- [M125 · Central Texture Atlas Registry (Location Assets adapter)](atlases-location-assets/CENTRAL_TEXTURE_ATLASES_M125_RU.md)
- [M129 — Re-publish shared texture atlases](atlases-location-assets/ATLAS_REPUBLISH_M129_RU.md)
- [M162 — legacy shared atlas inheritance / Studio Sync](atlases-location-assets/SHARED_ATLAS_INHERITANCE_M162_RU.md)

## Real Estate, FBX, House Sockets и Studio Sync

- [Историческая заметка: крепление фонаря за сокет дома](real-estate/LANTERN_ATTACHMENT_RIG_PIVOT_NOTE_RU.md)

- [M107 · Real Estate · первая версия authoring pipeline](real-estate/REAL_ESTATE_M107_RU.md)
- [M111 · Real Estate: optional door and Blender error propagation](real-estate/REAL_ESTATE_OPTIONAL_DOOR_M111_RU.md)
- [M112 · Real Estate: произвольное число мешей](real-estate/REAL_ESTATE_M112_DYNAMIC_MESHES_RU.md)
- [M127 · Real Estate как потребитель Central Atlas Registry](real-estate/REAL_ESTATE_ATLAS_REGISTRY_M127_RU.md)
- [M130 · Real Estate: Atlas Library, безопасное удаление, glass и restoration](real-estate/REAL_ESTATE_M130_ATLAS_LIBRARY_GLASS_RETIREMENT_RU.md)
- [M131 — Real Estate socket and hinge rig contract](real-estate/REAL_ESTATE_RIG_SOCKET_M131_RU.md)
- [M132 · Real Estate: восстановление Studio Sync при неполном наборе сокетов](real-estate/REAL_ESTATE_M132_STUDIO_SYNC_SOCKET_DIAGNOSTICS_RU.md)
- [M133 · Real Estate: восстановление невзвешенных сокетов в Studio](real-estate/REAL_ESTATE_M133_UNWEIGHTED_SOCKET_BONES_RU.md)
- [M134 · Real Estate collision mesh contract](real-estate/REAL_ESTATE_PHYSICS_M134_RU.md)
- [M140 · Real Estate · независимые ревизии отдельных мешей](real-estate/REAL_ESTATE_SCOPED_MESH_PUBLICATION_M140_RU.md)
- [M141 — версии текстурных атласов Real Estate](real-estate/REAL_ESTATE_ATLAS_VERSIONS_M141_RU.md)
- [M143 · Real Estate — единый workflow мешей](real-estate/REAL_ESTATE_MESH_WORKFLOW_M143_RU.md)
- [M146 · Взаимодействия через пространственные сокеты Real Estate](real-estate/REAL_ESTATE_HOUSE_SOCKETS_M146_RU.md)
- [M147 · House sockets / Studio debug hotfix](real-estate/REAL_ESTATE_HOUSE_SOCKETS_M147_HOTFIX_RU.md)
- [M148 · House socket discovery в любом месте Workspace](real-estate/REAL_ESTATE_HOUSE_SOCKETS_M148_DISCOVERY_RU.md)
- [M149 · Studio House Socket Reconcile](real-estate/REAL_ESTATE_HOUSE_SOCKETS_M149_RECONCILE_RU.md)
- [M150 — House Sockets: кастомный персонаж](real-estate/REAL_ESTATE_HOUSE_SOCKETS_M150_CHARACTER_ROOT_RU.md)
- [M152 — Real Estate: Workspace sync that includes manually placed template clones](real-estate/REAL_ESTATE_PLACED_SYNC_M152_RU.md)
- [M153 · Spawn socket orientation contract (уточнён M154)](real-estate/REAL_ESTATE_SPAWN_ORIENTATION_M153_RU.md)
- [Общая подготовка Model FBX — M153](real-estate/SHARED_MODEL_PUBLICATION_M153_RU.md)
- [M154 · Spawn sockets: Tail → Head](real-estate/REAL_ESTATE_SPAWN_ORIENTATION_M154_RU.md)
- [M155 · House Sockets: stateful padlock, elevator, unified E / F](real-estate/REAL_ESTATE_HOUSE_SOCKETS_M155_RU.md)
- [M156 · Real Estate · авторский pivot при замене house FBX](real-estate/REAL_ESTATE_HOUSE_PIVOT_M156_RU.md)
- [M159 · Сокеты дома: лифт, дверь/замок, тестовый ключ](real-estate/REAL_ESTATE_HOUSE_SOCKETS_M159_RU.md)
- [M160 · Спавны этажей и прицеливание по объёмной зоне лифта](real-estate/REAL_ESTATE_HOUSE_SOCKETS_M160_RU.md)
- [M161 · AIM raycast: лифт + сундук](real-estate/REAL_ESTATE_HOUSE_SOCKETS_M161_RU.md)
- [28.10.2026 — universal FBX skin coverage и house dimensions](real-estate/SHARED_FBX_SKIN_COVERAGE_2026-10-28_RU.md)

## Studio Plots и инструменты публикации

- [M95 — Studio Markers, Publication и Population Defaults](studio-tooling/M95_STUDIO_MARKERS_PUBLICATION_RU.md)
- [M119 · Studio Plots preview](studio-tooling/STUDIO_PLOTS_PREVIEW_M119_RU.md)
