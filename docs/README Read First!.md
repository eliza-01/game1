# Навигация по документации game1

**Последняя актуализация:** 2 ноября 2026 · **Основание:** M188 дамп + M189 Characters/Animations R3.
**Правило:** читать актуальные контракты прежде, чем исторические milestone-отчёты. Старые тексты оставлены для причин, миграций и отладки, **не** как одновременно действующие ТЗ.

## 1. Действующие документы

| Документ | Зачем читать | Статус |
| --- | --- | --- |
| [M230 — Legacy Placement Compatibility](workflows/REAL_ESTATE_PLACEMENT_LEGACY_COMPAT_M230_RU.md) | Place и Place all доступны для старых Model-pivot биндов без повторного Bind; новые бинды используют точный house pivot | **CURRENT · STUDIO SMOKE REQUIRED** |
| [M229 — Real Estate Placement rotation](workflows/REAL_ESTATE_PLACEMENT_ROTATION_M229_RU.md) | Bind измеряет author house pivot, Place выравнивает по тому же anchor; сохранение точного house pivot для новых Bind; прежний запрет legacy Place отменён M230 | **CURRENT CAPTURE / HISTORICAL LEGACY POLICY** |
| [M228 — Combat reticle primary melee](workflows/COMBAT_RETICLE_PRIMARY_MELEE_M228_RU.md) | Прицельная цель в AttackRadius получает урон независимо от объёма меча, дополнительные пересечения и один headshot сохраняются | **CURRENT · STUDIO PLAY REQUIRED** |
| [M227 — Real Estate Place all / Clear all](workflows/REAL_ESTATE_BULK_PLOT_PREVIEW_M227_RU.md) | Пакетная постановка выбранного дома по сохранённым Bind и удаление всех управляемых preview; одна Studio Undo-операция | **CURRENT · STUDIO SMOKE REQUIRED** |
| [M226 — Studio plugin installer recovery](workflows/STUDIO_PLUGIN_INSTALLER_LOCK_RECOVERY_M226_RU.md) | Ошибка file-lock при копировании Game1Bridge: проверка SHA-256, безопасный retry и восстановление после частичной установки M225 | **CURRENT** |
| [M223 — Asset Manager: Atlas и Plot Place/Clear](workflows/ASSET_MANAGER_ATLAS_PLOT_PREVIEW_M223_RU.md) | Sidebar order, централизованный Atlas Registry с retirement/историей, авторский Place/Clear домов по сохранённым Bind | **CURRENT · STUDIO SMOKE REQUIRED** |
| [M222 — Shared managed rig replacement](workflows/SHARED_PLACED_RIG_SYNC_M222_RU.md) | Единый транзакционный механизм child-rig swap для Real Estate и Location Assets, полная публикация skinned FBX, аудит, откат | **CURRENT · STUDIO SMOKE REQUIRED** |
| [M221 — In-place FBX geometry Sync](workflows/LOCATION_ASSETS_INPLACE_GEOMETRY_SYNC_M221_RU.md) | Guarded MeshPart:ApplyMesh, per-slug geometry update, Studio v4, rollback/history | **SUPERSEDED BY M222** |
| [M220 — Location Assets resource workflow](workflows/LOCATION_ASSETS_RESOURCE_WORKFLOW_M220_RU.md) | Раздельные Register/Edit, FBX Model ID и независимый Atlas Registry, общие UI-компоненты Real Estate, M221 updates geometry contract | **CURRENT UI / PUBLICATION** |
| [M219 — Location Assets per-row Sync + Edit dialog](workflows/LOCATION_ASSETS_ROW_SYNC_EDITOR_M219_RU.md) | Историческая ступень: адресная кнопка Sync; устаревшее перенесение формы в Edit отменено M220 | **SUPERSEDED BY M220** |
| [M218 — Database → Asset History](workflows/ASSET_HISTORY_DATABASE_M218_RU.md) | Read-only UI, копирование slug/ID, фильтры и страницы существующего MySQL аудита | **CURRENT** |
| [M217 — полный аудит замен всех ассетов](workflows/ASSET_REPLACEMENT_AUDIT_M217_RU.md) | MySQL 8.4, объединённая история публикаций/замен всех asset-доменов, backup/recovery | **CURRENT / SAFETY CRITICAL** |
| [M216 — Location Assets: аварийный откат M215 и безопасный ID Sync](workflows/LOCATION_ASSETS_SAFE_ID_SYNC_M216_RU.md) | Строгое ограничение Studio Sync одним slug, запрет перепостроения моделей и журнал заменённых ID | **HISTORICAL SAFETY FLOOR; M221 EXTENDS** |
| [M189 — R3 Characters/Animations stores](workflows/CHARACTER_ANIMATION_STORES_R3_M189_RU.md) | Границы Python-хранилищ, контроль идентичности генерации, дальнейший долг | **CURRENT R3 STEP** |
| [Анимации: лицо, emotions и события](animation/README.md) | Четыре контроллера лица, Blender-маркеры, документы клипов и этап внедрения | **CURRENT / IMPLEMENTING** |
| [Актуальное ТЗ](spec/CURRENT_PROJECT_SPEC_RU.md) | Текущие возможности, socket/atlas/FBX/actor контракты, scope и Definition of Done | **CURRENT** |
| [Архитектурная карта](architecture/CURRENT_ARCHITECTURE_RU.md) | Модули, владение данными, уже выполненная декомпозиция и устаревшие предположения | **CURRENT** |
| [Рефакторинг: остаток работ](architecture/REFACTOR_ROADMAP_RU.md) | Completed/Partial/Pending, очередность, критерии и non-goals | **CURRENT PLAN** |
| [Инженерные правила](../AGENTS.md) | Обязательные архитектурные ограничения для любого кода | **CURRENT** |
| [Workflow и проверки](workflows/DEVELOPMENT_AND_VALIDATION_RU.md) | Запуск, patch apply, регрессии, Studio smoke, сохранность IDs | **CURRENT** |
| [Правила документации](workflows/DOCUMENTATION_RULES_RU.md) | Приоритет источников, история vs ТЗ и обновление ссылок | **CURRENT** |

