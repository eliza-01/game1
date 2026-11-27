# game1 — действующая карта архитектуры

**Аудит по коду:** 2 ноября 2026, `game1_diag_2026-11-02_02-52-50.zip` (M188), с декомпозицией Python stores M189.
**Источник инженерных ограничений:** [`AGENTS.md`](../../AGENTS.md).
**Историческое обоснование:** [аудит 14 октября](../ARCHITECTURE_AUDIT_2026-10-14_RU.md). Его старые размеры файлов и список «следующих этапов» не актуальны.

## Слои и направления зависимостей

```text
Blender/FBX, atlas files
      ↓
system/asset-manager/ + system/control-center/{api,services,stores,real_estate}
      ↓          ↘ Open Cloud / local Host Agent / SQLite
assets/manifests + src/shared registry exports
      ↓
system/studio-plugin/ modules  →  Studio templates / placed models
      ↓
src/shared {contracts, policies, calculations, registries}
      ↙                                        ↘
src/server {authority, actors, house, combat}   src/client {input, presentation, debug}
```

Studio Plugin/Host Agent — **authoring plane**, не клиентский игровой runtime. Реплицируемые RemoteEvents не становятся источником истины о положении, владении предметом или уроне.

## Фактически выделенные компоненты

| Направление | Текущая граница | Проверено в исходниках |
| --- | --- | --- |
| Server bootstrap | `src/server/bootstrap/ServiceCatalog.luau`, `ServiceBootstrap.luau` | Список критичных/необязательных сервисов, dependencies, startup health; `init.server.luau` — тонкий entrypoint |
| HTTP Agent | `system/control-center/host_agent.py`, `api/read_dispatch.py`, `api/write_dispatch.py` | Роутинг вынесен; конструирование stores и dependency wiring всё ещё централизованы |
| Monster runtime | `src/server/monster/MonsterSpawnerService.luau`, `MonsterAIService.luau` и узкие modules | Population/AI/navigation/attack/lifecycle выделены; их не следует собирать обратно в один сервис |
| Combat | `src/server/combat/AttackService.luau`, `EntityHitboxService.luau`, spatial/session modules | Server authority, attack session и hitbox geometry разделены частично |
| Studio Bridge | `system/studio-plugin/Game1Bridge.server.luau`, `modules/Studio*` | Команды, Timeline, scene placement, Real Estate и validation разделены |
| Real Estate | `system/control-center/real_estate/{store,contracts,studio_sync,jobs,...}.py`, StudioRealEstate* | Авторинг и mesh revisions отдельно от sync; `store.py` всё ещё крупный |
| FBX | `system/asset-manager/model_publication.py`, `bone_weight_survival.py` | Общая подготовка скиннинга; независимо от ассетной категории, включая проверку покрытия вершин |
| Atlas | Registry + consumers Location/Real Estate | Shared Image ID у варианта; legacy inheritance поддерживается для существующих записей |
| Characters (M189, R3) | `character_store.py` + `character_core/{archetype_contract,model_workflow,registry_export}.py` | Основной фасад удерживает SQL access, stats/active identity; регистрация/публикация FBX и runtime export отделены; текущие API и ID не менялись |
| Monster/NPC Animations (M189, R3) | `monster_animation_store.py` + `monster_animation_core/{schema,bindings,publication}.py` | Схема/миграции, mutation привязок, публикация отделены от scan/read/export; Character Animations (`animation_core/`) не затронут |
| Verification (M164–M171) | `system/verify/verify.py` → `system/verify/validators/` | Вынесены source-only, project layout, Monster registry/spawn, Actor runtime и Combat Contact/Headshot, Character, Animation, Weapon, Studio Debug, Death, Attack Timeline и Rojo/Animation Speed tooling, Location/Deco/Environment/Texture Sync (M169), Combat foundation/Hitbox/Studio Character Bridge/registered attack clips (M170). `verify.py` содержит только orchestration; M171 устранил пропуск ошибок M54/M55/M128 при расчёте exit code. R2 завершён |
| House runtime | `HouseSocketContract`, `HouseElevatorPolicy`, `HouseSocketService`, `HouseDoorService`, `HousePadlockService`, клиентский Prompt, Studio debug | USE/AIM, модельный pivot двери, server authorization; детальнее в [ТЗ](../spec/CURRENT_PROJECT_SPEC_RU.md) |

## M570 · навигация и авторинг (сверка 27.11.2026)

