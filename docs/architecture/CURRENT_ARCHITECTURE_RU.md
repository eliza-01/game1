# game1 — действующая карта архитектуры

**Аудит по коду:** 2 ноября 2026, `game1_diag_2026-11-02_02-52-50.zip` (M188), с декомпозицией Python stores M189.
**Источник инженерных ограничений:** [`AGENTS.md`](../../AGENTS.md).
**Историческое обоснование:** [аудит 14 октября](../ARCHITECTURE_AUDIT_2026-10-14_RU.md). Его старые размеры файлов и список «следующих этапов» не актуальны.

## Текущий приоритет · Performance P0

**Текущий порядок (заменяет предыдущий):** Решение владельца 27.11.2026 (M613): временно отложить новые измерения и общий Performance Profiler. Сначала точечный рефактор критических модулей по подтверждённым дефектам статического аудита. Профилирование и итоговая приёмка остаются открытыми; не требовать baseline как блокирующую предпосылку рефактора. M613 — [общий пул sampler NPC/Monster](../workflows/M613_ACTOR_SAMPLER_POOL_RU.md). M614: серверный Combat broad phase переведён на NativePartSpatialIndex (GetPartBoundsInBox по существующим RootCollider, без новых Parts/циклов); точные проверки и дальность лучей сохранены. 300 сравнений кандидатов с полным перебором в Lua mock; Studio/DEV и замеры открыты. Следующие потребители — LOD, AI и сокеты. [M615](../workflows/M615_ACTOR_AI_SCHEDULER_RU.md): общий ActorAIScheduler для Monster/NPC с очередью deadlines; интервалы 0,1 с, Aggro 0,3 с и существующие боевые события сохранены. Experimental Navigation, Rescue Routes, BlockedWait и все таймеры не изменены. M616: локальный PlayerSpatialIndex (XZ, ячейка 32 studs, один ленивый снимок на пакет scheduler; порядок GetPlayers и точные policy сохранены). 1200 сравнений с полным обходом в Lua-модели; NPC остаются retaliation-only. M617: opt-in Adaptive AI LOD (Options → AI Performance): активные 0,1 с; агрессивный Idle сохраняет дедлайн Aggro 0,3 с, пассивный Idle и закреплённый NPC дома — контроль 0,3–2 с, событийное пробуждение до 0,1 с. Глубокий сон агрессивных отложен до гарантированного обнаружения входа в Aggro без потери реакции; навигация и боевые решения неизменны. Далее ComputeAsync budget (Legacy/NPC); Studio/DEV и замеры открыты.

M618: Native Navigation Budget только для Legacy Monster и NPC: FIFO, 2 одновременных ComputeAsync и 8 стартов/с (Options → AI Performance; диапазоны 1–8 и 1–30). Experimental Navigation и Rescue Routes не участвуют. Результат применяется только в текущем шаге навигации после проверки актуальности, ожидание не считается физическим застреванием. Studio/DEV и измерения открыты. [M618](../workflows/M618_NAVIGATION_BUDGET_RU.md).

M619: Runtime LOD этап 1 — StaticPlacementIndex (BVH по 3D snapshot pivot и hide+hysteresis), LocationLodCandidates (локальная область + прежние desired/actual до выгрузки). Только реальные переходы сортируются; при равной дистанции — порядок manifest. Policy, интервалы, fallback, сборка, HouseVisualAdapter, Studio Preview, server physics и AI сохранены. Composite effects пока обслуживаются отдельным проходом; threshold queue, cache, incremental budget и Real Estate ещё открыты. Studio/DEV и замеры не выполнены. [ТЗ Runtime LOD](../workflows/RUNTIME_LOD_STREAMING_REFACTOR_SPEC_RU.md).

M620: Runtime LOD этап 2 — LodThresholdCache (запас до порогов ±h, смещение от последнего resolve, точные границы и смена камеры) и LodTransitionQueue (одна заявка на placement, отмена/замена, сортировка только при изменении приоритета). При неподвижной камере BVH и стабильные дистанции не пересчитываются; fallback/proxy/effects продолжают обслуживаться. Aging 8 ticks; тяжёлая просроченная Location-заявка может получить полный бюджет на чётном tick, нечётный сохраняет резерв House. Policy, интервал и визуальный контракт сохранены. Кэш готовности, порционная сборка, Real Estate и Studio/DEV/профиль открыты.