## 2. Исторические материалы — каталог по доменам

[Все исторические документы по разделам](history/README.md).

- **Architecture M85–M105** — как реально разделяли серверный bootstrap, Host Agent, Monster, Combat, Studio Bridge. Не считать эти этапы невыполненными.
- **Actors / Combat / Animation** — NPC, monster pursuit, weapon attachment, attack loops и ранние animation contracts.
- **Location Assets / Atlas** — M117–M162, смена shared atlas, подтверждения Sync, legacy inheritance.
- **Real Estate / House Sockets** — M107–M161, FBX bones, sync, размеры, pivot, телепорт, E/F, AIM/USE.
- **Studio tooling** — authoring, preview, plots и публикационные инструменты.
- **Первоначальный Milestone 1** — первоначальный продуктовый план, не актуальный состав Asset Manager.

Два исторических артефакта остаются в корне `docs/` из-за контрактов и ссылок: [архитектурный аудит 14 октября](ARCHITECTURE_AUDIT_2026-10-14_RU.md), [CSV-инвентаризация 14 октября](ARCHITECTURE_SOURCE_INVENTORY_2026-10-14.csv). **Цифры и план из них датированы 14 октября.** Также один старый файл с нечитаемым именем `...pivot_...md` оставлен на месте из-за кодировки пути в исходном архиве; его содержательная тема доступна в [архивной заметке о фонаре и rig pivot](history/real-estate/LANTERN_ATTACHMENT_RIG_PIVOT_NOTE_RU.md).

## 3. Самостоятельные пакеты внутри репозитория

- [`docs/Eyesland_Character_Codex/START_HERE.md`](Eyesland_Character_Codex/START_HERE.md) — отдельный Blender character rig work package со своими `AGENTS.md` и технической спецификацией. Его requirements не автоматически применяются к текущему runtime.
- [`roblox_character_ui_agents/README.md`](../roblox_character_ui_agents/README.md) — автономное направление интерфейса персонажа с PRD/TECH/ART; его локальные docs сохраняются, не перемешиваются с историей основного проекта.
- [`place/README.md`](../place/README.md) — специфика сборки Place.

## 4. Как читать при противоречиях

Начать с текущего ТЗ и исходных contracts. Если отчёт M133 рекомендует `StudioRealEstateSocketRecovery`, он **устарел**: восстановление костей удалено M153. Если M146 рекомендует единую кнопку F для всех действий, для современной двери/замка применяются M159, а для лифта/сундука M161. См. раздел «Опасные устаревшие предположения» в [архитектурной карте](architecture/CURRENT_ARCHITECTURE_RU.md).

Чтобы добавить новый milestone: сохранить **отчёт** в соответствующем `history/<domain>`, а **действующий контракт** обновить в `spec/` и/или `architecture/`, затем обновить [каталог](history/README.md). Не дублировать конкурирующие «актуальные ТЗ» под разными датами.

- [M224 · Placement Anchor/Free, Atlas grouping, sidebar/database hotfix](workflows/ASSET_MANAGER_M224_PLACEMENT_ATLAS_HOTFIX_RU.md) — актуальные правила авторских превью и удаления атласов.

- [M231 · Location Assets FBX COLLISION / Glass / Skeleton](workflows/LOCATION_ASSETS_FBX_COLLISION_SKELETON_M231_RU.md) — общий анализ FBX и Studio-физика.

- M232: `docs/workflows/LOCATION_ASSETS_FBX_AUTHORING_M232_RU.md` — общий FBX inspection, видимый редактор mesh/collision/bones и исправление Precise для COL.

- [M233 · Location Assets Model-only publication isolation](workflows/LOCATION_ASSETS_MODEL_ONLY_PUBLICATION_M233_RU.md) — модельный FBX без встроенных атласов; отдельный API и запрет неявного Image upload.

- [M234 · Shared Atlas Editor / Apply Changes / Studio Sync](workflows/SHARED_ATLAS_EDITOR_APPLY_M234_RU.md) — CURRENT: единый редактор атласов для Real Estate и Location Assets, сохранение привязанных вариантов, предпросмотр совместного republish, только явный Studio Sync.
