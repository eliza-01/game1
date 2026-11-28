# Навигация по документации game1

**Актуальный статус · 28.11.2026 · M645 (после M644):** владелец подтвердил функциональную приёмку MNPC в обычной одиночной игре («да, всё работает»). Monster и NPC используют общий entity-first lifecycle; FULL / LOD1 / UNLOADED, красный статический dummy при отсутствии опубликованного LOD1, реальная выгрузка рига и восстановление боя приняты. M645 синхронизирует FULL-порог и гистерезис через `MnpcLodPolicy`, учитывает фактическую дальность оружия каждого игрока, сохраняет 5 s hold и gameplay pins; сервер держит риг, если он нужен хотя бы одному игроку. Options → MNPC LOD → Server rig demand (`mnpcDemand.enabled`, default OFF; включено при проверке). Настройки FULL 100 / Unload 200 / hysteresis 10 studs: выход FULL после 110, возврат до 90 при отсутствии боевых исключений. Никаких консольных команд для настройки.

**M646–M647 · Overhead UI Pool: функциональная приёмка владельцем подтверждена («все нормально»). T05 выполнена; полная ресурсная A05 и количественные замеры остаются NOT_RUN.** Общий `MnpcOverheadController`, FULL-ready реестр, отдельная policy, общий ленивый пул и rebind `HealthBarView`. 8 свободных GUI, TTL 5 с, не более 4 новых GUI за общий тик 0,1 с; активного hard cap нет. Старые два контроллера удалены. M647: late mesh bounds и защита от старых folder callbacks исправлены, профильные тесты актуализированы; Overhead функционально принят; после M648: Hitbox Precompute → Priority Animation Prewarm → Player Attack Sampler. Не возвращаться к MNPC без конкретного дефекта. Настоящие LOD1, строгая изоляция Animator двух клиентов, teleport/debug-range edge cases и количественный профиль остаются открытыми. A07 — NOT_RUN, A08 — PASS только для одиночного M645. Profiler/стресс-тесты, Incremental Studio Preview и Socket & Door до переработки взаимодействий отложены. См. `docs/workflows/M646_OVERHEAD_UI_POOL_RU.md` и `docs/workflows/M647_OVERHEAD_INTEGRATION_RU.md`.

**M648 · Character Creation Prewarm (KBN-0039-T05): CODE_COMPLETE.** Два реальных default preview имеют приоритет; дополнительные опубликованные компоненты прогреваются в фоне после bootstrap (до 24 уникальных публикаций, 20 с, один занятый слот). Один ограниченный серверный каталог типизированных MeshPart без скелетов и общий клиентский typed cache. Дополнительных сборок и блокировки экрана нет. Native Studio/DEV/Mobile и измерения NOT_RUN. Следующий этап после функциональной приёмки — Hitbox Precompute, затем Priority Animation Prewarm и Player Attack Sampler. См. `docs/workflows/M648_CHARACTER_ASSET_PREWARM_RU.md`.

**M649 · Hitbox Asset Contract & Geometry Lifetime (KBN-0039-T01): CODE_COMPLETE, миграция открыта.** Сессионные готовые bounds и версионированный server-only registry проверяются до EditableMesh; вершины и веса освобождаются после последнего расчёта. Studio-only capture фактического oracle и Control Center compiler v1, реестр пустой до настоящей миграции. SAT/headshot/AI/MNPC не изменены; native parity, coverage и performance NOT_RUN. Следующий этап M651 — authoring workflow, реальные записи и приёмка, затем удаление migration oracle после полного покрытия. M648 native acceptance отдельно открыта. См. `docs/workflows/M649_HITBOX_ASSET_CONTRACT_RU.md`.