| Ответственность | Источник / модули | Граница |
| --- | --- | --- |
| Баланс и общие эффекты | `config/balance/gameplay.json` → `BalanceRegistry` → `Balance.Skill` | Database Main; Buffer и HUD не содержат независимых численных параметров |
| Spawn Zones | `StudioMonsterSpawnAuthoring` / `game-balance.js` → `monster_spawn_store.py` → `assets/manifests/monster-spawns.json` → `MonsterSpawnRegistry` | Studio создаёт, перемещает, удаляет; браузер меняет параметры существующей записи через revision-guarded API; маркеры не источник runtime |
| Pursuit policy | `MonsterDeathChasePolicy` → AI, experimental navigation, ranged retreat | Death Chase и Home Leash взаимоисключающие; territory optional; калибровка отдельно |
| Navigation dispatch | `MonsterNavigationDispatch` → `MonsterExperimentalNavigation` либо `MonsterChaseNavigation` | Только Studio A/B; legacy и NPC сохранены; боевой таймлайн отдельно |
| Recovery geometry | `MonsterRecoveryGeometry` | Верхний/нижний луч, выход через пятки + основной луч, локальный обход и физический подъём; нет резервных sweep для щелей |
| Blocked pursuit M591 | `MonsterExperimentalNavigation` → `MonsterBlockedPursuit`, `MonsterBlockedRetreatGeometry`, `MonsterNavigationSpeed`; `MonsterNavigationDispatch` → AI/Presentation | Отступление/ожидание после NoAccessiblePlan, один владелец движения, ожидание запускает таймеры, геометрия отдельно; Options → GameOptions → Config; множители движения/анимации без перемножения, M592: максимальная дальность лука из Balance.Weapons с боевыми ограничениями, независимо от экипировки цели. |
| Rescue graph | `StudioRescueRoutes` → Place `Game1RescueRoutes` → `MonsterRescueGraph`; `rescue_route_store.py` → manifest | Place — источник координат графа; Database — зеркало; M590: Graph оркестрирует Topology → Routes → Entries → Paths → Exits; Connections — отдельные переходы только от свободных концов целой линии, с перепадом высоты ≤ Options routeConnectionHeight (2 studs по умолчанию), Sampling — 20/4 по длине линии; Segments — геометрия, Queries — per-search кэш и observer; Geometry — физика. Приоритет маршрута по цели, выхода внутри линии по высоте; каталог только метаданные |
| Trace | `MonsterNavigationTrace` | Studio Server Output, опциональный фильтр; без дополнительных кастов |

[Полный контракт и открытые проверки](../workflows/M570_GAMEPLAY_INFRASTRUCTURE_RU.md). Не объединять authoring, боевые решения, политику преследования и граф в один сервис. Производительность и физика эксперимента требуют измерений.

## M541 · gameplay test / прогрессия (сверка 26.11.2026)

| Ответственность | Модуль / поток | Граница |
| --- | --- | --- |
| Баланс | `config/balance/gameplay.json` → `BalanceRegistry` → `Balance` | Общий источник XP, порогов, экипировки, monster stats; не менять формулы ради стенда |
| Размещение | `GameplayWorldHuntingPlan` → `GameplayTestLayout` | Данные охотничьих карманов отделены от построения площадок; 6 зон + 2 calibration annexes |
| Жизненный цикл | `GameplayTestService`, `GameplayTestPanels`, `GameplayTestLoadout` | Один Studio-владелец; enter/exit/respawn, server checks, stock selection; временные данные отдельно от профиля |
| Награды | `ActorDamageSignals` → `CharacterProgressionService` | Сервер выбирает обычную ветку либо GP Reward; GP-событие никогда не проваливается в профиль |
| Проекция | `CharacterProgressionView.Publish` → `CharacterStatsService.SetProgressionLevel` | Общая функция отображения XP/Gold/уровня и пересчёта HP; не writer профиля |
| Hub | `GameplayTestService` → `GameplayTestHubRunMultiplier` → клиентское движение/анимация | Сервер определяет границы, клиент применяет ×3; не постоянный RunSpeed и не полная серверная проверка перемещения |
| Авторинг | `OptionsStore` → `options.json` → `GameOptionsRegistry` | `debugUi.startInHub` — boolean, default false; Studio guard не зависит от названия секции Options |
| Design | `KanbanStore` + KBN-0031, SVG UI | Продуктовый план и ссылки на иллюстрации, не источник runtime-спавнов; ревизии/SHA/история сохраняются |

См. [M541 workflow](../workflows/M541_HUB_WORLD_PROGRESSION_RU.md). Исторические размеры модулей и карта архитектуры M189/M439 ниже не являются новым сквозным аудитом. Studio/Android-приёмка остаётся открытой.

## M439 · актуальная схема World LOD и House Mechanics