M621: Runtime LOD этап 3 — shared LodPrototypeCache по Instance identity/generation/variant/contract, event-driven readiness missing/incomplete/ready/invalid, две bounded retries, late cache folder/Ready, frozen metadata/bounds и FULL component map. LocationWorldStreamer продолжает работу при отсутствующем/позднем template folder; stale generations обновляют visual атомарно. HouseVisualAdapter использует shared readiness cache для LOD1 и rebuild при замене шаблона, остаётся отдельным distance adapter. M619–M621 code/oracle checks готов; incremental assembly budget, common House queue/index и Studio/DEV/профиль открыты. [ТЗ](../workflows/RUNTIME_LOD_STREAMING_REFACTOR_SPEC_RU.md).

M622: Runtime Location stage 4 — `LodAssemblyJob` / `LodRuntimeWork`: detached incremental assembly (single mesh, multipart LOD, composite FULL); 12 build + 8 cleanup operation groups/frame, separate atomic commit reservation up to 132 groups, 16 queue checks/category/frame, one active job (≤64 visual meshes), at most two retired bundles. Commit revalidates proxy identity/current CFrames, preserves previous visual until swap and keeps effects tied to actual. Desired/prototype generation/root changes cancel staging; cleanup is incremental. Old Location cost clamp removed. House keeps independent 8/tick reservation pending stage 5; Studio Preview multipart drains the same job synchronously. Counts are not a hard CPU deadline; native streaming, effect traversal and Studio/DEV/Mobile profiling remain acceptance items. T03/A03 open.

M623: Real Estate stage 5 — every house part is a record in the common static BVH, threshold cache, aging transition queue and `LodRuntimeWork`. House influence uses a conservative sphere around scaled snapshot bounds; exact policy remains `ResolveHouse` with surface distance and per-part hide/LOD1. FULL acquisition (`HouseMeshRequests`) has four combined in-flight/ready slots, 15 s retry, generation and moving-proxy identity checks; async completion cannot publish. Detached result enters the common job, old actual survives until atomic commit, failure or absent preferred prototype preserves old actual; cold missing LOD1 can fall back to FULL. Missing unpublished part LOD1 retains FULL→UNLOADED. Shared unload/retirement handles committed geometry. Discard of a stale raw async MeshPart is immediate (bounded by four slots), outside the staged assembly counters. Only active moving parts are followed each frame; lost proxy detaches the owned mesh and removes DoorRaycast binding, stream-in rebinds using current CFrame and appearance. Static active parts refresh proxy color/material during local observation. Server physics, manifest, sockets and authority unchanged. Lua mocked lifecycle and mixed spatial/async oracles; actual Studio/DEV/Mobile, House5 interactions/two-client and profiling remain NOT_RUN. Preview still synchronous; T03/A03 open.