**M650 · Near-first Asset Loading (KBN-0037-T03): CODE_COMPLETE, native acceptance open.** Владелец M649 подтвердил попадания, но снова наблюдал дальние объекты раньше ближнего забора. Сервер строит единый порядок шаблонов Location/House по минимальной дистанции до поверхности от enabled SpawnLocation; клиент сохраняет существующую очередь с кольцами 32 studs от персонажа и ждёт typed mesh/image fetch перед atomic commit. Общий `AssetMeshPreloader` перенесён из Character Creation (один кэш, 4 общих слота, 1 фоновый), все потребители мигрированы. 25 s deadline на staged bundle, 30 s grace для неизвестной/ожидаемой зависимости, 4 s после staging для отсутствующей заявки; активный ближний прогресс удерживает кольцо. Failure/timeout — диагностируемый native fallback, не подтверждённая готовность. Native replication/CDN/GPU и SurfaceAppearance packs не гарантируются. Без новых Heartbeat/remotes, изменения LOD-порогов, AI, коллизий или manifest. M651 — отложенный Hitbox Asset Pipeline; затем Priority Animation Prewarm, Player Attack Sampler. M648 native acceptance и M649 migration parity открыты. См. `docs/workflows/M650_NEAR_ASSET_LOADING_RU.md`.

**История M627–M645:** подробная последовательность и контракты сохранены в MNPC LOD Spec и отдельных milestone-отчётах. Следующие записи M635–M637 описывают исторические состояния, не текущие задачи.

**M635: Studio Edit capture из зарегистрированного FULL template и опубликованного idle KeyframeSequence; общий Monster/NPC контракт, weapon mount, точная авторская keyframe около phase 0.35, снимок mesh/texture IDs, rest/posed bone frames и root-relative transforms. Снимок привязан к FULL/equipment/idle fingerprint; атомарная запись, предыдущий снимок сохраняется при ошибке. Не native Animator benchmark, не FBX/UV/bake; Studio NOT_RUN, Runtime FULL. Следующий этап M636 — геометрия, skinning и объединение атласов из снимка.**

**M636: общий Studio Edit capture фактических posed vertices/triangles/corner UV через EditableMesh (все веса, bind guard), local color atlas body/equipment с SHA-проверкой, UV remap/padding, M634 decimation/FBX round-trip и M633 staging/Atlas Registry. Capture & bake UI, captured idle provenance и stale-idle guard. Нативная геометрия, UV/масштаб, Blender/Cloud/Studio не приняты; material/PBR/alpha и bridge limits описаны. Runtime FULL, A07 NOT_RUN. Далее M637 — Studio import/alignment verification и runtime asset contract.** [M636](workflows/M636_MNPC_GEOMETRY_ATLAS_BAKE_RU.md).

**M637: Studio Edit read-only import published Model; detached single static MeshPart, native Mesh ID and root-space alignment from immutable M636 FBX. Bidirectional vertex-set fit with 24 proper axis rotations, uniform scale, translation; ambiguous/mismatch fails closed. Revision-pinned geometry alignment metadata in shared registry, no new Cloud upload or Place mutation. UV/color/native visual acceptance and runtime asset export/client LOD still open; Runtime FULL, A07 NOT_RUN.** См. `docs/workflows/M637_MNPC_IMPORT_ALIGNMENT_RU.md`.

## История оптимизации · P0 Performance

**Исторический порядок M613 (актуальная очередь выше):** Решение владельца 27.11.2026 (M613): временно отложить новые измерения и общий Performance Profiler. Сначала точечный рефактор критических модулей по подтверждённым дефектам статического аудита. Профилирование и итоговая приёмка остаются открытыми; не требовать baseline как блокирующую предпосылку рефактора. M613 — [общий пул sampler NPC/Monster](workflows/M613_ACTOR_SAMPLER_POOL_RU.md). M614: серверный Combat broad phase переведён на NativePartSpatialIndex (GetPartBoundsInBox по существующим RootCollider, без новых Parts/циклов); точные проверки и дальность лучей сохранены. 300 сравнений кандидатов с полным перебором в Lua mock; Studio/DEV и замеры открыты. Следующие потребители — LOD, AI и сокеты. [M615](workflows/M615_ACTOR_AI_SCHEDULER_RU.md): общий ActorAIScheduler для Monster/NPC с очередью deadlines; интервалы 0,1 с, Aggro 0,3 с и существующие боевые события сохранены. Experimental Navigation, Rescue Routes, BlockedWait и все таймеры не изменены. M616: локальный PlayerSpatialIndex (XZ, ячейка 32 studs, один ленивый снимок на пакет scheduler; порядок GetPlayers и точные policy сохранены). 1200 сравнений с полным обходом в Lua-модели; NPC остаются retaliation-only. M617: opt-in Adaptive AI LOD (Options → AI Performance): активные 0,1 с; агрессивный Idle сохраняет дедлайн Aggro 0,3 с, пассивный Idle и закреплённый NPC дома — контроль 0,3–2 с, событийное пробуждение до 0,1 с. Глубокий сон агрессивных отложен до гарантированного обнаружения входа в Aggro без потери реакции; навигация и боевые решения неизменны. Далее ComputeAsync budget (Legacy/NPC); Studio/DEV и замеры открыты.