| Владелец | Фактические компоненты | Правило |
|---|---|---|
| Source registrations | `services/location_lod_resource.py`, Atlas Registry, Real Estate stores | Asset ID/SHA/slug/revision принадлежат своим Stores, не клиенту |
| LOD profiles | `services/location_streaming_config.py`, `services/house_part_distances.py`, `services/house_runtime_profile.py` | Дистанции на каждый ассет/House part; общие только hysteresis и native Workspace profile |
| Studio Preview | `services/lod_studio_preview.py` → `StudioLodPreviewContract` → Studio Bridge → `StudioLodPreviewAdapter` | Preview schemaVersion=2, сохранённые изменения приходят в Play без Runtime rebuild |
| Runtime Build | `services/location_runtime_build.py`, `LocationRuntimeManifestContract`, `LocationLodTemplateService` | Offline `.rbxlx` + backup + marker, `publishAllowed=false` |
| Client visuals | `LocationWorldStreamer`, `HouseVisualAdapter`, `LocationCompositeVisual` | Визуалы локальные, серверные коллизии остаются в мире |
| House interactions | `HouseSocketContract`, `HouseSocketService`, `HouseDoorService`, `HouseElevatorService`, `HouseFireplaceService` | Server-owned actions/timers, клиент только визуал и ввод |
| Mechanics docs | `mechanics/catalog.py`, `mechanics/house.py`, `api/mechanics.py` | Read-only source allowlist; `cooking_pot_socket` — вложенная точка модели котла |
| Development Kanban | `kanban_store.py`, `docs/kanban/cards`, `specs`, `history` | SHA256+revision+history атомарны; приёмку Studio не синтезировать |

Эта таблица проверена по проектным файлам на срезе M438a; ей **не** присваивается статус Studio Play/полевого теста. См. [актуальный Kanban](../kanban/STATUS_2026-11-22_M439.md).

## M449 · единый контракт радиусов сокетов

`OptionsStore` — единственный writer постоянных `socketRanges` (`options.json` → `GameOptionsRegistry`). `HouseSocketContract` и `CampfireSocketContract` применяют их к серверному USE и клиентскому AIM через существующие сервисы; HS Studio Debug использует только временные атрибуты игрока. В Mechanics остаются тайминги и эффекты камина/костра, но не редактируемые диапазоны взаимодействия. См. [M449](../workflows/SOCKET_RANGES_OPTIONS_M449_RU.md).

## Опасные устаревшие предположения

- **Не считать** `StudioRealEstateSocketRecovery` действующим механизмом: M133 описывает удалённый в M153 workaround. Текущий Studio Bridge проверяет фактические Bones.
- **Не считать** `M146` текущими клавишами: единая `F`-подсказка заменена более поздними M155/M159/M161 правилами.
- **Не считать** AIM зоной курсора на экране: после M161 луч идёт из центра прицела, проверяется occlusion. Старые описания M160 — снимок предыдущей реализации.
- **Не считать** `TextureID` у каждого потребителя отдельной независимой публикацией: M125/M162 используют Atlas Registry и адаптеры наследования.
- **Не делать** реставрацию автора в Studio при потере костей и не вводить компенсационное масштабирование Model без сравнения Blender/FBX/Roblox.
- **Не обобщать** «завершено» на всё MMO: в коде есть placeholder chest/lock/key, а опубликованные ID и приватные данные вне dump не переоцениваются.

## Зоны ответственности, ещё требующие декомпозиции

Текущие размеры: `verify.py` **~187 строк после M171** (2986 до M164), `MovementDebugController` ~1009, `TestLoadoutController` ~987, `monster_animation_store.py` 469 после M189 (946 ранее), `real_estate/store.py` 822, `character_store.py` 250 после M189 (834 ранее), `location_asset_store.py` 691 строк. **Размер лишь триггер аудита, не доказательство неправильных границ.** Для каждого этапа нужен анализ read/write ownership, API и тестов.

- Python stores: хранение + публикационный workflow + совместимость legacy/manifest могут смешиваться; выносить через service/repository с сохранением внешних методов.
- Клиентские debug UI: повторяющиеся элементы и управление inputs, но не выносить gameplay ownership из server.
- NPC на monster-инфраструктуре: это существующая внутренняя совместимость, не контракт будущего `Actor` API.
- `HouseSocketService` и большой debug controller: дополнительно распределять state, eligibility, effect и UI при росте функционала.
- `verify.py`: M164–M170 вынесли 23 валидатора (source-only, project layout, Monster, Actor runtime, Combat Contact/Headshot, Character, Animation, Weapon, Studio Debug, Death, Attack Timeline и authoring tooling, Location authoring, Location Assets, Deco Studio, shared texture variants, environment bounce, published texture sync, categories). Фасад уже стал тонким координатором; дальнейшего дробления ради количества строк не требуется. В M171 устранён дефект прежнего CLI: M54/M55/M128 теперь учитываются единственной проверкой `if errors`; при ошибке код завершения `1`, при успехе `0`. Подтверждено независимыми end-to-end тестами. R2 закрыт; сохранять CLI и регрессионные тесты при будущих изменениях.