M606a закрепляет обязательный цикл [KBN-0035–0039](../kanban/README.md#текущий-фокус--27112026--performance-review-m605). Это целевая архитектура оптимизации, не описание уже реализованных модулей. Новые механики отложены до приёмки цикла; исключения — блокирующие дефекты и необходимые для приёмки работы.

- **Диагностика:** единый контракт агрегированных измерений client/server, scopes MicroProfiler, ограниченная память и очистка. OFF по умолчанию без диагностических циклов, постоянных аллокаций и RPC; доступ только через действующий Debug-контракт. CPU/GPU/frame time, RAM и сеть не смешивать.
- **Пространственная инфраструктура:** общий алгоритм индекса, отдельные серверные и клиентские владельцы данных; статические placements и динамические существа обновляются по своим lifecycle. Broad phase не заменяет точную проверку и серверную авторизацию. Эквивалентность запросов сверять с полным перебором в тестах, не оставлять параллельный legacy runtime.
- **Клиент:** общий строгий бюджет sampler для NPC/Monster, native Bone RigidConstraint для жёсткой экипировки (M609, функционально принят, без follower), бюджет подготовки и сборки World Streaming, локальная выборка сокетов и кэш дверных мешей без периодического переключения CanQuery, ограниченный пул Overhead UI с cleanup. Сохранять позы, коллизии, точное наведение и правила видимости.
- **Сервер:** пространственный combat broad phase (melee, bow, headshot), общий планировщик AI с безопасным пробуждением и справедливым бюджетом ComputeAsync; авторитетный бой, агро, leash, blocked wait и rescue routes сохраняются. Экспериментальная навигация остаётся opt-in/OFF в опубликованном Runtime.
- **Asset pipeline:** версия готовых bone-local bounds привязана к mesh revision/rig/scale; предрасчёт в Control Center, миграция с parity и откатом, отсутствие скрытого fallback. Приоритетная загрузка уникальных клипов/ресурсов вместо массовой репликации вариантов внешности, с дедлайном, отменой и сохранением Death/DeathIdle.

Исключение владельца: M607 (KBN-0037-T02) первым; M613 — рефактор критических модулей до новых замеров, затем остальные задачи цикла. Не создавать отдельные глобальные циклы и индивидуальные несогласованные лимиты для каждого контроллера. Измерять каждый этап в одинаковых условиях; синхронно обновлять производителей/потребителей контрактов и доказательства приёмки в Kanban. Точные бюджеты и частоты утверждаются по измерениям. Подробные границы и критерии — в пяти спецификациях, статический аудит не означает подтверждённый выигрыш.

## M612 · Remote Player Attack

AttackPresentationState публикует серверный snapshot принятой атаки, AttackPresentationPhase определяет фазу, RemotePlayerAttackController подписывается на lifecycle удалённых персонажей. AttackUpperBodyComposer переиспользуется через независимые контексты и общий scheduler только активных атак. Локальное процедурное наведение остаётся локальным; урон и движение не меняются. Общий бюджет sampler и фактические замеры открыты в KBN-0037.

## M611 · Network Motion Owner

NetworkMotionOwnerCapture запускается только в авторизованном DEV при запросе наблюдателя, прекращает RenderStepped по завершении окна или таймауту. Существующий RemoteEvent передаёт один старт и один агрегированный отчёт цели; сервер проверяет отправителя, ID сессии, окно времени, конечные числовые поля. NetworkMotionCapture измеряет dt монотонными локальными часами; синхронизация окна остаётся по серверному времени.

## M610 · Network Motion diagnostics

NetworkMotionStatistics — ограниченный числовой агрегатор; NetworkMotionCapture — чтение одного NavigationRoot в согласованном окне времени; NetworkMotionDiagnosticService — авторизованная серверная сессия с cooldown и общим лимитом; NetworkMotionDiagnosticView — существующая Camera Debug панель, ручной запуск, вывод отчёта. Никаких постоянных измерительных циклов, изменений CFrame или потока координат. Общий Profiler продолжить после записи baseline.

## M609 · Equipment socket contract

`RigidEquipmentMount` восстанавливает прежнюю семантику: P — анимированная родительская Bone, L — authored CFrame сокета, R — поправка ориентации. Желаемая world-поза grip = P*L*R. Attachment1 имеет локальный frame grip*(L*R)^-1; Attachment0 — родительская Bone (для верхнего уровня identity Attachment на MeshPart). Вспомогательные Bone M608 и исключения из карт скелетов удалены. Weapon lookup возвращён к прежней области Visual; hair readiness использует rig_carrier. Timeline и аналитическая точка выпуска стрелы используют endpoint frame. Никакого покадрового follower. Владелец подтвердил работу M609 в Runtime и на физическом телефоне. Контракт принят для жёсткой экипировки; полная матрица регрессий и замеры CPU/Physics/frame time ещё открыты. Следующий этап — общий Performance Profiler. Не возвращать follower или вспомогательные Bone.

## M608 · Equipment socket contract (отклонённый эксперимент)

`RigidEquipmentMount` создаёт и переиспользует маркированную identity Bone под каноническим сокетом. RigidConstraint связывает дочернюю Bone и скорректированный grip. Вспомогательная Bone не участвует в картах композиции/сравнении NPC-скелетов; bow release использует исходную animated Bone. Timeline использует joint frame при явном семплировании. Не меняются корневая физика, число constraints, исходные FBX и публикации. M607 и M608 не прошли визуальную приёмку; M608 удалён в M609.

## M607 · Equipment mounting (исходный контракт)

`RigidEquipmentMount` — общий контракт hair/weapon, `BoneModelMount` — только статическое выравнивание. `CharacterAssemblyBuilder` и `WeaponEquipService` создают по одному RigidConstraint на предмет; NPC используют EquipVisual. Составные части свариваются внутри предмета; без коллизий, touch/query, с Massless и низким RootPriority. Нет runtime-перемещения предметов по кадрам. Timeline WorldModel отдельно применяет уравнение joint при явном семплировании позы. Нативное следование и стоимость Physics требуют приёмки на физическом телефоне.

## M605 · HUD / Animation readiness

`HudButtonTheme` — общая подложка Wallet и touch controls; `HudSvgIcons` — единый кэш SVG raster payload для House и Mobile (перенесён из HouseInteractionStateIcons). `MobileLayout` сохраняет масштаб CoreUISafeInsets, мобильные combat/weapon слои имеют общий физический правый DeviceSafeInsets край. `WorldAnimationPreloader` — один клиентский content fetch без per-actor Animator, `CharacterAnimationController.WaitForPrewarm` наблюдает существующий cache job, `CharacterCreationController` владеет curtain и отменой. Death оставляет серверный track owner и terminal hold, а клиентский compositor освобождает sampler до записи позы.

## M602 · Camera-relative backpedal

`MovementController` — единый владелец world-space travel и reversed gait для PC и touch. Удалена root-relative/RMB ветка; `cameraRelativeDirection` использует текущую камеру, `cameraForwardDirection` задаёт facing при backpedal, существующие explicit facing locks сохраняют приоритет. Новых контроллеров и RPC нет.

## M601 · Weapon corner / binding

`WeaponSelectionController` отделяет мобильный DeviceSafeInsets от desktop. `MobileWeaponSlots` измеряет CoreUISafeInsets через GuiService и использует общий MobileLayout; остальные HUD не перемещаются. Database JSON остаётся источником binding, BalanceRegistry — его проекцией. `WeaponEquipService` и серверная авторизация не меняются.

## M599 · Mobile debug and equipment shortcuts

`DebugDockProfile` разделяет наборы launcher и используется bootstrap и layout. `MobileWeaponQuickSelect` владеет жизненным циклом touch slots; `WeaponSlotCatalog` выбирает slug из серверного каталога. `WeaponSelectionController` остаётся владельцем RPC, mobile ветка возвращается до создания desktop picker. Серверные границы не изменены.

## M598 · Mobile HUD geometry

`MobileLayout` вычисляет пропорции и полярные координаты Skill относительно Attack, а также фактические границы контекстной области. `HudCornerLayout` задаёт единый footprint Settings / Debug; `StudioDebugDock` учитывает размер weapon grid на touch. Ввод и RPC M597 неизменны.

## M597 · Mobile action routing

`AttackRepeatInput` хранит источники удержания и автоматический режим; `AttackController` использует существующий RenderStepped и timeline lock. `MovementController` владеет jump hold, ground sensor и импульсом. `MobileActionRegistry` регистрирует UI action surfaces, `MobileActionTouches` хранит независимые пальцы и отличает tap от drag; `MobileInputController` единственный маршрутизатор камеры/джойстика. `MobileLayout` задаёт shared safe-area контракт, `MobileControlsView`/`MobileWeaponSlots`/`SettingsLauncherView` только рисуют UI. `WeaponSelectionController` по-прежнему единственный клиентский владелец DEV equip RPC. [M597](../workflows/M597_MOBILE_HOLD_HUD_RU.md).

## M596 · Character Roster

`CharacterCreationGateway` владеет стадиями и общей блокировкой запросов; `CharacterRosterGateway` управляет списком/выбором/удалением. `CharacterProfileRoster` — чистые операции над схемой v2, `CharacterCreationProfileStore` — миграция, CAS UpdateAsync и выбранная запись. `CharacterProgressionService` по-прежнему работает с `Profiles.Get(player)`, теперь это выбранный ID. `CharacterRosterView` отвечает за UI выбора, `CharacterCreationController` — за RPC, epoch и превью. Отдельных циклов нет. [M596](../workflows/M596_CHARACTER_ROSTER_RU.md).

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

## M594 · навигация и авторинг (сверка 27.11.2026)

| Ответственность | Источник / модули | Граница |
| --- | --- | --- |
| Баланс и общие эффекты | `config/balance/gameplay.json` → `BalanceRegistry` → `Balance.Skill` | Database Main; Buffer и HUD не содержат независимых численных параметров |
| Spawn Zones | `StudioMonsterSpawnAuthoring` / `game-balance.js` → `monster_spawn_store.py` → `assets/manifests/monster-spawns.json` → `MonsterSpawnRegistry` | Studio создаёт, перемещает, удаляет; браузер меняет параметры существующей записи через revision-guarded API; маркеры не источник runtime |
| Pursuit policy | `MonsterDeathChasePolicy` → AI, experimental navigation, ranged retreat | Death Chase и Home Leash взаимоисключающие; territory optional; калибровка отдельно |
| Navigation dispatch | `MonsterNavigationDispatch` → `MonsterExperimentalNavigation` либо `MonsterChaseNavigation` | Studio A/B; опубликованный Runtime opt-in (enabled + runtimeEnabled, default OFF); Legacy и NPC сохранены; боевой таймлайн отдельно |
| Recovery geometry | `MonsterRecoveryGeometry` | Верхний/нижний луч, выход через пятки + основной луч, локальный обход и физический подъём; нет резервных sweep для щелей |
| Blocked pursuit M591 | `MonsterExperimentalNavigation` → `MonsterBlockedPursuit`, `MonsterBlockedRetreatGeometry`, `MonsterNavigationSpeed`; `MonsterNavigationDispatch` → AI/Presentation | Отступление/ожидание после NoAccessiblePlan, один владелец движения, ожидание запускает таймеры, геометрия отдельно; Options → GameOptions → Config; множители движения/анимации без перемножения, M592: максимальная дальность лука из Balance.Weapons с боевыми ограничениями, независимо от экипировки цели. |
| Blocked wait combat M594 | `MonsterTargetPolicy` → `MonsterBlockedPursuit.IsWaiting`; `MonsterAIService.onDamaged` → `MonsterNavigationDispatch.NotifyDamage` → `MonsterBlockedPursuit` | Ожидание не запрещает обычную атаку; проверка цели/LOS сохраняется; событие урона от текущей цели или приближение будит навигацию без фонового поиска. Активная навигация и отдельная политика специальных действий сохраняются. |
| Rescue graph | `StudioRescueRoutes` → Place `Game1RescueRoutes` → `MonsterRescueGraph`; `rescue_route_store.py` → manifest | Place — источник координат графа; Database — зеркало; M590: Graph оркестрирует Topology → Routes → Entries → Paths → Exits; Connections — отдельные переходы только от свободных концов целой линии, с перепадом высоты ≤ Options routeConnectionHeight (2 studs по умолчанию), Sampling — 20/4 по длине линии; Segments — геометрия, Queries — per-search кэш и observer; Geometry — физика. Приоритет маршрута по цели, выхода внутри линии по высоте; каталог только метаданные |
| Trace | `MonsterNavigationTrace` | Studio Server Output, опциональный фильтр; без дополнительных кастов |
| Debug bootstrap | `ServiceCatalog` / `init.client` → `PublishedDebugAccess` | GP/AG/Buffer только Studio (compiled Draft только при Start in Hub), прочие debug только Studio или точный настроенный private DEV Place ID, включая compiled Runtime (M595); вне DEV Place исключены до require/start. Shared test contracts сохраняются. |
| Search cost M593 | `MonsterRescueSampling`, `MonsterExperimentalNavigation` | Свободная проекция без сетки, отсев линий вне радиуса, ожидание без callback/повторной записи таймера; остальное под профилированием. |

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
| Авторинг | `OptionsStore` → `options.json` → `GameOptionsRegistry` | `debugUi.startInHub` — boolean, default false; в обычном Studio ручной Hub доступен; в compiled Draft Studio GP/AG/Buffer только при Start in Hub |
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

## M600 · House interaction presentation

HouseSocketService реплицирует состояния и проверяет действие/дистанцию. HouseSocketPromptController использует прежний 10 Hz цикл; DoorInteractionRaycast связывает runtime proxy с визуальным мешем через HouseVisualAdapter. Вне USE-зоны луч не запускается. HudSvgIcons кэширует растеризованные SVG на клиенте. NpcDisplayNameFormatter работает только на границе UI.