M618: Native Navigation Budget только для Legacy Monster и NPC: FIFO, 2 одновременных ComputeAsync и 8 стартов/с (Options → AI Performance; диапазоны 1–8 и 1–30). Experimental Navigation и Rescue Routes не участвуют. Результат применяется только в текущем шаге навигации после проверки актуальности, ожидание не считается физическим застреванием. Studio/DEV и измерения открыты. [M618](workflows/M618_NAVIGATION_BUDGET_RU.md).

M619: Runtime LOD этап 1 — StaticPlacementIndex (BVH по 3D snapshot pivot и hide+hysteresis), LocationLodCandidates (локальная область + прежние desired/actual до выгрузки). Только реальные переходы сортируются; при равной дистанции — порядок manifest. Policy, интервалы, fallback, сборка, HouseVisualAdapter, Studio Preview, server physics и AI сохранены. Composite effects пока обслуживаются отдельным проходом; threshold queue, cache, incremental budget и Real Estate ещё открыты. Studio/DEV и замеры не выполнены. [ТЗ Runtime LOD](workflows/RUNTIME_LOD_STREAMING_REFACTOR_SPEC_RU.md).

M620: Runtime LOD этап 2 — LodThresholdCache (запас до порогов ±h, смещение от последнего resolve, точные границы и смена камеры) и LodTransitionQueue (одна заявка на placement, отмена/замена, сортировка только при изменении приоритета). При неподвижной камере BVH и стабильные дистанции не пересчитываются; fallback/proxy/effects продолжают обслуживаться. Aging 8 ticks; тяжёлая просроченная Location-заявка может получить полный бюджет на чётном tick, нечётный сохраняет резерв House. Policy, интервал и визуальный контракт сохранены. Кэш готовности, порционная сборка, Real Estate и Studio/DEV/профиль открыты.

M621: Runtime LOD этап 3 — LodPrototypeCache по Instance identity/generation/variant/contract: event-driven missing/incomplete/ready/invalid, bounded retry (2), поздний template folder/Ready, immutable assembly metadata/bounds, FULL component-name map. Location streamer больше не ждёт cache folder 30 с и не выключается при его позднем появлении; stale prototype generation rebuilds atomically, per-placement failedAssemblies остаётся generation-aware. House LOD1 uses shared cache, но spatial index / общая queue / budget Real Estate ещё не интегрированы. M619–M621 код и Lua-oracle проверки готовы; Studio/DEV/профиль открыты. [ТЗ Runtime LOD](workflows/RUNTIME_LOD_STREAMING_REFACTOR_SPEC_RU.md).

M622: Runtime Location stage 4 — `LodAssemblyJob` / `LodRuntimeWork`: detached incremental assembly (single mesh, multipart LOD, composite FULL); 12 build + 8 cleanup operation groups/frame, separate atomic commit reservation up to 132 groups, 16 queue checks/category/frame, one active job (≤64 visual meshes), at most two retired bundles. Commit revalidates proxy identity/current CFrames, preserves previous visual until swap and keeps effects tied to actual. Desired/prototype generation/root changes cancel staging; cleanup is incremental. Old Location cost clamp removed. House keeps independent 8/tick reservation pending stage 5; Studio Preview multipart drains the same job synchronously. Counts are not a hard CPU deadline; native streaming, effect traversal and Studio/DEV/Mobile profiling remain acceptance items. T03/A03 open.