## Статус первоначального рефакторинга

M85–M105 **реализовали** значительную декомпозицию bootstrap, Host Agent, Monster lifecycle, Combat/Hitbox и Bridge. До M162 появились другие доменные модули. Старый текст `Planned decomposition (not yet implemented)` в AGENTS был устаревшим. Нынешний список и последовательность с критериями — [REFACTOR_ROADMAP_RU.md](REFACTOR_ROADMAP_RU.md).

## Порядок обновления этой карты

При изменении сервиса, store, контрактов Remote или schema обновлять: (1) текущую карту/ТЗ, (2) область проверки и ограничения, (3) исторический milestone-отчёт при крупном изменении. Не переписывать задним числом старые выводы. Наличие README или unit test не равно авторскому подтверждению Studio runtime.


### M203 · Атласы и потребители

Real Estate и Location Assets не владеют Image Asset и не публикуют его сами. Варианты и исходники принадлежат Atlas Registry; в `texture_atlas_bindings` — только ссылки `consumer_type/consumer_id → variant_id`. M203 удаляет исторические owner-ссылки/retained-slug механизм миграцией двух баз. Проекции `textureAssetId` в runtime реестрах не являются ownership. Weapon/Monster/NPC texture slots пока отдельный старый контур — не приписывать его к этому контракту без миграции. Подробнее: `docs/workflows/ATLAS_INDEPENDENCE_M203_RU.md`.

### M216: безопасность синхронизации Location Assets

`DecoPlacedAssetSync.RefreshIds` — исключительно редакторская замена двух Image ID
свойств на существующих MeshPart для **одного** `Game1DecoAssetSlug`, плюс
метаданные Model Asset reference. Обновление самой FBX-геометрии/физики не входит
в Sync Studio. `StudioDecoSyncCommands` принимает только schemaVersion=3, Host
Agent валидирует target slug и сохраняет append-only журнал изменений ID через
`LocationAssetSyncHistory`; общий Atlas Republish не запускает Studio Sync.
См. `docs/workflows/LOCATION_ASSETS_SAFE_ID_SYNC_M216_RU.md`.

### M217: постоянный аудит замен всех ассетов

`MySqlAssetReplacementAudit` — единственный writer нормализованных audit-таблиц
MySQL 8.4. `SqliteAssetAuditImporter` проецирует store-owned publication tables
в общий журнал без изменения SQLite. `LocationAssetSyncHistory` отдельно
координирует Studio WAL и per-instance результат (`instanceId`, path, old/new
IDs). Ошибка MySQL блокирует audit-sensitive publish/delete/Sync, но не запуск
остальных Host Agent сервисов. См.
`docs/workflows/ASSET_REPLACEMENT_AUDIT_M217_RU.md`.


## M447 · Граница авторского хранения и runtime state (23.11.2026)

[Матрица всех Mechanic-карт и их долгов](../workflows/MECHANICS_RUNTIME_GAPS_M447_RU.md) уточняет ownership без изменения кода: Project Stores/генераторы (`OptionsStore`, `mechanics.settings`, реестры и spawn manifests) владеют **authoring**; серверные `HouseFireplaceService`, `NpcSpawnerService`, `MonsterPopulationController`, `CharacterService` владеют **live session**; клиентские `InformativeWindowDock` и feedback-контроллеры владеют только представлением. Наличие первого слоя не означает DataStore для второго. Будущий persistent world/player adapter должен быть отдельной ответственностью, с безопасным восстановлением при новом Server/Streaming/re-register, без копирования save-кода в каждый service. Studio Play и compiled Runtime Build acceptance остаются открытыми.

## M533 · Направленные статусы

`MonsterTargetPolicy.CanBeginTargetedCast` проверяет допустимость, дальность и LOS до начала; `MonsterSkillCast` применяет зафиксированный навык без повторной hit-геометрии, сохраняя life/isolation/serial guards. `SkillEffects` остаётся владельцем длительности и модификаторов. `CharacterAnimationController` использует существующий cache и social resolver для stun, `AttackController` завершает aim/movement presentation, `StatusEffectVisuals` владеет локальным attachment и VFX. Схема Database и Remote-контракты не меняются. См. M533 workflow.