M623: Real Estate stage 5 — every house part is a record in the common static BVH, threshold cache, aging transition queue and `LodRuntimeWork`. House influence uses a conservative sphere around scaled snapshot bounds; exact policy remains `ResolveHouse` with surface distance and per-part hide/LOD1. FULL acquisition (`HouseMeshRequests`) has four combined in-flight/ready slots, 15 s retry, generation and moving-proxy identity checks; async completion cannot publish. Detached result enters the common job, old actual survives until atomic commit, failure or absent preferred prototype preserves old actual; cold missing LOD1 can fall back to FULL. Missing unpublished part LOD1 retains FULL→UNLOADED. Shared unload/retirement handles committed geometry. Discard of a stale raw async MeshPart is immediate (bounded by four slots), outside the staged assembly counters. Only active moving parts are followed each frame; lost proxy detaches the owned mesh and removes DoorRaycast binding, stream-in rebinds using current CFrame and appearance. Static active parts refresh proxy color/material during local observation. Server physics, manifest, sockets and authority unchanged. Lua mocked lifecycle and mixed spatial/async oracles; actual Studio/DEV/Mobile, House5 interactions/two-client and profiling remain NOT_RUN. Preview still synchronous; T03/A03 open.

M624: opt-in Runtime LOD diagnostics (authorized Studio/DEV debug dock, PC/mobile), bounded capture with heartbeat/callback elapsed, queue/desired→actual latency, local candidates, sorts/cache/async/work counters, peaks and client memory at boundaries; no telemetry or new scheduler. Studio Preview teardown now disconnects Workspace subscriptions, restores authored visibility and destroys local folder. Authoring assembly remains synchronous; composite/tagged passes are measured, not eliminated. Actual Studio/DEV/PC/Mobile, two-client and A/B acceptance NOT_RUN; T03/A03/A06 remain open. See docs/workflows/M624_RUNTIME_LOD_ACCEPTANCE_RU.md.

M625: `LocationCompositeEffects` replaces the periodic global composite pass with shared manifest-path prefix subscriptions (`ChildAdded/Removed`) and scoped root `DescendantAdded/Removing`. Initial discovery once per resident root; actual LOD commit/native detach controls cached effects, not desired. Hidden authored Enabled state is restored on show, stream-out and Stop; late descendants and replacement roots are handled. Compiled paths are static (runtime rename unsupported). Observable external Enabled=true while hidden is suppressed and retained; false writes indistinguishable from the local false cannot be observed without an authoritative separate state, so dynamic server-controlled effects are not newly opted in. No new Heartbeat/remotes/manifest changes; doors, rotors, House effects and tagged visual pass unchanged. Owner deferred incremental Studio Preview as optional tooling. Real Studio/DEV/physical Mobile and A/B acceptance remain NOT_RUN; T03/A03/A06 open.

M626 · Near-first Runtime LOD: после публикации M625 владелец подтвердил обычную работу без заметного ухудшения, но на слабом телефоне ближние ограждения догружались позже дальних домов. `LodLoadPriority` использует позицию HumanoidRootPart игрового персонажа (камера в меню/при отсутствии root), минимальную surface distance по authored bounds Location/House, кольца по 32 studs. Camera-based visibility/LOD thresholds и пространственный индекс не меняются. В общей очереди: unload отдельно, затем ближайшее кольцо, cold перед upgrade, aging только внутри класса и кольца. Ближайшее незавершённое кольцо ограничивает admission сборок даже при ещё отсутствующем template/proxy; 4 секунды без прогресса разрешают следующие кольца, поздний ассет остаётся приоритетным. При respawn/телепорте порядок обновляется без ожидания очередного 0,25 s sample; активная недопустимая сборка отменяется. Четыре async FULL slots и прежние бюджеты сохранены; при нехватке слотов для ближнего FULL разрешено освободить один готовый дальний detached result, не отменяя in-flight вызов. Без новых Heartbeat, массового PreloadAsync, remotes, изменений серверной физики, манифеста и Preview. Порядок управляет клиентской сборкой/публикацией и house FULL requests, а не гарантирует порядок native Roblox replication, CDN fetch или GPU render. Профилирование/стресс-тесты отложены по решению владельца; ближайшая практическая проверка — обычный вход в игру на слабом телефоне. T03/A03/A06 формально открыты.




**Решение владельца проекта от 27.11.2026:** закрытие всего цикла оптимизации M605 — высший текущий приоритет. Не начинать новые игровые механики и расширение контента до закрытия KBN-0035–0039. Исключение — исправления блокирующих дефектов и работа, необходимая для приёмки оптимизации; старые карточки не отменяются.

Читать сначала [действующее ТЗ](spec/CURRENT_PROJECT_SPEC_RU.md#текущий-приоритет--performance-p0), [архитектурные ограничения](architecture/CURRENT_ARCHITECTURE_RU.md#текущий-приоритет--performance-p0) и [очередь Kanban](kanban/README.md#текущий-фокус--27112026--performance-review-m605). Порядок: [0035 Profiler](kanban/specs/KBN-0035.md) → [0036 Spatial Index](kanban/specs/KBN-0036.md) → [0037 Client](kanban/specs/KBN-0037.md) → [0038 Server](kanban/specs/KBN-0038.md) → [0039 Asset Pipeline](kanban/specs/KBN-0039.md). P1 у последней карточки — относительный порядок внутри обязательного цикла, не повод отложить её.

По решению владельца сначала M607 · [Native Rigid Equipment](workflows/M607_RIGID_EQUIPMENT_RU.md) (KBN-0037-T02); исторически планировалось вернуться к Profiler и baseline (отложено владельцем), затем небольшие проверяемые патчи с измерениями до/после. Статический аудит не является измерением. CODE_COMPLETE не равен DONE: обязательны профильные тесты, Studio/DEV и физический телефон, evidence в Kanban. При новом диалоге продолжать первую незакрытую задачу по зависимостям; не объявлять цикл завершённым до приёмки всех пяти карточек. M607 не прошёл визуальную приёмку: отрыв волос/оружия в прыжке, меч NPC смещён в Idle. M608 также не прошёл визуальную приёмку. M609 · [Rigid Parent Frame](workflows/M609_RIGID_PARENT_FRAME_RU.md) — восстановление исходного контракта сокета; владелец подтвердил работу в Runtime и на физическом телефоне. KBN-0037-T02 выполнен, полная матрица регрессий и измерения Physics/CPU остаются открыты. **Исторически следующей задачей был Profiler M610; текущий порядок M613 указан выше.** Базу для дальнейших работ снимаем на M609; сравнение креплений с M605 — отдельный A/B в одинаковых условиях. Остальные этапы обязательны.

**M610 · [Network Motion](workflows/M610_NETWORK_MOTION_RU.md):** первый сценарий Profiler, KBN-0035 IN_PROGRESS. Сначала получить синхронную запись неравномерного движения двух игроков в Studio/DEV. Причина ещё не подтверждена, игровой контроллер не изменён.

**M612 · [Remote Player Attack](workflows/M612_REMOTE_PLAYER_ATTACK_RU.md):** блокирующее исправление видимости атак других игроков; Studio/DEV-приёмка открыта. Profiler и Spatial Index остаются приоритетом.

**M611 · [Network Motion Owner](workflows/M611_NETWORK_MOTION_OWNER_RU.md):** измерения M610 подтвердили разброс позиционной скорости; автоматический третий замер на локальном клиенте цели, причина ещё открыта.

**Настройка Place · 27.11.2026:** по решению владельца `Workspace.ImprovedPhysicsReplication = Enabled` пока оставляем включённой. Это временная конфигурация, не подтверждённое исправление сетевого движения; учитывать при сравнениях Studio/DEV и Runtime Build. [Контекст замера](workflows/M611_NETWORK_MOTION_OWNER_RU.md).

**Последняя сверка Monster AI / Runtime / Debug:** 27 ноября 2026, M595 (дамп M592 + патчи). Debug: [контракт DEV Place](spec/CURRENT_PROJECT_SPEC_RU.md#m595--debug-в-закрытом-dev-place). [Аудит и приёмка](workflows/M593_MONSTER_RUNTIME_AUDIT_RU.md). Остальной gameplay — M570/M571. Для остальных доменов сохраняются M447 Mechanics audit и M439 общий справочник. Основной подробный список M188–M189 ниже является историческим срезом соответствующих workflow.
**Правило:** читать актуальные контракты прежде, чем исторические milestone-отчёты. Старые тексты оставлены для причин, миграций и отладки, **не** как одновременно действующие ТЗ.

**M602 · Движение:** [camera-relative backpedal](workflows/M602_CAMERA_BACKPEDAL_RU.md).

**M601 · Оружие:** [верхний правый угол и Database binding Newbie Slayer](workflows/M601_WEAPON_CORNER_RU.md).

**M605 · HUD и прогрев:** [контракт и проверка](workflows/M605_HUD_ANIMATION_PREWARM_RU.md).

**M600 · Дом и NPC:** [иконки замка/двери, наведение, имена NPC](workflows/M600_HOUSE_INTERACTION_ICONS_RU.md).

**M597–M599 · Управление и HUD:** [удержание, мобильные кнопки, оружие](workflows/M597_MOBILE_HOLD_HUD_RU.md).

**Character Creation M596:** [Character Roster — слоты, миграция и приёмка](workflows/M596_CHARACTER_ROSTER_RU.md).

## Наиболее актуальная точка входа

- **[MNPC LOD / M645](workflows/MNPC_LOD_SPEC_RU.md)** — принятый одиночный runtime, результаты и оставшиеся gates.
- **[Kanban KBN-0037](kanban/specs/KBN-0037.md)** — M646–M647 функционально приняты; M648 Character Creation Prewarm, код готов.

- **[M570 · Gameplay infrastructure](workflows/M570_GAMEPLAY_INFRASTRUCTURE_RU.md)** — актуальный workflow Database, Spawn Zones, Death Chase/Home Leash, Rescue Routes, навигация и диагностика MONNAV. Приоритет над историческими M541 и M560–M565 в изменённых контрактах. [Kanban](kanban/README.md): KBN-0032 и KBN-0033, приёмка открыта.

- **[M541 · Hub, World GP и XP](workflows/M541_HUB_WORLD_PROGRESSION_RU.md)** — текущий стенд 384 × 384, Start in Hub, временная прокачка, расстановка, серверные границы, Studio-чеклист. Заменяет ранние описания дорожек и полного запрета GP-наград.
- **[Design · KBN-0031](kanban/specs/KBN-0031.md)** — закреплённая карточка, шесть территорий, бестиарий, 30 целей, эмоции, навыки без классов, 9–12 ч как цель. [M539 · Database names и World GP](workflows/M539_DESIGN_WORLD_ZONES_RU.md) — историческая реализация с последующими изменениями M540/M541.
- **[M531 · Guided Combat](workflows/M531_GUIDED_COMBAT_RU.md)**, **[M532 · Headshot/Export](workflows/M532_HEADSHOT_GP_RECOVERY_RU.md)**, **[M533 · Status Effects](workflows/M533_TARGETED_STATUS_EFFECTS_RU.md)**, **[M534 · male GP animations](workflows/M534_MALE_GP_WEAPON_ANIMATIONS_RU.md)** — действующие с уточнениями в ТЗ. Guided остаётся без наград.

- **[Kanban · историческая сверка первых 17 карточек](kanban/STATUS_2026-11-22_M439.md)** — проверка источников и открытая Studio/Android-приёмка; [спецификации карточек](kanban/README.md).
- **[Skills · M529: каталог и Skilled Monsters](workflows/M529_SKILLS_AND_SKY_TEST_RU.md)** — формулы downgrade, runtime и высотный стенд.
- **[Balance · M527: ranged](workflows/M527_RANGED_RETREAT_BALANCE_RU.md)** — HP, ATK, AS и отступление.
- **[Balance · M526: melee/ranged](workflows/M526_MONSTER_TYPES_RU.md)** — типы, дальность, компактный стенд.
- **[Balance · M525: парные мечи](workflows/M525_DUALSWORDS_RU.md)** — два попадания и рецепт B/B+.
- **[Balance · M524: критический шанс и урон](workflows/M524_CRITICAL_BALANCE_RU.md)** — индивидуальные значения, предел и тестовые бонусы.
- **[Balance · M523: скорость и урон оружия](workflows/M523_INTERLUDE_WEAPON_BALANCE_RU.md)** — действующие формулы и адаптация лука без перезарядки.
- **[Balance · план следующего этапа](kanban/BALANCE_PLAN_RU.md)** — KBN-0018–0024, актуальный melee и 15-минутная прогрессия (PROPOSED).
- **[Текущее ТЗ](spec/CURRENT_PROJECT_SPEC_RU.md)** и **[Архитектурная карта](architecture/CURRENT_ARCHITECTURE_RU.md)** — текущие приоритеты и реальные границы сервера, клиента, систем авторинга.
- **[Mechanics · аудит всех четырёх разделов M447](workflows/MECHANICS_RUNTIME_GAPS_M447_RU.md)** — House/NPC/Monster/Character, незавершённые механики, persistence, Runtime/Studio критерии; [как устроен каталог](workflows/MECHANICS_HOUSE_CATALOG_M436_RU.md).
- **[Камин и костёр · M442](workflows/CAMPFIRE_AND_FIREPLACE_M442_RU.md)** — единая механика готовки, условный дым, мобильный/ПК dock, HUD и редактируемые параметры.
- Для LOD использовать текущие контрактные модули `location_streaming_config.py`, `LocationWorldStreamer.luau`, `lod_studio_preview.py`, а не общие пороги из исторического M355.

## 1. Действующие документы

| Документ | Зачем читать | Статус |
| --- | --- | --- |
| [M230 — Legacy Placement Compatibility](workflows/REAL_ESTATE_PLACEMENT_LEGACY_COMPAT_M230_RU.md) | Place и Place all доступны для старых Model-pivot биндов без повторного Bind; новые бинды используют точный house pivot | **CURRENT · STUDIO SMOKE REQUIRED** |
| [M229 — Real Estate Placement rotation](workflows/REAL_ESTATE_PLACEMENT_ROTATION_M229_RU.md) | Bind измеряет author house pivot, Place выравнивает по тому же anchor; сохранение точного house pivot для новых Bind; прежний запрет legacy Place отменён M230 | **CURRENT CAPTURE / HISTORICAL LEGACY POLICY** |
| [M228 — Combat reticle primary melee](workflows/COMBAT_RETICLE_PRIMARY_MELEE_M228_RU.md) | Исторический контракт до M358/M360; актуальный melee — серверный сектор и один HitEnd, headshot только допустимой цели | **HISTORICAL · SUPERSEDED BY M358/M360** |
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

- [**M449 · Options → Sockets, постоянные USE/AIM зоны**](workflows/SOCKET_RANGES_OPTIONS_M449_RU.md) — House/Campfire, валидация и HS Studio Debug override.

- [M531 — Guided Combat Analytics, RunSpeed, касты и VFX](workflows/M531_GUIDED_COMBAT_RU.md).

- [M532 — независимый melee Headshot, GP Export/Skip/Retry, timing-only fallback](workflows/M532_HEADSHOT_GP_RECOVERY_RU.md).

- [M533 — Targeted Status Effects](workflows/M533_TARGETED_STATUS_EFFECTS_RU.md).

- [M639 · MNPC Runtime demand](workflows/M639_MNPC_RUNTIME_DEMAND_RU.md) — актуальный opt-in серверный lifecycle M645; одиночная приёмка A08 PASS, полная A07 открыта.
- [M638 · MNPC Runtime LOD / red dummy](workflows/M638_MNPC_RUNTIME_LOD_RU.md) — визуальная интеграция, native isolation открыта.
