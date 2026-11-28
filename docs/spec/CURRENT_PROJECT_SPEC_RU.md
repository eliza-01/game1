# game1 — действующее техническое задание

**Актуальный статус · 28.11.2026 · M645 (после M644):** владелец подтвердил функциональную приёмку MNPC в обычной одиночной игре («да, всё работает»). Monster и NPC используют общий entity-first lifecycle; FULL / LOD1 / UNLOADED, красный статический dummy при отсутствии опубликованного LOD1, реальная выгрузка рига и восстановление боя приняты. M645 синхронизирует FULL-порог и гистерезис через `MnpcLodPolicy`, учитывает фактическую дальность оружия каждого игрока, сохраняет 5 s hold и gameplay pins; сервер держит риг, если он нужен хотя бы одному игроку. Options → MNPC LOD → Server rig demand (`mnpcDemand.enabled`, default OFF; включено при проверке). Настройки FULL 100 / Unload 200 / hysteresis 10 studs: выход FULL после 110, возврат до 90 при отсутствии боевых исключений. Никаких консольных команд для настройки.

**M646–M647 · Overhead UI Pool: функциональная приёмка владельцем подтверждена («все нормально»). T05 выполнена; полная ресурсная A05 и количественные замеры остаются NOT_RUN.** Общий `MnpcOverheadController`, FULL-ready реестр, отдельная policy, общий ленивый пул и rebind `HealthBarView`. 8 свободных GUI, TTL 5 с, не более 4 новых GUI за общий тик 0,1 с; активного hard cap нет. Старые два контроллера удалены. M647: late mesh bounds и защита от старых folder callbacks исправлены, профильные тесты актуализированы; Overhead функционально принят; после M648: Hitbox Precompute → Priority Animation Prewarm → Player Attack Sampler. Не возвращаться к MNPC без конкретного дефекта. Настоящие LOD1, строгая изоляция Animator двух клиентов, teleport/debug-range edge cases и количественный профиль остаются открытыми. A07 — NOT_RUN, A08 — PASS только для одиночного M645. Profiler/стресс-тесты, Incremental Studio Preview и Socket & Door до переработки взаимодействий отложены. См. `docs/workflows/M646_OVERHEAD_UI_POOL_RU.md` и `docs/workflows/M647_OVERHEAD_INTEGRATION_RU.md`.

**M648 · Character Creation Prewarm (KBN-0039-T05): CODE_COMPLETE.** Два реальных default preview имеют приоритет; дополнительные опубликованные компоненты прогреваются в фоне после bootstrap (до 24 уникальных публикаций, 20 с, один занятый слот). Один ограниченный серверный каталог типизированных MeshPart без скелетов и общий клиентский typed cache. Дополнительных сборок и блокировки экрана нет. Native Studio/DEV/Mobile и измерения NOT_RUN. Следующий этап после функциональной приёмки — Hitbox Precompute, затем Priority Animation Prewarm и Player Attack Sampler. См. `docs/workflows/M648_CHARACTER_ASSET_PREWARM_RU.md`.

**M649 · Hitbox Asset Contract & Geometry Lifetime (KBN-0039-T01): CODE_COMPLETE, миграция открыта.** Сессионные готовые bounds и версионированный server-only registry проверяются до EditableMesh; вершины и веса освобождаются после последнего расчёта. Studio-only capture фактического oracle и Control Center compiler v1, реестр пустой до настоящей миграции. SAT/headshot/AI/MNPC не изменены; native parity, coverage и performance NOT_RUN. Следующий этап M651 — authoring workflow, реальные записи и приёмка, затем удаление migration oracle после полного покрытия. M648 native acceptance отдельно открыта. См. `docs/workflows/M649_HITBOX_ASSET_CONTRACT_RU.md`.

**M650 · Near-first Asset Loading (KBN-0037-T03): CODE_COMPLETE, native acceptance open.** Владелец M649 подтвердил попадания, но снова наблюдал дальние объекты раньше ближнего забора. Сервер строит единый порядок шаблонов Location/House по минимальной дистанции до поверхности от enabled SpawnLocation; клиент сохраняет существующую очередь с кольцами 32 studs от персонажа и ждёт typed mesh/image fetch перед atomic commit. Общий `AssetMeshPreloader` перенесён из Character Creation (один кэш, 4 общих слота, 1 фоновый), все потребители мигрированы. 25 s deadline на staged bundle, 30 s grace для неизвестной/ожидаемой зависимости, 4 s после staging для отсутствующей заявки; активный ближний прогресс удерживает кольцо. Failure/timeout — диагностируемый native fallback, не подтверждённая готовность. Native replication/CDN/GPU и SurfaceAppearance packs не гарантируются. Без новых Heartbeat/remotes, изменения LOD-порогов, AI, коллизий или manifest. M651 — отложенный Hitbox Asset Pipeline; затем Priority Animation Prewarm, Player Attack Sampler. M648 native acceptance и M649 migration parity открыты. См. `docs/workflows/M650_NEAR_ASSET_LOADING_RU.md`.

**История M627–M645:** подробная последовательность и контракты сохранены в MNPC LOD Spec и отдельных milestone-отчётах. Следующие записи M635–M637 описывают исторические состояния, не текущие задачи.

**M635: Studio Edit capture из зарегистрированного FULL template и опубликованного idle KeyframeSequence; общий Monster/NPC контракт, weapon mount, точная авторская keyframe около phase 0.35, снимок mesh/texture IDs, rest/posed bone frames и root-relative transforms. Снимок привязан к FULL/equipment/idle fingerprint; атомарная запись, предыдущий снимок сохраняется при ошибке. Не native Animator benchmark, не FBX/UV/bake; Studio NOT_RUN, Runtime FULL. Следующий этап M636 — геометрия, skinning и объединение атласов из снимка.**

**M636: общий Studio Edit capture фактических posed vertices/triangles/corner UV через EditableMesh (все веса, bind guard), local color atlas body/equipment с SHA-проверкой, UV remap/padding, M634 decimation/FBX round-trip и M633 staging/Atlas Registry. Capture & bake UI, captured idle provenance и stale-idle guard. Нативная геометрия, UV/масштаб, Blender/Cloud/Studio не приняты; material/PBR/alpha и bridge limits описаны. Runtime FULL, A07 NOT_RUN. Далее M637 — Studio import/alignment verification и runtime asset contract.**

**M637: Studio Edit read-only import published Model; detached single static MeshPart, native Mesh ID and root-space alignment from immutable M636 FBX. Bidirectional vertex-set fit with 24 proper axis rotations, uniform scale, translation; ambiguous/mismatch fails closed. Revision-pinned geometry alignment metadata in shared registry, no new Cloud upload or Place mutation. UV/color/native visual acceptance and runtime asset export/client LOD still open; Runtime FULL, A07 NOT_RUN.** См. `docs/workflows/M637_MNPC_IMPORT_ALIGNMENT_RU.md`.


**Исходный срез:** `game1_diag_2026-10-30_13-52-46.zip`, 30 октября 2026. **Редакторская сверка действующих контрактов:** 22.11.2026, M438a/M439; детали в актуальном дополнении ниже. Старые разделы отражают этапы внедрения.
**Статус:** действующий живой документ. Последняя сверка Monster Navigation / Runtime / Debug: M594 на базе свежего дампа M592 `game1_diag_2026-11-27_06-32-10.zip`. Прочие gameplay-домены сохраняют предыдущие сверки.
**Проект:** `game1`, самостоятельный Roblox Place / основа MMO.
**Важное различие:** «реализовано в исходниках» не означает «проверено в Roblox Studio Play / production».
**История:** [исходное ТЗ Milestone 1](../history/milestone-1/PROJECT_SPEC_MILESTONE_1_RU.md) описывает запуск проекта, **не** текущее требование к единственному разделу Characters.

## Текущий приоритет · Performance P0

**Исторический порядок M613 (актуальная очередь выше):** Решение владельца 27.11.2026 (M613): временно отложить новые измерения и общий Performance Profiler. Сначала точечный рефактор критических модулей по подтверждённым дефектам статического аудита. Профилирование и итоговая приёмка остаются открытыми; не требовать baseline как блокирующую предпосылку рефактора. M613 — [общий пул sampler NPC/Monster](../workflows/M613_ACTOR_SAMPLER_POOL_RU.md). M614: серверный Combat broad phase переведён на NativePartSpatialIndex (GetPartBoundsInBox по существующим RootCollider, без новых Parts/циклов); точные проверки и дальность лучей сохранены. 300 сравнений кандидатов с полным перебором в Lua mock; Studio/DEV и замеры открыты. Следующие потребители — LOD, AI и сокеты. [M615](../workflows/M615_ACTOR_AI_SCHEDULER_RU.md): общий ActorAIScheduler для Monster/NPC с очередью deadlines; интервалы 0,1 с, Aggro 0,3 с и существующие боевые события сохранены. Experimental Navigation, Rescue Routes, BlockedWait и все таймеры не изменены. M616: локальный PlayerSpatialIndex (XZ, ячейка 32 studs, один ленивый снимок на пакет scheduler; порядок GetPlayers и точные policy сохранены). 1200 сравнений с полным обходом в Lua-модели; NPC остаются retaliation-only. M617: opt-in Adaptive AI LOD (Options → AI Performance): активные 0,1 с; агрессивный Idle сохраняет дедлайн Aggro 0,3 с, пассивный Idle и закреплённый NPC дома — контроль 0,3–2 с, событийное пробуждение до 0,1 с. Глубокий сон агрессивных отложен до гарантированного обнаружения входа в Aggro без потери реакции; навигация и боевые решения неизменны. Далее ComputeAsync budget (Legacy/NPC); Studio/DEV и замеры открыты.

M618: Native Navigation Budget только для Legacy Monster и NPC: FIFO, 2 одновременных ComputeAsync и 8 стартов/с (Options → AI Performance; диапазоны 1–8 и 1–30). Experimental Navigation и Rescue Routes не участвуют. Результат применяется только в текущем шаге навигации после проверки актуальности, ожидание не считается физическим застреванием. Studio/DEV и измерения открыты. [M618](../workflows/M618_NAVIGATION_BUDGET_RU.md).

M619: Runtime LOD этап 1 — StaticPlacementIndex (BVH по 3D snapshot pivot и hide+hysteresis), LocationLodCandidates (локальная область + прежние desired/actual до выгрузки). Только реальные переходы сортируются; при равной дистанции — порядок manifest. Policy, интервалы, fallback, сборка, HouseVisualAdapter, Studio Preview, server physics и AI сохранены. Composite effects пока обслуживаются отдельным проходом; threshold queue, cache, incremental budget и Real Estate ещё открыты. Studio/DEV и замеры не выполнены. [ТЗ Runtime LOD](../workflows/RUNTIME_LOD_STREAMING_REFACTOR_SPEC_RU.md).

M620: Runtime LOD этап 2 — LodThresholdCache (запас до порогов ±h, смещение от последнего resolve, точные границы и смена камеры) и LodTransitionQueue (одна заявка на placement, отмена/замена, сортировка только при изменении приоритета). При неподвижной камере BVH и стабильные дистанции не пересчитываются; fallback/proxy/effects продолжают обслуживаться. Aging 8 ticks; тяжёлая просроченная Location-заявка может получить полный бюджет на чётном tick, нечётный сохраняет резерв House. Policy, интервал и визуальный контракт сохранены. Кэш готовности, порционная сборка, Real Estate и Studio/DEV/профиль открыты.

M621: Runtime LOD этап 3 — LodPrototypeCache keyed by Instance identity, generation, variant and component contract. Event-driven missing/incomplete/ready/invalid; bounded retry 2; cache-folder/Ready late arrival; frozen immutable assembly metadata/bounds; FULL component map. Location no longer waits 30s for the template folder or disables visual streaming when it is late. Stale generations rebuild atomically; HouseVisualAdapter shares readiness cache for LOD1 replacements. M619–M621 code and Lua-oracle tests pass; incremental budget, House spatial/queue integration and Studio/DEV/profile acceptance remain open. [Runtime LOD ТЗ](../workflows/RUNTIME_LOD_STREAMING_REFACTOR_SPEC_RU.md).

M622: Runtime Location stage 4 — `LodAssemblyJob` / `LodRuntimeWork`: detached incremental assembly (single mesh, multipart LOD, composite FULL); 12 build + 8 cleanup operation groups/frame, separate atomic commit reservation up to 132 groups, 16 queue checks/category/frame, one active job (≤64 visual meshes), at most two retired bundles. Commit revalidates proxy identity/current CFrames, preserves previous visual until swap and keeps effects tied to actual. Desired/prototype generation/root changes cancel staging; cleanup is incremental. Old Location cost clamp removed. House keeps independent 8/tick reservation pending stage 5; Studio Preview multipart drains the same job synchronously. Counts are not a hard CPU deadline; native streaming, effect traversal and Studio/DEV/Mobile profiling remain acceptance items. T03/A03 open.

M623: Real Estate stage 5 — every house part is a record in the common static BVH, threshold cache, aging transition queue and `LodRuntimeWork`. House influence uses a conservative sphere around scaled snapshot bounds; exact policy remains `ResolveHouse` with surface distance and per-part hide/LOD1. FULL acquisition (`HouseMeshRequests`) has four combined in-flight/ready slots, 15 s retry, generation and moving-proxy identity checks; async completion cannot publish. Detached result enters the common job, old actual survives until atomic commit, failure or absent preferred prototype preserves old actual; cold missing LOD1 can fall back to FULL. Missing unpublished part LOD1 retains FULL→UNLOADED. Shared unload/retirement handles committed geometry. Discard of a stale raw async MeshPart is immediate (bounded by four slots), outside the staged assembly counters. Only active moving parts are followed each frame; lost proxy detaches the owned mesh and removes DoorRaycast binding, stream-in rebinds using current CFrame and appearance. Static active parts refresh proxy color/material during local observation. Server physics, manifest, sockets and authority unchanged. Lua mocked lifecycle and mixed spatial/async oracles; actual Studio/DEV/Mobile, House5 interactions/two-client and profiling remain NOT_RUN. Preview still synchronous; T03/A03 open.

M624: opt-in Runtime LOD diagnostics (authorized Studio/DEV debug dock, PC/mobile), bounded capture with heartbeat/callback elapsed, queue/desired→actual latency, local candidates, sorts/cache/async/work counters, peaks and client memory at boundaries; no telemetry or new scheduler. Studio Preview teardown now disconnects Workspace subscriptions, restores authored visibility and destroys local folder. Authoring assembly remains synchronous; composite/tagged passes are measured, not eliminated. Actual Studio/DEV/PC/Mobile, two-client and A/B acceptance NOT_RUN; T03/A03/A06 remain open. See docs/workflows/M624_RUNTIME_LOD_ACCEPTANCE_RU.md.

M625: `LocationCompositeEffects` replaces the periodic global composite pass with shared manifest-path prefix subscriptions (`ChildAdded/Removed`) and scoped root `DescendantAdded/Removing`. Initial discovery once per resident root; actual LOD commit/native detach controls cached effects, not desired. Hidden authored Enabled state is restored on show, stream-out and Stop; late descendants and replacement roots are handled. Compiled paths are static (runtime rename unsupported). Observable external Enabled=true while hidden is suppressed and retained; false writes indistinguishable from the local false cannot be observed without an authoritative separate state, so dynamic server-controlled effects are not newly opted in. No new Heartbeat/remotes/manifest changes; doors, rotors, House effects and tagged visual pass unchanged. Owner deferred incremental Studio Preview as optional tooling. Real Studio/DEV/physical Mobile and A/B acceptance remain NOT_RUN; T03/A03/A06 open.

M626 · Near-first Runtime LOD: после публикации M625 владелец подтвердил обычную работу без заметного ухудшения, но на слабом телефоне ближние ограждения догружались позже дальних домов. `LodLoadPriority` использует позицию HumanoidRootPart игрового персонажа (камера в меню/при отсутствии root), минимальную surface distance по authored bounds Location/House, кольца по 32 studs. Camera-based visibility/LOD thresholds и пространственный индекс не меняются. В общей очереди: unload отдельно, затем ближайшее кольцо, cold перед upgrade, aging только внутри класса и кольца. Ближайшее незавершённое кольцо ограничивает admission сборок даже при ещё отсутствующем template/proxy; 4 секунды без прогресса разрешают следующие кольца, поздний ассет остаётся приоритетным. При respawn/телепорте порядок обновляется без ожидания очередного 0,25 s sample; активная недопустимая сборка отменяется. Четыре async FULL slots и прежние бюджеты сохранены; при нехватке слотов для ближнего FULL разрешено освободить один готовый дальний detached result, не отменяя in-flight вызов. Без новых Heartbeat, массового PreloadAsync, remotes, изменений серверной физики, манифеста и Preview. Порядок управляет клиентской сборкой/публикацией и house FULL requests, а не гарантирует порядок native Roblox replication, CDN fetch или GPU render. Профилирование/стресс-тесты отложены по решению владельца; ближайшая практическая проверка — обычный вход в игру на слабом телефоне. T03/A03/A06 формально открыты.



Решение владельца 27.11.2026 (M606a): весь цикл оптимизации из [Kanban KBN-0035–0039](../kanban/README.md#текущий-фокус--27112026--performance-review-m605) обязателен до возобновления новых механик и расширения контента. Допускаются исправления блокирующих дефектов и работы, необходимые для приёмки. Старые задачи сохраняются; приоритет внутри цикла не исключает ни одну карточку.

| Порядок | Обязательный результат | Спецификация |
| --- | --- | --- |
| 1 | Общий выключенный по умолчанию Performance Profiler; MicroProfiler, ограниченные агрегаты и воспроизводимый baseline CPU/GPU/RAM/сети | [KBN-0035](../kanban/specs/KBN-0035.md) |
| 2 | Переиспользуемый Spatial Index с локальными запросами, корректным lifecycle и проверкой эквивалентности | [KBN-0036](../kanban/specs/KBN-0036.md) |
| 3 | Строгий бюджет animation sampler Monster/NPC, native RigidConstraint для волос/оружия, бюджет Runtime LOD, локальные сокеты и кэш door meshes, Overhead UI Pool | [KBN-0037](../kanban/specs/KBN-0037.md) |
| 4 | Spatial broad phase melee/bow/headshot, AI LOD, локальный поиск агро, общий бюджет навигации | [KBN-0038](../kanban/specs/KBN-0038.md) |
| 5 | Предрасчёт bone-local hitboxes, приоритетный прогрев клипов и уникальных ресурсов Character Creation | [KBN-0039](../kanban/specs/KBN-0039.md) |

Критерии завершения: все работы и критерии приёмки пяти карточек закрыты; сохранены воспроизводимые сравнения до/после, результаты регрессий в Studio и опубликованном DEV (PC и физический Android), версии, сцены и настройки. Статический анализ и эмуляция телефона не заменяют реальные замеры. Бюджеты уточняются по baseline, без произвольных целей FPS. Не ухудшать точность боя, Headshot, навигацию, коллизии, анимации и доступность взаимодействия ради цифр производительности. Не закрывать карточки только по факту выпуска патча; незавершённая проверка остаётся явно открытой. Замеры переиспользовать в KBN-0003/0010.

Текущий статус M609: KBN-0037-T02 реализован и функционально принят владельцем в Runtime и на физическом телефоне. M610–M612: диагностика сети и исправление удалённых атак; текущий порядок изменён владельцем в M613 (рефактор прежде новых замеров). Полная матрица регрессий и количественные измерения открыты; текущая база дальнейших оптимизаций — M609, исходная база для A/B креплений — M605. Источник статических замечаний, работы и подробные критерии — спецификации пяти карточек.

## M612 · Remote Player Attack

Атаки должны отображаться у всех наблюдателей с сохранением движения ног. Сервер публикует атомарное состояние принятой атаки, клиент наблюдателя воспроизводит верхнюю ветку существующим композитором. Фаза привязана к серверному времени; локальный игрок не проигрывается повторно. [Контракт и приёмка](../workflows/M612_REMOTE_PLAYER_ATTACK_RU.md). Приёмка открыта.

## M611 · Network Motion Owner

[Три синхронных точки измерения](../workflows/M611_NETWORK_MOTION_OWNER_RU.md): наблюдатель, сервер, локальный клиент цели. GetServerTimeNow для окна, os.clock для dt. Диагностика не меняет движение; полученный baseline M610 сохранён в KBN-0035.

Настройка Place (решение владельца 27.11.2026, после M611): `Workspace.ImprovedPhysicsReplication = Enabled` пока сохраняется. Не считать это доказанным исправлением пульсации; фиксировать фактическое значение в каждом сравнительном замере и проверять его в собранном Runtime. Изменение или отключение — отдельный осознанный эксперимент.

## M610 · Network Motion

Первый измерительный сценарий KBN-0035: Camera Debug → Network motion, выбранный игрок, синхронное 8-секундное окно client/server. Горизонтальная скорость физической позиции, AssemblyLinearVelocity, client render position, frame p95, полусекундные bins. Только Studio/разрешённый DEV, по запросу, без изменения движения. [Приёмка](../workflows/M610_NETWORK_MOTION_RU.md). Полный Profiler и фактическая причина пульсации скорости остаются открыты.

## M609 · Rigid Parent Frame (функционально принят владельцем)

M608 не устранил отрыв. M609 удаляет вспомогательные Bone и восстанавливает выбор сокета и формулу до M607: `parent.TransformedWorldCFrame * target.CFrame`, без собственного Transform сокета. Native RigidConstraint соединяет родительскую Bone с grip, в котором учтено постоянное локальное смещение сокета; для верхнего уровня используется обычная Attachment на MeshPart. Bow release и Timeline используют то же уравнение крепления. Без follower, новых FBX или изменения физики персонажа. [Приёмка и диагностика](../workflows/M609_RIGID_PARENT_FRAME_RU.md). KBN-0037-T02 выполнен; полная проверка A02 и измерения T06 открыты.

## M608 · Runtime Socket Bone (отклонённый эксперимент)

M607: владелец наблюдал отрыв меча и волос при прыжке, смещение меча охранника в Idle. В M608 нативный joint перенесён на созданную в Roblox дочернюю Bone с identity CFrame/Transform, одну на исходный сокет. Исходный grip, ориентация, physics/root ownership не меняются; отдельного follower нет. Это эксперимент по устранению дефекта, а не доказательство исправления. [История эксперимента](../workflows/M608_RIGID_SOCKET_BONE_RU.md). M608 отклонён; заменён функционально принятым M609.

## M607 · Native Rigid Equipment (история первоначального контракта)

- Один RigidConstraint между канонической Bone и локальным grip на корне каждого жёсткого предмета; составные меши соединяются WeldConstraint. Волосы, оружие игроков/NPC используют существующие опубликованные модели без новых FBX и без привязки публикации к расе/полу.
- Удалён BoneMountedAttachmentController и его покадровое перемещение. Bow release вычисляется по animated socket, а не задержанному положению визуального предмета. Одноразовое выравнивание при сборке и редакторский Timeline pose sampling остаются; не являются runtime follower.
- [Приёмка M607](../workflows/M607_RIGID_EQUIPMENT_RU.md): PC/Android, сеть, бег, атака, превью и сравнение Physics/CPU/frame time.

## M605 · HUD и прогрев анимаций при входе

- M604 включён в M605: Lock над Door, правая граница Attack / Skill 4 / weapon grid — DeviceSafeInsets − 2 px, Jump под Skill 1. Общий фон Wallet, SVG Attack/Jump/Aim через прежний RGBA pipeline. Пропорции сохранены, дуга расширена для независимых hit targets.
- Клиент при старте однократно загружает опубликованные клипы NPC/Monster по уникальным ID, по 16 за запрос. Существующий world-entry curtain ожидает также текущий кеш AnimationTrackCache персонажа. Лимит дополнительного ожидания 12 с, отмена по смене персонажа/epoch. Без Character Creation preload фоновый. Death запускается до fade старых треков и отключает client lower-body compositor немедленно; terminal pose policy не меняется. [Приёмка](../workflows/M605_HUD_ANIMATION_PREWARM_RU.md).

## M602 · Движение назад

- PC S/Down и отрицательная Y ось touch используют Walk/Backward и направление относительно текущей камеры, независимо от yaw персонажа, ПКМ и атаки. Touch сохраняет аналоговую силу и диагонали; PC сохраняет одноосный S вне live aim. Боевые locks остаются в силе. [Приёмка](../workflows/M602_CAMERA_BACKPEDAL_RU.md).

## M601 · Оружейные слоты и Newbie Slayer

- Mobile: блок 2×2 на DeviceSafeInsets, 2 px сверху/справа; размер по CoreUISafeInsets сохраняет 37% Attack. `newbie_slayer_01` → `weapon_003` в Database (bigsword первого уровня), без изменения характеристик. При пустой категории лог и обновление каталога на следующий тап. [Приёмка](../workflows/M601_WEAPON_CORNER_RU.md).

## M600 · Дом: иконки и наведение; имена NPC

- Замок и дверь показывают текущее состояние иконкой, без текста успеха; E/F и серверная авторизация сохранены. Наведение E на меш двери проверяется только в USE-радиусе ручки. Runtime визуалы связаны с proxy, используется реальный Raycast по мешу с его CollisionFidelity. NPC: удаление цифр только при отображении имени, не из реестров. [Контракт и приёмка](../workflows/M600_HOUSE_INTERACTION_ICONS_RU.md).

## M599 · Мобильные debug и оружейные слоты

- Touch: GP (Play, только разрешённый Studio Hub), UI presentation, HP (линейка), CD (камера). Остальные debug-контроллеры не запускаются на touch. Оружейные слоты переключают тип одним нажатием через прежний DEV equip RPC, без меню; при отсутствии ранее выбранного оружия берётся первый доступный slug по сортировке. Авторизация и desktop без изменений. [Приёмка](../workflows/M597_MOBILE_HOLD_HUD_RU.md#m599--mobile-debug--quick-switch).

## M598 · Мобильная раскладка HUD

- Attack в нижнем правом углу safe area; Jump/Auto слева от него, 4 Skill на дуге вокруг Attack; все вторичные кнопки 46% диаметра Attack. Joystick 106%, weapon slots 37%. Debug Dock сдвинут вправо на размер Settings (44 px), на touch резервирует верхний правый weapon grid. Логика M597 неизменна. [Приёмка](../workflows/M597_MOBILE_HOLD_HUD_RU.md#m598--геометрия-hud).

## M597 · Удержание и мобильный HUD

- PC ЛКМ и mobile Attack: немедленный запрос при нажатии и повтор после завершения существующего attack timeline; серверные правила и попадания неизменны. Mobile Jump: повтор только после физического приземления и окончания air lock. Release/cancel, смерть, смена персонажа, потеря фокуса, меню и блокировка сцены снимают удержание/автоатаку.
- Action touch сохраняет право поворота камеры, но не становится пальцем pinch; отдельный свободный палец имеет приоритет. Зелёная кнопка включает непрерывную атаку по текущему прицелу, один раз пробует существующий AutoAim; ручной поворот снимает фиксацию цели, не отключая автоатаку. Drag не считается тапом кнопок.
- HUD: справа снизу Attack/Jump/Auto, четыре пустые skill-ячейки; справа сверху четыре категории DEV-оружия (dagger/sword/bigsword/bow) через существующий серверный каталог, не выдача предметов в production; слева под Roblox — белая круглая шестерёнка. Gold plate шириной по тексту + прежние 42 px. Context/Info dock учитывают новый кластер. [Приёмка M597](../workflows/M597_MOBILE_HOLD_HUD_RU.md).

## M596 · Character Roster

- Character Creation при включении поддерживает до пяти персонажей на аккаунт. Список и активный ID серверные; кнопки создания, смены и удаления находятся на экране выбора. Удаление необратимо после явного подтверждения, только выбранный ID; последнего — переход в создание. Отмена создания возвращает к сохранённым персонажам. Невалидное превью не запрещает управление списком.
- Прежний DataStore `game1_character_profiles_v1`, ключ `player_<UserId>`: schema v1 мигрирует без сброса внешности, XP, Gold и позиции в schema v2 при первом сохранении/создании/удалении. Слоты имеют стабильные ID; язык и сохранённая палитра остаются аккаунтными. Изменения атомарны с проверкой ревизии, при конфликте/неясном результате запись блокируется до нового подключения. Опубликованная игра не допускает session-only вместо неудачной записи.
- Перед публикацией остановить все серверы старых версий того же Experience (они не понимают schema v2); после миграции не откатывать сервер до M596. Новый Runtime собрать из обновлённого авторского Place. Studio/DEV PC/Mobile приёмка — открыта. [Чеклист M596](../workflows/M596_CHARACTER_ROSTER_RU.md).

## M595 · Debug в закрытом DEV Place

- `Options → Debug / TestPlace → Private DEV Place ID` (`debugUi.publishedPlaceId`, по умолчанию пусто) — точный Roblox Place ID, не Universe ID. В опубликованном Place, включая compiled Runtime, debug доступен всем допущенным в этот Place игрокам при соответствующей галочке PC/Mobile. В другом Place или без ID debug закрыт. Владелец/ранг группы больше не являются условием; допуск игроков обеспечивает закрытый Roblox Place, а не лимит 10 мест. Сервер выставляет атрибут разрешения и проверяет каждый debug-вызов. GP/AG/Buffer и Studio-only действия остаются Studio-only. При обеих снятых галочках debug-сервисы не стартуют. Сохранить Options, Rojo Sync авторского Place, пересобрать Runtime и опубликовать именно DEV Place. При релизе сохранять отдельный Place ID и закрытые настройки. Started language остаётся debug-настройкой и применяется к допущенным клиентам при её включении.

## Текущий контракт · M594 (Monster AI / Runtime)

- M594: BlockedWait не блокирует обычную атаку: проверяются живая цель, территория, радиус, высота и препятствия, затем штатная остановка навигации и атака. Если удар невозможен, новый подход ×1,5 Run запускается при входе цели в радиус лука, уменьшении 3D-дистанции внутри радиуса минимум на 1 stud от наблюдавшегося максимума либо получении ненулевого урона от текущей цели. Неподвижная цель не запускает повторный поиск; активные Climb/Rescue Route/Retry/BlockedRetreat сохраняют владение движением. Studio/Runtime Play: повторить подход вплотную к ожидающему монстру, проверить удар, стену и неподвижное ожидание.

[Gameplay infrastructure M570](../workflows/M570_GAMEPLAY_INFRASTRUCTURE_RU.md) — единая актуальная инструкция по Database, спавнам, политике преследования, экспериментальной навигации, Rescue Routes и диагностике. Старые milestone-описания ниже сохраняют историю; M566/M568/M569/M570 имеют приоритет над прежними условиями. Экспериментальная навигация не принята целиком в Studio.

## M593 · Runtime и нагрузка Monster AI

- До M592 включительно Experimental был жёстко Studio-only, хотя исходники входят в Rojo. M593: `Options → Monster Navigation → Enable in published Runtime` (`runtimeEnabled`, default false) разрешает Experimental в опубликованной игре только вместе с `enabled=true`. Studio override действует только в Studio; compiled Draft без override наследует обе Runtime-настройки. NPC/Legacy, GP Guided/Skilled не изменены. Для нового Runtime требуется Rojo Sync, сохранённый `.rbxlx`, Preflight → Draft. Не публиковать до приёмки KBN-0032; текущий `publishAllowed=false` не изменён.
- При выключенном backend граф не строится; при свободном входе проверяется проекция без сетки 20/4; линии вне радиуса отсекаются; BlockedWait не создаёт геометрических callback и не переписывает неизменный счётчик секунд. При агрессии сначала отсекаются далёкие игроки, затем проверяются life/territory/isolation. Периодические диагностические записи скорости/лучей и обновление точки плана только Studio. Алгоритм входа/выхода, M582 и 20/4 сохраняются. MONNAV только Studio, без дополнительных кастов.
- `Debug / TestPlace`: `startInHub` и обе галочки published debug сохранены. GP/AG/Buffer только Studio (compiled Draft — только при Start in Hub), в M593 опубликованный Runtime исключался, это правило заменено M595 (точный DEV Place ID); при отключении обеих галочек нет подписки авторизации. Небольшие общие combat/test-policy модули остаются в Rojo; не вырезать их как независимый dev-код.
- См. [аудит M593](../workflows/M593_MONSTER_RUNTIME_AUDIT_RU.md), [KBN-0032](../kanban/specs/KBN-0032.md). Измерений CPU/физики Roblox не проводилось; статическая проверка не является нагрузочной приёмкой.

## Историческое дополнение · M560 — авторинг Monster Spawn Zones (уточнено M568/M570)

- Единственный интерфейс создания, перемещения и удаления зон монстров: **Roblox Studio → Plugins → game1 → Monster Spawns**, в режиме редактирования, при запущенном Control Center. Выбор вида и доступного уровня привязывает запись к `balanceId`, а не к уровню модели. Неопубликованные виды можно планировать; runtime ждёт соответствующую опубликованную модель и обязательные анимации.
- Выбор уровня → параметры → Place spawn zone → клик по поверхности → Apply. Сток: радиус 15, количество 3, респавн 10 секунд, Home Leash 150; Aggressive, Aggro и Death Chase из выбранной строки Database. Индивидуальные overrides сохраняются в `assets/manifests/monster-spawns.json`, runtime registry генерируется сервером Control Center. После сохранения — Rojo Sync перед Play. Database → Main → Spawn Zones с M570 позволяет редактировать параметры существующих зон; координаты и ID только чтение.
- Прежние формы Monster Spawn Authoring / Monster Spawns и их browser write API удалены. NPC authoring не меняется. Старые зоны сохраняют привязку до явного переавторинга. С M568 Death Chase не зависит от наличия `Game1MonsterZone`: без однозначной территории нет leash и тайм-аута.
- Monsters → Registered monsters показывает все виды Database, включая незарегистрированные, портрет из общего атласа, уровни и состояние моделей/текстур. Готовность и применение проверять в Studio; исходники не являются подтверждением Play-приёмки.

## M572 · Физические столкновения акторов

- `ActorCollisionPolicy`: физические корни NPC и монстров используют `Game1NonPlayerBodies` без взаимных столкновений (NPC–NPC, NPC–Monster, Monster–Monster). Игроки остаются в `Game1ActorBodies`; контакт с игроками и миром сохранён. Правило действует в Studio и опубликованной игре, без дополнительных циклов или ограничений на пары акторов.
- Боевые хитбоксы, RootCollider, смерть/респавн, урон и агрессия сохраняют свои контракты. Пространственные запросы экспериментальной навигации и ranged retreat используют группу физического корня; Combat targeting не изменён. Studio-приёмка: пересечение группы NPC/монстров, игрок и стена, удары по пересекающимся целям, повторный спавн.

## M588/M590 · Переходы между отдельными Rescue Routes и поиск 20/4 (заменяет соединения M579 и поиск входа M586)

- При активном Experimental на старте MonsterAI (Studio или явно разрешённый Runtime с M593) один раз строится граф: M590 — только свободные начало и конец целого маршрута соединяются с ближайшей произвольной точкой на отрезке другой линии, без ограничения длины перехода, но с перепадом высоты не более Options → Monster Navigation → Route connection height (routeConnectionHeight, по умолчанию 2 studs, диапазон 0–100). Сохранение → Rojo Sync → перезапуск Play; применяется при построении графа, не ограничивает вход/выход. Сначала учитываются существующие геометрические стыки; затем ближайшие переходы, уже соединённые концы не создают новые. Внутренние вершины и замкнутые линии не инициируют мосты; наклонный отрезок ограничивается допустимой полосой высот. Переход двусторонний, не входит в авторскую линию и не участвует в её ранжировании. Точка проекции может быть внутри отрезка; исходные данные Place не меняются. Перед использованием ненулевого перехода проверяется Raycast от пяток до пяток; результат кэшируется в рамках поиска. Terrain исключён, как и раньше; проверка лучом не гарантирует физическую проходимость.
- Выбирается маршрут по ближайшей проекции цели; M582 остаётся только для целевой линии/выхода. Поиск входа: ближайшая проекция пяток монстра, при блокировке ±20 studs по длине полилинии (не от каждой вершины); включены концы линии. При первой свободной грубой пробе уточнение в направлении проекции цели шагом 4 studs, не дальше одного интервала 20, до блокировки/границы/цели. Свободная исходная проекция принимается сразу. Радиус из Options сохраняется. Если входа/полного пути нет, соседние маршруты перебираются по длине переходов без повторной проверки той же линии за поиск. Dijkstra использует проверенные переходы; выход остаётся на целевой линии. Кэш входов, переходов и путей — на один поиск.
- `NoAccessiblePlan`: не повторять полный расчёт каждые 1,5 с. При Chase M591 — отступление до горизонтальной дальности лука из Database (M592: максимум по лукам, сейчас 40 studs, независимо от экипировки) + 2 studs, затем ожидание. При невозможности отступить дальше — ожидание на достигнутой точке. StuckTimeout и Home Leash NoDamageTimeout начинают отсчёт при ожидании; повторное сближение и новый поиск при необходимости — по условиям M594 выше. При Return старый Retry и watchdog сохраняются. Options: blockedRetreatBuffer (2), blockedRetreatSpeedMultiplier (1), blockedReengageSpeedMultiplier (1.5), rescueRouteSpeedMultiplier (1.5); скорости — множители Run, без перемножения. MonsterBlockedPursuit / MonsterBlockedRetreatGeometry / MonsterNavigationSpeed. Не меняет M582 или граф. При смене цели/контекста или неудаче выбранного плана допускается новый поиск. MONNAV: `GRAPH_TRANSFER`, `transferChecks`, `entryRouteId`. `MonsterRescueConnections` и `MonsterRescueSampling` — отдельные хелперы. Studio Play и профилирование старта/массового преследования не проведены.

## M587 · Проверка входа Rescue Route от пяток (уточняет M586)

- `Geometry.RouteEntryClear`: один конечный Raycast от пяток монстра до точки на линии; любой учитываемый коллайдер отклоняет кандидата (`FootBlocked`), даже если препятствие низкое. Поиск альтернативных входов, фильтры коллизий (Terrain исключён), ранжирование маршрутов и условия выхода неизменны. Луч от головы не используется только для входа; Collision, Direct, Climb и проверки выхода сохраняют свои правила. Проверка одной линии не гарантирует свободный объём тела; Studio Play обязателен.

## M586 · Целевой маршрут и архитектура Rescue Route (уточняет M584; проверка входа заменена M587)

- Приоритет между маршрутами — ближайшая 3D-точка линии к пяткам цели. На выбранной линии сначала проверяется ближайшая 3D-проекция монстра, затем при блокировке — точки всех локальных отрезков по расстоянию с шагом до 1 stud. Радиус входа из Options. Проверка входа с M587 — один луч от пяток до точки на линии; любой учитываемый коллайдер отклоняет точку, физическая проходимость всего тела не гарантируется.
- Если полный план не найден, проверяются другие входы выбранной линии, связанная сеть, затем следующие маршруты. M582 (сфера выходов), высота/дистанция выхода внутри выбранной линии, проверка прямого выхода, сравнение с Collision/Climb, leash/cooldown и досрочный сход сохранены. Кэш проверок общий на поиск; GRAPH_ROUTE и routeId в диагностике.
- Граф разделён на Topology, Segments, Routes, Entries, Paths, Exits, Queries; MonsterRescueGraph сохраняет публичный Find. Подробности: M570_GAMEPLAY_INFRASTRUCTURE_RU.md. Studio Play и измерение нагрузки ещё обязательны.

## M584 · Непрерывные входы и выходы Rescue Route (уточняет M581/M582)

- В каждом сегменте в пределах 40 studs сначала проверяется ближайшая 3D-проекция ног монстра. При её недоступности на этом сегменте проверяются остальные кандидаты по расстоянию: совпадение высоты, границы интервала, сетка до 4 studs. Если проекция доступна, концы сегмента как альтернативные входы не проверяются. Кэш соединений сохраняется. Dijkstra для достижимого выхода сначала минимизирует расстояние до входа, затем длину пути: более далёкая вершина не выигрывает за счёт срезания маршрута.
- Выход вычисляется на непрерывном отрезке внутри сферы M582: минимальный перепад высоты, затем расстояние до цели, при равном ранге — ближайший вход и стоимость. При отсутствии доступного аналитического выхода выполняется ограниченный поиск промежуточных выходов (не более 32 интервалов на сегмент). Это конечная сетка, не гарантия нахождения произвольной узкой щели. M582, Raycast доступности, topology M579, leash/cooldown и проверка досрочного схода/пересчёт после окончания плана сохраняются. Нагрузка при блокировке множества входов/выходов требует профилирования в Studio. NPC/Legacy и схемы данных не меняются.

## M582 · Ограничение конечной точки Rescue Route

- При выборе плана выход должен находиться не дальше от цели, чем монстр в момент поиска (3D-дистанция между позициями ног). Равная дистанция допустима. Сегменты выхода аналитически обрезаются сферой вокруг цели; в допустимой части рассматриваются ближайшая по высоте точка, 3D-проекция и границы. Приоритет высоты, затем дистанции, затем полной стоимости сохраняется. Промежуточные точки маршрута могут удаляться от цели. Входы M581, проверки доступности, leash, Retry, Climb и Home Recall не изменены. Если допустимого выхода нет, Graph.Find возвращает nil. Studio Play необходим.

## M581 · Поиск входа в Rescue Route без порога высоты

- Входы рассматриваются в прежнем 3D-радиусе `searchDistance` (40 studs по умолчанию), без жёсткого допуска Y в 2 studs. Основные кандидаты — ближайшая 3D-проекция, точка ближайшей высоты ног и концы сегмента. Входная стоимость остаётся 3D-дистанцией; высота участвует в ней и разрешает равенство дистанций. Все входы проверяются существующим `Geometry.Clear` и политикой leash/cooldown.
- Только если ни один основной вход не прошёл, проверяются дополнительные точки на части каждого сегмента внутри сферы поиска, с шагом не более 4 studs. Общий кэш проверки точек и MONNAV `GRAPH_SEARCH` охватывают обе стадии. Выходы (уточнены M582), топология M579, Climb/Recall M580, NPC и Legacy не изменены. Лучи по-прежнему не учитывают Terrain; доступность физического прохода и нагрузку fallback необходимо подтвердить в Studio.

## M580 · Ограниченный прыжок и возврат телепортом

- Climb завершает попытку максимум через 1 с от входа в состояние, независимо от FloorMaterial; раннее подтверждённое приземление по-прежнему завершает прыжок. На тайм-ауте текущий план сбрасывается и цель оценивается заново. Повторный импульс в воздухе запрещён, высота и физика не меняются. Лог `CLIMB_TIMEOUT`.
- Глобальный `StuckTimeout` теперь инициирует `MonsterHomeRecall` при Chase или застревании на пешем Return. Тот же экземпляр монстра, HP и идентификатор сохраняются. 1,05 с исчезновения, перенос на сохранённый MonsterHomePosition, 1,05 с появления. В обеих фазах отключены получение урона и повторный агро, движение остановлено; после появления — обычное состояние Idle. Отмена при смерти/удалении. Обычные Home Leash, NoDamageTimeout и TargetLost остаются пешими, если не застряли.
- `BuffCastVisuals.PlayAt` переиспользует эффект бафа на фиксированной мировой позиции, минимум 10,4 studs высоты, фиолетовый; события только клиентам в радиусе 160 studs. `HOME_RECALL_OUT/IN/DONE`, `MonsterHomeRecalling`. Experimental с областью действия M593; физика, визуал и Streaming требуют Studio Play.

## M578 · Обычный прыжок монстра (дополнен M580)

- В экспериментальном навигаторе `MonsterClimbMotion` больше не закрепляет root, не перемещает CFrame и не удерживает высоту. Один физический импульс на земле: вертикальная скорость `CharacterConfig.JumpVelocity * sqrt(PlayerJumpSettings.heightMultiplier)`, горизонтальная — текущая эффективная скорость монстра по направлению движения. Обычная гравитация, столкновения и Humanoid Move; замедление падения персонажа не копируется. Следующий прыжок возможен только после приземления. Настройка Climb speed удалена; прежнее поле при миграции Options игнорируется.
- При свободном верхнем луче и скорости ниже 50% (настраивается) сохраняется безусловный приоритет прыжка, без поиска альтернатив. Rescue Route сохраняется; после приземления либо тайм-аута M580 обычная навигация и замер скорости возобновляются. Stuck return 30 с сохраняется (действие изменено M580). MONNAV: `LOW_CLIMB`, `CLIMB_JUMP`, `CLIMB_LAND`. Проверка физики в Studio необходима; NPC и Legacy не меняются.

## История M573 · Повторяемый физический подъём (заменён M578)

- `MonsterClimbMotion` удерживает одну попытку: малые вертикальные импульсы каждые 0,7 с (фаза подъёма до 0,35 с, скорость из Options, по умолчанию 8 studs/s), между ними медленное сползание 1 stud/s. Humanoid продолжает движение к выбранной точке; временный LinearVelocity действует только по вертикали. Коллизии, A/B и обычная навигация не изменяются.
- Нет общего пятиисекундного дедлайна и мгновенного отказа при горизонтальном контакте. Сохраняется безопасность потолка: вертикальный Blockcast только на очередной импульс. Прогресс — новый максимум высоты или уменьшение горизонтального расстояния до точки минимум на 0,15 studs; повторная осцилляция не продлевает watchdog. Успех — достижение landing по XZ; после 7 с без прогресса — Retry и поиск альтернатив, прежняя временная блокировка неудачной точки 8 с. В Retry близкий контакт нижнего луча запрещает Direct даже при свободных лучах выхода. После снятия препятствия/истечения cooldown возможен повторный подъём. Все временные силы удаляются при выходе, смерти, смене цели или обездвиживании.
- MONNAV: `CLIMB_PULSE`, `CLIMB_STALLED`; существующие `CLIMB_STEP`, `RETRY`, `MonsterRecoveryMode`. Исполняемые тесты проверяют контроллер и переходы на моках, а не физику Roblox. Studio Play: повторные импульсы на низкой стене, тонком заборе и ступенях, потолок, Root/Stun, Return, без ложного перезапуска.

## M579 · Процедурное соединение Rescue Routes (заменяет M577)

- Ручная привязка и статус Junction удалены из Studio: клик сохраняет исходную точку поверхности. Apply/Cancel/Delete и каталоги работают как прежде. Уже сохранённые маршруты не требуют переавторинга.
- `MonsterRescueGraph` автоматически соединяет вершины, T-образные примыкания, пересечения внутренних частей отрезков и коллинеарные перекрытия. Допуск реального расстояния в 3D — 0,25 studs; для небольшого зазора создаётся короткое двустороннее ребро. Совпадение XZ на разных этажах само по себе не создаёт связь. Маршруты должны быть проложены по проходимому пространству: автосвязь не выполняет проверку стены между почти совпадающими линиями.
- Разбиение и соединение выполняются в памяти однократно при построении графа; исходные координаты, ID, каталоги и зеркало Database не меняются. Попарная проверка авторских сегментов ограничена существующим лимитом 2048, с предварительным отсевом по AABB; плотная сеть требует профилирования. Новых кастов при движении нет. Приоритет выхода и прыжок M578 сохранены. Studio-приёмка открыта.

## M576 · Безусловный приоритет низкого препятствия (движение заменено M578)

- При замере движения ниже настроенного порога (50% по умолчанию) и свободном верхнем горизонтальном луче немедленно запускается существующий кинематический подъём M575. Без сравнения стоимости, `Detour`, `Graph.Find` и cooldown точки. На Rescue Route подъём сохраняет текущий маршрут. Если поверхность не найдена, используется короткая попытка подъёма вперёд с теми же ограничениями по высоте тела и sweep-проверками. Неудача не разрешает проход сквозь геометрию; при повторной проверке низкого контакта снова подъём, а не выбор маршрута. Общий Stuck Return сохранён. Высокие препятствия используют прежний поиск альтернатив. Событие `LOW_CLIMB` в MONNAV. Приёмка физики в Studio необходима.

## M575 · Stuck Return и исторический кинематический подъём (заменён M578)

- Экспериментальное карабканье M573 заменено: без импульсов, LinearVelocity и сползания. На время подтверждённого низкого препятствия физический root закрепляется, высота наращивается небольшими шагами со скоростью Climb speed, затем удерживается при перемещении через кромку. Если кромка блокирует движение, подъём продолжается в пределах высоты коллайдера от начальной позиции. Каждый шаг ограничивается Blockcast по физическому root, учитывающим коллизии мира и Terrain; CanCollide не меняется. При завершении/отмене возвращается обычная физика и серверное владение, при смерти сохраняется закрепление трупа. 7 с без нового прогресса — Retry. Прежние импульсы M573 исторические.
- `Options → Monster Navigation · Experimental → Stuck return · sec`: 30 по умолчанию (5–300), независим от Home Leash и Death Chase. `MonsterStuckWatchdog` сохраняет окно прогресса при смене плана, повторном подъёме и Retry; обновляет при смещении по XZ на 2 studs или расширении диапазона высоты на 0,5 studs, не при повторении того же прыжка. С M580 AI при истечении вызывает телепортацию домой (`StuckTimeout`), включая застревание на пешем Return. Таймер не работает при остановленной навигации/обездвиживании. Область Experimental — по M593, NPC/Legacy не затронуты.
- MONNAV: `CLIMB_LEVITATE`, `CLIMB_CROSS`, `CLIMB_STALLED`, `STUCK_TIMEOUT`, `RETURN StuckTimeout`; Explorer: `MonsterRecoveryStuckSeconds`. Исполняемые тесты используют моки пространственных запросов; Studio Play требует приёмки.

## M574 · Единая проверка выхода из recovery и связный граф

- Обычный Direct сохраняет короткий горизонтальный луч в радиусе атаки. При сходе с маршрута, Retry и проверке выхода кандидата `RecoveryExitClear` выполняет Head → Feet (+0,1 studs), затем при свободном луче горизонтальную проверку **до цели целиком**, а не только в радиусе атаки. Та же проверка применяется к конечным точкам Collision и Rescue Route. Высокая стена за пределами короткого lookahead не разрешает сход. Новых объёмных проверок, таймеров и проверок щелей нет.
- В `MonsterRescueGraph` радиус поиска 40 studs относится только к входу. M581 заменил прежний допуск высоты 2 studs и расширил набор кандидатов. Отброшенные кандидаты не исчерпывают прежний лимит 8: с M586 сначала выбирается ближайший к цели авторский маршрут, затем проверяется ближайший доступный вход с кэшем повторных точек; Dijkstra определяет достижимый граф. Выходы выбранного маршрута ограничены исходной дистанцией до цели (M582) и сортируются по высоте пяток цели, дистанции и полной стоимости. Проверки выхода прекращаются после найденного допустимого ранга (равный ранг сравнивается по стоимости). Лимит графа 2048 рёбер сохранён; нагрузка большого локального графа требует измерения.
- MONNAV `GRAPH_SEARCH`: число кандидатов входа, доступных входов, фактических проверок входа, рассмотренных достижимых выходов и проверок выхода. `PRIMARY_HEAD` на сходе теперь имеет длину до цели. M573 Climb, Death Chase/Home Leash, NPC и Legacy не изменены. Тестируется воспроизведение ошибок на аналитических геометрических запросах и графах, не физика Studio.

## Актуальное дополнение · M439 (22.11.2026)

- **UI/реестр:** Atlas Favorites (M435), карточки Mechanics House (M436), единое автозаполнение и новые визуальные дефолты (M437), заголовки вкладок и блокировка регистрации Location Asset (M438) присутствуют в коде. Текущие регистрационные defaults относятся к новым записям, не мигрируют существующие ID.
- **LOD:** индивидуальные `assetDistances` на Location Asset, индивидуальные House MeshPart-дистанции, единый `hysteresis`, общие native Workspace Streaming settings; Studio Live Preview и отдельный compiled Runtime Draft используют разные источники применения. M429 согласовал Bridge schemaVersion=2. Runtime compiler фиксирует `publishAllowed=false`, требует сохранённого `.rbxlx` и проверенного backup. Понятие «глобальные LOD-дистанции» из старых материалов больше не является текущим контрактом.
- **Дом:** `fireplace_01_socket` предлагает E/F по серверному состоянию. `firewood_01` 120 с → `embers_01` 120 с → пусто; cooking_pot_01 ставится на дрова, готовка 30/60 секунд, клиентский progress до 50 studs. Пар, огонь и свет являются runtime эффектами. `cooking_pot_socket` принадлежит котлу, **не** HouseSocketContract. Ресурсы и выдача блюда — stub, не production inventory. В M438 UI Mechanics ещё только читал техкарты; **с M442** тайминги редактируются через валидируемый Fireplace settings API, а с **M449** постоянные USE/AIM-радиусы редактируются исключительно в Options → Sockets. Ранее сохранённые поля радиусов в Mechanics JSON остаются для совместимости, но больше не управляют диапазонами runtime. Состояние живого камина не сохраняется между перезапусками.
- **Сокеты этажей:** актуальные имена по HouseSocketContract — `house_floor_01_spawn_socket`, `house_floor_02_spawn_socket`, `house_floor_03_spawn_socket`. Старая форма с добавочным `_01` была ошибочной.
- **Статусы:** наличие Luau/Python/JS-кода не означает прохождение Studio Play или Android. Матрица открытых проверок: [Kanban M439](../kanban/STATUS_2026-11-22_M439.md).

## Актуальное дополнение · M447 (23.11.2026, исходники после M446)

**[Сквозной аудит всех разделов Mechanics](../workflows/MECHANICS_RUNTIME_GAPS_M447_RU.md)**: House 10 карт, NPC 3, Monster 3, Character 5. Для каждой зафиксированы существующие кодовые контракты, недостающие runtime-переходы, сохранение и реальные Play-проверки. Старое описание раздела Mechanics как содержащего только House актуально для M436, не для M447.

Отличать сохранённые **авторские данные проекта** (Options JSON/Registry, Fireplace tuning, spawn/asset registries, Plot/LOD settings) от **состояния игры** (персонаж UserId, inventory, HP, живой NPC/Monster, открытая дверь, огонь/котёл/готовка). У просмотренного игрового Runtime нет интегрированного account/world DataStore и атомарных транзакций ресурсов. Параметры можно сохранить и опубликовать, но live-состояния при новом сервере не восстанавливаются. Зависимость `HouseFireplaceService` от `task.delay` также пока не обеспечивает heat-aware готовку. **Это открытые задачи, а не новые требования к M447-коду.**

Нельзя отмечать Mechanics и gameplay persistence готовыми до Studio Play, мобильного устройства, двух клиентов и опубликованного Runtime Build с актуальным `.rbxlx`. M447 — **только документационный аудит**, ни одна игровая механика не менялась.

## Баффы · M545–M556 (актуальные значения восстановленной M570)

- Базовый реген игрока 1 HP/с (в Guided 0); Slow −40% из Database.
- D-баффы: Might +20% ATK, Earth +30% MaxHP, Life +1 HP/с (настройка пользователя в дампе M556; первоначально +2), Wind +20 Speed (+2 studs/с). Длительность 600 с (10 минут); общий `SkillEffects`, `CharacterStatsService` и `CharacterRegenerationService`. Покупка активного баффа разрешена: срок заменяется на полную длительность за 5 Gold, без сложения силы или времени; разные эффекты совместимы. MaxHP не даёт мгновенного лечения.
- Studio GP: золотой Buffer Dummy в Hub, модальное окно с четырьмя иконками покупки (M554–M556). Баффы сохраняются при обычном телепорте, сбрасываются при выборе GP-комплекта, Group/Guided, смерти и Exit. HUD показывает реальные прибавки, иконки с перелётом и таймером. Локальная открытая аура и искры; не репликация другим клиентам. Studio-приёмка открыта. См. [KBN-0026](../kanban/specs/KBN-0026.md).

## Актуальное дополнение · M544 (26.11.2026)

Database: Sword и Dagger — 9 studs для всех грейдов; melee-монстры — 10 studs (включая наследующие базовые строки Skilled). Bigsword, Dualswords, Bow, ranged-монстры и остальные характеристики без изменений. Именованные виды не повторяются между шестью основными территориями: Mandragora только в долине, Spore Spitter в садах LVL 15–19. Ice/Fire Vale Master — отдельные разновидности. GP-модели пока proxy; реальные ассеты не перепривязаны. Studio-приёмка открыта.

## Актуальное дополнение · M541 (26.11.2026)

[Действующий Hub / World GP workflow](../workflows/M541_HUB_WORLD_PROGRESSION_RU.md) имеет приоритет над M515/M517/M539/M540 в части движения, расположения и наград.

- Размер зон 384 × 384 сохраняется; шесть основных территорий из [Design](../kanban/specs/KBN-0031.md), 60 обычных точек, резерв 31–35 (10) и Skilled (8). `GameplayWorldHuntingPlan` задаёт самостоятельные карманы охоты относительно входа, от слабых к сильным; рельеф, биомы, настоящие модели и боссы ещё не построены. Первый размер визуально одобрен, новый runtime не принят.
- `debugUi.startInHub` default false, Options → published TestPlace → Debug and test controls. Только разрешённый Studio human_male после готовности персонажа, stock LVL 1. Hub ×3 (48 studs/s при базе 16) только обычный свободный бег, без дорожек/ускорения Group/Guided. Базовый RunSpeed и баланс неизменны.
- M549: Database → Monsters хранит Aggressive и Aggro radius (studs); новый спавн получает значения связанной записи, затем может переопределять их. Старые спавны без полей наследуют Database; несвязанные модели используют настройки ассета. GP zone использует ту же Database; Guided/Group сохраняют изолированное управление агро.
- Обычные zone-убийства в GP дают XP/Gold через серверный `ActorDamageSignals` → `CharacterProgressionService` → `GameplayTestLoadout.Reward`. Guided/Group/Skilled и чужие цели без наград. `CharacterProgressionView` — единая проекция уровня/XP/Gold и пересчёт базовых HP при level-up. Сессия хранит прогресс через смерть/телепорт, новый комплект сбрасывает до выбранного уровня; Exit не меняет постоянный профиль. GP cap определяется Levels (35), 30 — цель первого релиза. Новый грейд автоматически не выдаётся.
- M554: при первом входе в GP выдается 1000 Gold; кошелек сохраняется при смерти, телепорте и смене комплекта, уничтожается при выходе из GP. HUD показывает Gold слева внизу. Золотой Buffer открывает меню кликом по NPC или ProximityPrompt; один D-бафф стоит 5 Gold, покупка серверная, активный эффект можно купить снова за 5 Gold: срок заменяется на полную длительность, сила и время не суммируются. Визуально пять монет летят от персонажа к Buffer; это только локальное представление подтвержденной оплаты. Guided/Group не допускают покупки; производственный профиль не затронут. M556: уведомление баффа поверх магазина, повторная покупка повторяет VFX; GP → Hub возвращает в хаб без потери баффов и кошелька; Spawn создаёт группу с общим overhead (иконка, локализованное имя, уровень, красная *); декоративный overhead монстра пропускает мировой ввод; базовый реген 1 HP/с начисляется целым секундным тиком.
- M559: M557/M558 объединены поверх фактической M556 без сброса пользовательских значений агро; Database → Monsters поддерживает drag-порядок колонок и сортировку по заголовку. Настройки представления хранятся локально, не меняют каноническую последовательность записей и не сбрасывают черновик.
- M558: Monster Debug (aggro + combat sandbox) и Movement Debug удалены вместе с клиентскими/серверными модулями и runtime-override движения. Для постоянного агро используются Database/AG, для анимаций — авторские настройки и Custom Scaling. Панель разработчика: восемь пиктограмм TL, CS, HS, CD, HP, UI, GP, AG (внутренние ID сохранены), подсказки при наведении, прежнее выделение открытого раздела. GP и AG соседние. Боевой баланс и Options не изменены.
- M557: Database → Main: Monsters / Skills / Weapons / Levels / Character / Armor / Model bindings. Death Chase — общий флаг вида, выключен по умолчанию; после агро монстр преследует до выхода цели из исходной территории вместо обычного leash и таймера. GP использует границы карты, production — однозначную зону BasePart с тегом Game1MonsterZone, содержащую центр спавна. До M568 без зоны сохранялся обычный leash; это поведение отменено. Guided/Group/Skilled калибровка не меняются. Options: перетаскивание секций за ручку, локальное сохранение порядка, без стрелки раскрытия.
- M555: Database всегда открывается в Main; Skills внутри Main, категории Buff / Debuff / Monster / Character. Единый черновик и revision-guarded Save changes для всех таблиц. Общие эффекты не имеют владельца; D-варианты Might/Earth/Life/Wind перенесены в canonical gameplay.json (600 с), M557: короткие Might/Haste без грейда и два зависимых Skilled GP-профиля удалены; остаются четыре D-баффа и шесть дебаффов. Monster содержит назначения общих эффектов для Skilled GP; Character — отдельная точка входа будущих индивидуальных навыков без классов. HUD и Buffer получают параметры D-вариантов через Balance.Skill; иконки остаются presentation metadata.
- Продуктовые цели: шесть зон, LVL30/B, 9–12 ч (630 мин ориентир), второй биом — хоррор, вход виден из первой зоны. Без классов: каждый может учить навыки, применение ограничено оружием; Armor Crush только bigsword, Shackle Shot bow, масштабирование дебаффа по грейду — на согласовании. Не объявлять квесты, экономику, навыки, боссы и production persistence реализованными. Все 30 целей и Any — в Design.

## Актуальное дополнение · M540 (26.11.2026)

GP: стороны зон 384 вместо 1536 studs, шаг 408, стены 16, переходы 32 шириной; пересчитаны точки спавна, Go и входы. Hub, радиусы боя и баланс не изменены. Studio-приёмка открыта.

## Актуальное дополнение · M539 (26.11.2026)

[Design и полноразмерная GP карта](../workflows/M539_DESIGN_WORLD_ZONES_RU.md): 6 зон 1–30, резерв 31–35 и Skilled; Database names без численного rebalance. Старые дорожки, ×3 и ограничение ranged-подхода M517/M526 удалены. Hub, телепорты, три stock комплекта на зону, HUD и прежний Guided. Высота GP +1024; только Studio, реальная приёмка открыта.

## Актуальное дополнение · M529 (26.11.2026)

[Skills и высотный тестовый стенд](../workflows/M529_SKILLS_AND_SKY_TEST_RU.md): Database schema 4, независимые навыки с ID и назначения в Skilled Monsters, производный ATK downgrade (по умолчанию включён, можно выключить на назначении), шесть действующих профилей LVL20 (до M557 было восемь). Studio-only runtime, Silence пока не ограничивает автоатаку и не даёт штрафа, поскольку нет character skills. Отдельные платформы Hub/Melee/Ranged/Skilled на +100 studs (исторический контракт, заменён M539), переходы и GP выбор. Обычные 70 монстров M527 не изменены.

## Актуальное дополнение · M527 (26.11.2026)

[Баланс и отступление ranged](../workflows/M527_RANGED_RETREAT_BALANCE_RU.md): HP ×1,10, ATK ×180/139, AS ×139/180 относительно melee, округление до целых; AttackSpeed — поле Database schema 3. Отступление строго от цели в пределах бюджета цикла, до 4 studs, без melee pursuit во время атаки. Ограничение подхода M526 действовало до M539; в новых зонах обычное преследование.

## Актуальное дополнение · M526 (26.11.2026)

[Типы монстров и стенд](../workflows/M526_MONSTER_TYPES_RU.md): Database schema 2, 35 melee и 35 ranged, стабильные ID и отдельные характеристики/дальность. Уровень персонажа ограничен таблицей Levels, не числом монстров. Исторический стенд: две дорожки ×3 и ограниченный ranged-подход; с M539 заменены зонами без ускорения и gate. Ренж использует существующие серверные проверки дальности и LOS на Hit, отдельного снаряда и анимации пока нет.

## Актуальное дополнение · M525 (26.11.2026)

[Парные мечи](../workflows/M525_DUALSWORDS_RU.md): тип dualswords, с B-грейда (уровень 30), B+ имеет то же требование. Один цикл, два серверных попадания, общий ATK +12,5% относительно меча до округления. Рецепт из двух одинаковых записей меча и доплаты, без реализованного крафта. В GP допустима временная 1hs-анимация; вне GP требуются отдельные опубликованные анимации и два события. Остальные типы не изменены.

## Актуальное дополнение · M524 (26.11.2026)

[Критический баланс](../workflows/M524_CRITICAL_BALANCE_RU.md): Database владеет базовым критом без оружия, шансом каждой записи оружия/монстра, пределом (50%) и множителем урона (×2). Начальные значения 12% кинжал/лук, 8% меч/двуручник, 1% руки, 5% все 35 обычных монстров. Модификаторы GP временные, не влияют на сохранённый профиль. Headshot остаётся независимым множителем. Значения M523 «крит не менялся» относятся к историческому патчу, не текущей версии.

## Актуальное дополнение · M523 (26.11.2026)

[Баланс скорости и урона оружия](../workflows/M523_INTERLUDE_WEAPON_BALANCE_RU.md): Database владеет базовой AS персонажа (180) и модификаторами оружия. Interlude ratios: кинжал 433/379, меч 1, двуручник 325/379, лук 293/379. Лук без дополнительной перезарядки нормализован до DPS меча. Статы всех 32 записей пересчитаны; углы, дистанции, крит, HP монстров, XP, цены и заточка не менялись. Рост AS по уровню не введён. Runtime и GP используют один реестр; проверка в Studio обязательна.

## 1. Цель и пределы продукта

Развивать независимую от RobloxLineage сетевую игру на Roblox с кастомными персонажами, серверной боёвкой, NPC/монстрами, авторскими анимациями и оружием, локациями, размещаемым декором и недвижимостью. Системы публикации и Studio authoring должны переиспользоваться между категориями ассетов без специальных исключений по имени модели.

**Не считать реализованными без отдельного ТЗ и проверки:** аккаунтную MMO-персистентность и прогрессию, экономику и торговлю между игроками, квесты, владение недвижимостью с сохранением, полноценную систему ключей/предметов, завершённую лифтовую физику, production-инвентарь. В текущем доме замок и сундук используют временные части и тестовую логику; лифт переносит персонажа, а не двигает платформу.

## 2. Неприкосновенные инженерные требования

- Отдельные данные/порты/Place и project identity; никаких runtime-фолбэков на RobloxLineage. Актуальные правила — [`AGENTS.md`](../../AGENTS.md).
- **Server authority:** столкновения, атаки, здоровье, игровые проверки дистанций, интерактивные состояния и перенос персонажа подтверждает сервер. Клиент рисует интерфейс, принимает ввод и сглаживает визуал.
- Слои: `src/shared` — контракты/чистые расчёты; `src/server` — gameplay; `src/client` — presentation; `system` — авторинг, публикация, Control Center, Bridge, backup/verify. Направление зависимостей — внутрь.
- Стабильные slugs, авторские FBX, SHA-256, опубликованные Roblox Asset IDs и данные SQLite/манифестов нельзя сбрасывать ради рефакторинга. Миграции явные, обратимо проверяемые на копиях данных.
- Единые контракты для reusable actor behavior и подготовки моделей; исключения по slug и раздельные «почти одинаковые» реализации запрещены без обоснования.
- Разделять «готово в коде», «проверено статически», «проверено в Studio» и «осталось реализовать».

## 3. Текущее функциональное покрытие

| Домен | Наличие в исходниках | Ограничения и статус проверки |
| --- | --- | --- |
| Инфраструктура | Rokit/Rojo, отдельный Place, PowerShell, Control Center, Host Agent, Studio Bridge, backup и verify | Настройки конкретной машины не входят в дамп и должны проверяться при запуске |
| Characters | Регистрация модели, анимационные профили, кастомный `ControllerManager`/камера/движение/респавн, визуальная сборка | Существующая анимационная и физическая механика должна оставаться совместимой |
| Combat / Weapons | Серверные атаки и хитбоксы, попадания по нескольким целям, weapon attachment, урон и эффекты | Полные Play-тесты обязательны; не заменять проверкой строк в коде |
| Monsters / NPC | Отдельный spawn/AI/lifecycle, преследование, реакция, боевые анимации, authoring | Общий `MonsterStore(kind="npc")` и NPC payload `monsterSlug` — архитектурный долг, **не** новая норма |
| Location Assets | Категории, registration/publication, Deco/Studio sync, авторские атласы | Варианты общего Atlas Registry сосуществуют с legacy texture inheritance |
| Real Estate | `house` + произвольные опциональные меши, отдельные Model Asset IDs деталей, door optional, сокеты, Studio Sync | Студийные размещённые экземпляры и publication revisions должны проверяться отдельно |
| House Sockets | Дверные ручки, замок, сундук, дым, лифт/перенос по этажам, debug USE/AIM | Некоторые элементы остаются заглушками; наводка проверяется клиентом, дистанция и права — сервером |

## 4. Character / actors / combat

- Runtime персонажа не должен зависеть от `Humanoid` для собственного custom-controller; совместимость с Humanoid необходима в предусмотренных точках взаимодействия.
- `CharacterSpatialRoot` определяет корень для серверных пространственных проверок, а не имя видимого MeshPart.
- Боевая область melee — объём, следующий за авторским движением `EquippedWeapon`, ограниченный дальностью; один sweep может задеть несколько целей. Обязательны серверная валидация, правила повторного hit и dead/respawn cleanup.
- Weapon slug и анимационные semantic slots независимы от конкретного персонажа. Существующие ID анимационных клипов, биндинги, skeleton checks и непрерывность attack loop сохраняются.
- Для NPC и Monster разные lifecycle/policy допустимы, но общие actor-примитивы не копируются. Переименование внешних полей — отдельная versioned migration.
- Facial animation / смена спрайтов глаз обсуждались как **предложение**, не являются реализованным текущим subsystem и требуют отдельного визуального/технического ТЗ.

**Characters · M172 (UI-first):** единый `Reg + Publish` с последовательным отчетом по регистрации, Roblox publication и Studio, отдельно `Save Identity` (миграция ID/paths), `Save Starting Stats` (SQLite + JSON/Luau export, без Model Sync), `Reset` выбранной формы и `Set as Startup`. При частичной ошибке Studio нельзя считать Roblox upload отменённым. Подробности и критерии проверки — [Characters Pipeline M172](../workflows/CHARACTERS_PIPELINE_M172_RU.md).

## 5. Asset Manager и публикация

- Источник (`assets/source`) отделён от подготовленной FBX-копии (`assets/prepared`) и опубликованного Model/Image/Animation ID. Изменения публикации не изменяют исходник автоматически.
- Общая подготовка skinned FBX — `system/asset-manager/model_publication.py` + `bone_weight_survival.py`; должна сохранять все кости, rest pose и геометрию, валидировать веса **всех** вершин, не больше четырёх положительных нормализованных influences. Для невзвешенных вершин действует текущая политика nearest-authored-bone-head. Результат Blender round-trip не заменяет проверку Roblox scale/binds после импорта.
- Публикация исходно статического меша не требует искусственной Armature. Реальный `house` — обязательный Mesh с `house_armature`; `door` и прочие детали опциональны, для каждой присутствующей детали отдельная публикация/ревизия.
- Roblox Studio **не восстанавливает** отсутствующие кости вручную (`StudioRealEstateSocketRecovery` удалён в M153); обязательна валидация фактически опубликованного рига до замены шаблона.
- Общий текстурный атлас — версия/вариант с ID из **Atlas Registry**. Image Asset ID относится к варианту, не к каждому потребителю. `texture_reference_slug` остаётся совместимым legacy-отношением; разрешение ID/статуса должно следовать актуальному реестру и не создавать повторный upload.
- Статусы `PUBLISHED` / `UPDATE_AVAILABLE` / `pending_studio_sync` должны отражать реальные версии и подтверждения Studio, а не только имя файла или успешность HTTP-команды. Смена shared atlas не должна сбрасывать опубликованные Model IDs.
- Пример проверенного исторического случая M162: `structures_01_2048x2048_atlas.jpg` и Stone Fence / Pillar / Wooden Fence / Wooden Fence Pillar / Stone Ladder — один Image Asset ID, отсутствие ложного `UPDATE_AVAILABLE` после общего refresh.

## 6. Real Estate: authored sockets и взаимодействия

- Сокеты — реальные Blender Bone под своим MeshPart; не подменять Attachment с приблизительной координатой. Списки имён и радиусы — [`HouseSocketContract.luau`](../../src/shared/world/HouseSocketContract.luau).
- При **открывании** дверь временно отключает `CanCollide` только у частей своей `DoorAssembly` и восстанавливает их индивидуальные значения после завершения tween или cleanup; **закрывание** не отключает коллизию. При этом остальные коллайдеры дома не меняются. Требуется фактическая проверка физики с несколькими игроками в Studio Play.
- Дверь вращается как жёсткий `DoorAssembly` вокруг authored hinge через `Model:PivotTo`; `Bone.Transform` не меняется. Для двух ручек общая табличка: когда снят замок и дверь закрыта — `E` открыть, `F` навесить замок. При открытой — `E` закрыть; во время движения навесить замок нельзя. Снятие навесного замка — `E` на padlock socket с ключом.
- **Тестовый ключ** `KEY: OWN / LOST` разрешён только в Studio; текущая проверка ключа — заглушка, не production inventory. Цвет слова «ключ» отражает наличие (зелёный / красный); сервер принимает окончательное решение.
- Лифт: `elevator_01/02/03_socket` являются **кнопками вызова**, а при назначении этажей 1/2 персонаж прибывает строго на `house_floor_01_spawn_socket` / `house_floor_02_spawn_socket`. Отсутствует authored destination → отказ. Для третьего этажа в текущей политике сохранён переход к `elevator_03_socket` (не обещание готового floor-03 spawn).
- Лифт и сундук: `USE` = расстояние персонажа до socket (сервер), `AIM` = пересечение луча из **центра прицела** с виртуальной сферой socket (клиент), а также физический raycast до зоны по `CanQuery`-препятствиям. Оба условия обязательны для отображения. Значения по умолчанию: лифт USE 10 / AIM 5, сундук USE 8 / AIM 4 studs. Студийный debug показывает и независимо изменяет обе зоны; обычные door/padlock используют иной prompt flow. Начиная с M449, Options → Sockets задаёт постоянные USE/AIM-параметры для всех интерактивных House и Campfire сокетов. HS Studio Debug переопределяет их только временно в Play (атрибуты игрока). HEAD/spawn/chimney не интерактивны и не настраиваются как радиусы.
- Контракт AIM **не** гарантирует блокировку объектами `CanQuery=false`. Не допускать невидимых queryable Parts, меняющих combat/headshot raycasts. UI проверки не заменяют серверную проверку прав и дистанций.
- Дымоход: постоянный дым; сундук/замок могут быть процедурными placeholder Parts до публикации моделей.

## 7. Предстоящие требования и критерии завершения

**P1 — защитить существующие механики и данные:** отсутствие regression при повторном Studio Sync, смене общего атласа, публикации skinned FBX, teleport/door/lock; проверка на настоящих размещённых экземплярах и обеих моделях персонажей. Приоритет не означает, что найден конкретный дефект.

**P2 — завершить архитектурную декомпозицию:** чистый `verify`, ответственность Python stores, UI debug, разделение политики/механики house sockets, actor naming. Очередность, статусы и точные non-goals — [roadmap](../architecture/REFACTOR_ROADMAP_RU.md).

**Будущие игровые системы:** дальнейшая MMO-персистентность, инвентарь и реальный ключ, экономика, квесты, права собственности, финальная мимика — это открытые продуктовые решения, которые нельзя выводить из одного лишь наличия папок или заглушек. Для них нужны отдельные требования, владельцы состояния и acceptance tests.

## 8. Definition of Done для следующих изменений

1. Названа конкретная подсистема, API/Remote/asset contract и критерии успеха. Миграции, если требуются, описаны до запуска.
2. Нет потери FBX/atlas/publication ID, данных SQLite, authored mesh/bones, placed model CFrame. Если change intentional — описана версия и процедура отката.
3. Статические и focused-тесты проходят, `verify.py`, Luau preflight и подходящие JS/Blender проверки пройдены; известные skipped/failed названы явно.
4. При UI/physics/animation/Studio изменениях выполнен отдельный **Studio Play/Edit smoke** либо прямо указано, что он не выполнялся.
5. Патч применим к объявленной базе через `git apply --check`, scope ограничен, в handoff описаны изменения и риски.

**Порядок разрешения расхождений:** source/runtime contracts + современное ТЗ выше, затем [действующая архитектура](../architecture/CURRENT_ARCHITECTURE_RU.md); отчёты M1–M162 в `docs/history` — свидетельства истории, а не автоматически действующие требования. Непроверенные подробности остаются открытыми, их нельзя подменять догадками.

### Обязательная редакторская безопасность Location Assets (M216)

Sync Studio работает строго по одному выбранному опубликованному Location Asset.
Запрещено пересоздавать размещённые Models/MeshParts или менять их трансформации,
структуру и физику. Допустимы только опубликованные Image Asset IDs в TextureID
и существующем ColorMap плюс метаданные-ссылка Model Asset ID. Изменение FBX
выводится как pendingGeometry, без ложной отметки о применённой геометрии.
Сохраняется отдельная append-only история изменений ID в Host Agent и журнал
внутри размещения. См. M216 workflow.


## M531 · Guided GP, RunSpeed и отдельные специальные касты

См. `docs/workflows/M531_GUIDED_COMBAT_RU.md` и KBN-0025–0030. Database владеет RunSpeed игрока и привязанных монстров. Debuff trigger `cast`; отдельная special-action, визуализация без изменения навигации; GP отчёт серверный, неперсистентный. Studio-приёмка открыта.

## M532 · Headshot и восстановление теста GP

Headshot melee: 32 studs вдоль проверенного reticle ray, независимо от AttackRadius, только уже валидные цели сектора. GP экспортирует завершённые строки на любом шаге, Retry/Skip и автоматический GP_TRIAL; временный melee timing-only fallback ограничен Studio GP, отдельно маркируется. См. `docs/workflows/M532_HEADSHOT_GP_RECOVERY_RU.md`. Баланс без изменений; KBN-0025 не принят в Studio.

## M533 · Targeted Status Effects

См. `docs/workflows/M533_TARGETED_STATUS_EFFECTS_RU.md`. Poison/Bleed/Slow — 10 с, Root/Silence — 5 с, Stun — 3 с; Slow −30% (с M545 −40%). Начатый направленный дебафф не промахивается по геометрии обычного удара. Отмена невалидного каста сохранена. Poison следует за игроком, Stun использует unaware. Studio-приёмка открыта.

## M534 · GP male, 2hs и dualswords

См. `docs/workflows/M534_MALE_GP_WEAPON_ANIMATIONS_RU.md`. Только Studio GP: human_male, bigsword из newbie_slayer_01, dualswords — два newbie_sword_01. Небоевые weapon slots берутся из 1hs, атаки — из собственных 2hs/dualswords. Отсутствие авторского таймлайна маркируется timing-only; реальный клип может проигрываться как preview. Female, production bindings, параметры баланса и опубликованные ID не изменены.

## M535 · Bigsword left grip

Обычная экипировка персонажа и GP: bigsword крепится к weapon_grip_l, как bow; sword/dagger и основной клинок dualswords остаются справа, второй клинок dualswords — слева. NPC сохраняют явно выбранную руку. Используется существующий BoneModelMount и WeaponTargetBoneName; анимации, таймлайны, данные и опубликованные ID не меняются. Studio-приёмка: проверить крепление в idle/run/attack на human_male и смену оружия.

## M536 · Monster target lock

Во время обычной атаки и направленного каста монстр использует жёсткую цель поворота в общем `ActorFacingTracker` (один scheduler, без записи CFrame физического root). Обычный Hit направлен на серверно выбранную цель: обход вокруг монстра в радиусе больше не создаёт промах из-за угла корпуса. На Hit сохраняются проверки живой цели, GP-изоляции, текущей дальности, высоты и LOS. Выход из радиуса, препятствия и отмена атаки остаются валидными способами избежать удара. Навигация, ranged retreat, self-buff, атаки NPC/игрока и численные параметры не меняются. Studio-приёмка: `system/verify/studio_m536_monster_target_lock.luau` и круговой бег вокруг melee/ranged в GP; проверка поворота, урона, препятствий, возврата и смерти. KBN-0025 остаётся открытым для приёмки.

## M537 · Design / Favorites (tooling only)

Канонический продуктовый план: [KBN-0031 · Design](../kanban/specs/KBN-0031.md). План первого релиза — 6 зон, LVL 1–30, 9–12 часов до B; цели каждого уровня, не измеренный баланс. Без классов; навыки изучает каждый, применение ограничено оружием; scaling utility по грейду пока предложение. Kanban favorite — revisioned метаданные. Runtime/Database не меняются.

### M550 · Прогрессия и виды монстров
- M552: базовая ATK персонажа = 5 + Levels.attackBonus; первый level up +1, последующие прибавки растут на средний арифметический относительный прирост стокового оружия между соседними грейдами, делённый на число переходов (4, затем 5). Прибавки округлены до сотых, накоплены в Database. HP фиксировано для всех игроков: однократная компенсация от M549 по среднему относительному приросту фактического целочисленного обычного урона стокового оружия доступного грейда. DamageService, оружие, AS, радиусы, XP, Gold и атаки монстров не меняются. GP-приёмка необходима: компенсация средняя, на границе грейдов возможны падения HP относительно предыдущего уровня. Skilled наследуют HP; прежний шаг 0,25 удалён. Оба варианта M551 отменены.
- Database: nameEn/nameRu отдельно; общий радиус и Aggressive по непустому nameEn; безымянные записи независимы. Индивидуальные overrides спавна сохраняются.
- AG справа от GP: локальная визуализация текущей зоны включена по умолчанию и не зависит от открытия панели; Show radii отключает тонкие контуры агро (красный — aggressive, серый — passive). Sync применяет тестовые значения и отправляет только изменённые виды через авторизованный Studio Bridge. Сохранение подтверждает ответ агента; после сохранения Rojo Sync для следующих запусков.
- Над монстром локализованное имя, красная * для агрессивных, Lv.N / Ур.N. Поиск Database не изменяет данные.

### M561 · Experimental Monster Navigation / Rescue Routes (историческая основа; алгоритм заменён M566/M569)

В Studio обычные монстры, GP group и основные GP-зоны 1–6 используют экспериментальный навигатор (Options → Monster Navigation · Experimental, по умолчанию ON). Guided/Skilled/резерв и опубликованные серверы сохраняют прежнее поведение. NPC и старая реализация `MonsterChaseNavigation` не изменены. `MonsterNavigationDispatch` — единственная точка выбора и очистки. Преследование во время активной анимации атаки остаётся прежним; эксперимент владеет Chase/Return, а не боевым таймлайном.

- Замер фактического 3D-перемещения и накопленной ожидаемой дистанции раз в 1 с, порог 50% (учтены Slow/Root/Stun). При обычном беге геометрические запросы не выполняются. При застревании — пара горизонтальных лучей от верха визуального RootCollider и уровня ног. Terrain исключается из запросов, но сохраняет физическую коллизию. Высокая коллизия — тонкий поиск на уровне головы (0,2 × 60 × 40 studs), ограниченные кандидаты у краёв. Низкая/ступенчатая — проверка фактической поверхности и физический вертикальный подъём с временным LinearVelocity, без телепортации/отключения коллизий. Принимается кратчайшая оценка доступного варианта: локальный подъём/обход или Rescue Route. Проверка прямой доступности при обходе раз в 1 с, в том числе луч до верхней точки RootCollider цели и объёмная проверка. Неудачная точка временно исключается, повтор через 1,5 с. Home Leash / Death Chase остаются внешней политикой.
- Studio Plugins → game1 → Rescue Routes: New route · draw, щелчки по поверхности (включая ступени), Close loop, Apply. Синие линии сохранены, зелёные — черновик. Исторически соединялись только совпадающие вершины; M579 автоматически связывает пересекающиеся отрезки в 3D. Вход/выход проецируются на отрезки; M581 отменил жёсткий допуск высоты входа, выход ограничен исходной дистанцией до цели (M582) и ранжируется по высоте; Dijkstra с min-heap, полный путь с входом/выходом. До 2048 рёбер на Place. Данные — `Workspace.Game1RescueRoutes` / Folder / нумерованные Vector3Value; нет физических runtime-маркеров. Сохранить Place. Database → Main → Rescue Routes — read-only зеркало последней Studio-синхронизации, `assets/manifests/rescue-routes.json`; при ошибке HTTP локальный маршрут остаётся, Sync Database повторяет запись. Не является резервной копией Place. После ручного undo или переноса маршрута повторить Sync. Режим A/B — Options или Place attribute `Game1ExperimentalMonsterNavigation` (nil = Options).
- Runtime-атрибуты `MonsterRecoveryMode` (Direct / Collision / RescueRoute / Climb / Retry) и `MonsterRecoveryPoint` для диагностики в Explorer. Геометрические эвристики не гарантируют путь в лабиринте; маршруты не заменяют физику Terrain. Studio Play: низкий забор, лестница из нескольких MeshPart, кольцо со входом, два этажа, Root/Stun при подъёме, смерть/Return, Death Chase, профиль нагрузки. До приёмки эксперимент не включать на опубликованных серверах.

### M562 · Rescue Routes / безопасный каталог Studio

- Сохранённые маршруты выбираются только из списка Rescue Routes; Explorer не участвует в Edit/Delete. Повторный щелчок снимает выделение. Выбранный маршрут жёлтый, остальные синие, черновик зелёный. При сворачивании каталога выделение сбрасывается. New route сбрасывает выделение; до Apply или Cancel все операции удаления и переключения сохранённой строки запрещены.
- Route name и Catalog — редактируемые метаданные (`RouteDisplayName`, `RouteCatalog`). Каталоги группируют список, но не меняют физическую иерархию графа, UUID, координаты или связность. Старые маршруты отображаются в Unsorted, без миграции координат. Метаданные синхронизируются в Database вместе с прежними ID и длиной.
- Delete требует подтверждения выбранной строки; Cancel deletion не изменяет Place. Undo last deletion восстанавливает последний удалённый маршрут с исходным ID и метаданными и синхронизирует зеркало. Studio Undo/Redo остаются доступны; после них ручной Sync Database. Cancel draft не записывает и не удаляет сохранённый маршрут; закрытие окна приостанавливает черновик, Resume drawing продолжает. Локальные изменения сохраняются при ошибке HTTP. Навигация M561 и параметры баланса не изменены.

### M563 · Melee / ограды и узкие препятствия (резервные навигационные Blockcast удалены M566)

- Наклонный LOS не разрешает melee-атаку сквозь ограду: дополнительно проверяется горизонтальный луч на уровне ног и физический Blockcast корня к цели. На старте и на Hit действует одна проверка препятствий; во время активной атаки прямое преследование при преграде приостанавливается (проверка 0,2 с). Атака не прерывает активное карабканье. Исправление melee применяется и при старом навигаторе; NPC, ranged и параметры баланса не меняются. Terrain исключён из дополнительных проверок движения, исходный боевой LOS сохранён.
- Для узкой ограды поверхность измеряется также непосредственно за контактом нижнего луча, а не только в точке посадки за оградой. Подъём берёт максимальную измеренную высоту; сохраняются коллизии, физическая проверка пространства и ограничение по высоте головы. Studio-приёмка: игрок выше ограды, melee за оградой, узкий MeshPart, преследование на открытом месте, Root/Stun.
- При переходе к новой точке маршрута перезапускается замер прогресса, чтобы поворот не считался застреванием из-за длины хорды. `MonsterLastReturnReason` и `MonsterLastReturnRecoveryMode` сохраняют причину и режим на момент последнего возврата; `MonsterLastRecoveryEvent` фиксирует завершение, выход с маршрута или причину Retry. Правила Home Leash и таймер отсутствия урона не изменены, Death Chase сохраняет прежнюю территорию. Проверка melee действует также при реакции на полученный урон.

- При застревании, если пара центральных лучей не даёт точки подъёма, выполняется резервная пара тонких Blockcast по физической ширине корня на уровне ног и головы (верхний только при близком нижнем контакте). Это исключает пропуск коллизии через щель между блоками; допуск 0,35 studs сохранён, сравниваются только расстояния запросов одного типа. Атрибуты MonsterRecoveryProbe, MonsterRecoveryHeadDistance и MonsterRecoveryFootDistance фиксируют последний замер.

### M564 · Обход сплошной коллизии (проверки отрезков упрощены M566)

- Локальный поиск остаётся тонким слоем на высоте головы, только при восстановлении движения. Кандидаты — углы с запасом под физический корень; проверяются одноточечные и двухточечные пути вокруг одного препятствия (до восьми кандидатов, кешированные проверки входа/выхода). Полная длина пути сравнивается с подъёмом и Rescue Route. Это ограниченная эвристика, не Wall Follow и не глобальный Pathfinding. Проверка каждого отрезка сочетает луч и тонкий Blockcast.
- Retry не сбрасывается в слепой Direct: после паузы проверяется доступность цели или повторно выбирается маршрут/подъём; при отсутствии решения монстр стоит в combat_idle. Замер ожидаемой дистанции учитывает фактически прошедшее время. В Studio атрибуты `MonsterNavigationBackend`, `MonsterRecoveryActualSpeed`, `MonsterRecoveryExpectedSpeed`, `MonsterLastRecoveryEvent` (включая NoAccessiblePlan, CollisionSelected, RescueRouteSelected, ClimbSelected) позволяют различить неактивный эксперимент, застревание и отсутствие доступного пути. Home Leash/Death Chase, NPC, старый алгоритм и баланс неизменны. Приёмка: один высокий Part с игроком на противоположной стороне, стена шире области поиска с/без Rescue Route, низкая ограда, открытый проход, возврат домой.

### M565 · Удержание выбранного пути (правила выхода заменены M566)

- Выбранный Collision/RescueRoute удерживает управление до первой достигнутой точки; далее ранний выход требует двух последовательных проверок прямого прохода. Проверяется горизонтальный коридор на уровне ног в обоих направлениях (с учётом начального пересечения shapecast) и верхний луч. Конец маршрута не разрешает слепой Direct: при заблокированной актуальной цели — Retry. Обычные melee/ranged атаки и спецкасты не прерывают активное восстановление. Home Leash, Death Chase и смена цели остаются законными причинами остановки. `MonsterRecoveryPlanIndex`, `MonsterRecoveryPlanSize` и `ExternalNavigationStop` / `RouteExitBlocked` облегчают диагностику. Физическая приёмка Studio обязательна.


### M566 · Приоритетные лучи экспериментальной навигации

- Заменяет правила M563–M565 о резервных sweep-проверках, коридоре в обоих направлениях, двух подтверждениях и обязательном достижении первой точки. Direct: первичный горизонтальный луч от верхней границы RootCollider − 0,05 studs в сторону цели, длина min(горизонтальная дистанция до цели, MonsterAttackRadius). Сразу при входе в Direct и далее с интервалом recheckSeconds (1 с по умолчанию). Высокая коллизия запускает выбор альтернативы без ожидания падения скорости; нижний луч на том же отрезке, верхний результат переиспользуется. При застревании сохраняется парная проверка и физический подъём на низкие/ступенчатые поверхности.
- Collision / RescueRoute: раз в recheckSeconds сначала луч от головы к нижнему центру RootCollider цели + 0,1 studs (fallback на расчёт уровня ног, для Return — домашняя точка); только если свободен, повторяется тот же горизонтальный первичный луч. Один успешный результат обеих проверок разрешает выход; наличие препятствия не разрешает Direct даже при свободном диагональном луче. При завершении маршрута действуют те же проверки. Retry сохраняет остановку, если проход и альтернативы недоступны. Выбор по длине пути, leash, таймеры, граф и 3D-замер скорости сохранены.
- Убраны навигационные Blockcast для щелей, маршрутов и коридоров; поиск локальных углов — только тонкий слой и лучи, запас углов по радиусу сохраняется. OverlapParams создаются только при выборе альтернативы. Существующая отдельная боевая проверка melee и физические проверки подъёма не изменены. Геометрия предполагает отсутствие узких щелей. NPC, legacy, баланс, настройки и данные маршрутов не изменены. Приёмка Studio: высокая стена перед целью, низкая ограда, лестница, маршрут с заблокированным выходом, движущаяся цель.

### M567 · Диагностика навигации в Server Output

- Только Studio, опционально: `workspace:SetAttribute("Game1MonsterNavTrace", true)` в Server Command Bar, отключение `false`. Необязательный `Game1MonsterNavTraceFilter` — подстрока имени модели. Префикс `[MONNAV #id name time]` позволяет связать события одного агента. Логируются выбранный backend, AI_ACTION, координаты тела и цели, фактические PRIMARY_HEAD/PROBE_HEAD/PROBE_FOOT/HEEL_RAY (начало, конец, попадание, расстояние, collision group), замер скорости, стоимость кандидатов, точки плана, переходы состояний, MOVE_TO, причины Retry/Return, внешние StopNavigation/ClearPath с источником вызова, начало атаки и проверка attack pursuit. Движение/координаты выводятся не чаще раза в секунду, смены состояний — по событию. Новых пространственных запросов нет. Алгоритм M566, настройки, данные баланса и маршруты не изменены. Проверка поведения в Studio по логам обязательна.

### M568 · Взаимоисключающие политики преследования

- Database → Main → Spawn Zones: отдельные колонки Death Chase и Home Leash · studs. Studio → Monster Spawns: явный выбор одного режима, числовой радиус только для Home Leash. В записи сохраняется последнее числовое значение для обратного переключения; оно не является активным ограничением в Death Chase. Существующие спавны и defaults видов не перезаписываются. Для старых записей без override наследование флага соответствует Database.
- Death Chase не зависит от наличия территории: при одной однозначной `Game1MonsterZone` действует её граница, без неё (или при неоднозначном пересечении) радиуса и тайм-аута отсутствия урона нет. Home Leash и Death Chase не переключаются автоматически. AI, Experimental Navigation и ranged retreat используют общую политику `MonsterDeathChasePolicy`; обычный Home Leash сохраняет радиус и таймер. Возврат домой разрешён из-за пределов ограничения. Guided/group/Skilled-калибровка сохраняет прежнюю политику. Атрибут `MonsterPursuitMode` показывает фактический режим; активный Death Chase удаляет `MonsterHomeRadiusStuds`. Проверка в Studio: погоня более 30 секунд и за пределы 150 studs, маршрут за радиусом, выход из размеченной территории, возврат при смерти цели. Алгоритм навигации и NPC не изменены.

### M569 · Приоритет выхода Rescue Route (исторический; ограничения поиска заменены M574)

- Среди доступных выходов выбранного в M586 маршрута, не превышающих исходную 3D-дистанцию до цели (M582), выбирается сначала минимальный абсолютный перепад по Y относительно пяток цели, затем минимальная дистанция до цели в 3D, затем полная длина пути при равных выходах. Для наклонного отрезка берётся ближайшая к высоте цели точка внутри сферы исходной дистанции до цели; также проверяются 3D-проекция и границы допустимого отрезка. Историческое ограничение 2 studs на вход отменено M581; для выхода заменено приоритетом высоты, без жёсткого порога. Радиус поиска входа, проверка соединения, связность графа и политика преследования сохраняются; прежний лимит 8 отменён M574. Недостижимый выход не блокирует более низкоприоритетный достижимый выход из набора кандидатов.
- Стоимость выбранного Rescue Route по-прежнему сравнивается с локальным обходом и подъёмом по полной длине. `CANDIDATES` в MONNAV дополнительно выводит `exitHeightDelta` и `exitDistance`. Другие лучи и механика движения не меняются. Физическая приёмка Studio необходима.

### M570 · Database: редактирование Spawn Zones

- Main → Spawn Zones: компактная редактируемая таблица, общий Save changes, черновики сохраняются при переключении вкладок. Выбор вида/уровня, радиус, количество, агрессивность, радиус агро, режим преследования, Home Leash, Respawn и Enabled. Home Leash скрыт при Death Chase, значение сохраняется. Координаты, Place/map и ID только для чтения; создание, перемещение и удаление остаются в Studio. Обновление каждые 3 секунды только без черновика и активного поля.
- POST `/api/monster-spawns/database-update` изменяет только существующие зоны, проверяет ревизии всех строк, валидирует поля и сохраняет пачку одной транзакцией реестра спавнов. При смешанном сохранении сначала баланс, затем спавны; ошибка второго этапа оставляет черновик и сообщает о частичном сохранении. Маркеры Studio обновляются через Refresh Database / restore markers, конфликт устаревшего черновика отклоняется. Rojo Sync перед Play. Пользовательские файлы спавнов/баланса и навигация не изменены патчем.


**M638: владелец утвердил red dummy при отсутствии LOD1. Общий клиентский Runtime FULL / LOD1 / UNLOADED для Monster и NPC, runtime registry с M637 identity/alignment, красный статический Part без collide/query/touch/Animator, native weld к root, замена verified mesh после async readiness. Hysteresis, player distance, combat pin, local visibility/effects, attack sampler binding и overhead gate; existing world Heartbeat, отдельная capped MNPC lane. Реплицированный native FULL маскируется, но не гарантирует прекращение Animator; M632 остаётся Studio-only OFF, production shell-only/demand, strict native isolation и A07 NOT_RUN. Реальные LOD1 не блокируют продолжение. См. M638_MNPC_RUNTIME_LOD_RU.md.**

**M639–M645 · действующий runtime contract:** общий opt-in Runtime demand (Options → MNPC LOD → Server rig demand, `mnpcDemand.enabled`, default OFF с M640) заменяет Studio-only M632 pilot. Оба спавнера допускают initial shell-only после квалификации ранее готового FULL того же типа/шаблона; обычный первый spawn, GP/rise и неподдержанные конфигурации сохраняют прежний путь. M645: общий `MnpcLodPolicy.Resolve` и фактический AttackRadius каждого игрока для клиентского LOD и server demand; FULL exit F+h, enter F−h, без отдельных prewarm/release margins и глобального debug reach. Сервер сохраняет риг при потребности хотя бы одного игрока или активном gameplay pin; hold 5 s, near-first admission, placeholder до ready/full. Код server demand доступен в опубликованном Runtime; одиночное восстановление и бой приняты владельцем после M645 (A08 PASS). Телепорт и строгая изоляция реплицированного Animator при нескольких игроках не подтверждены; полная A07/T08 остаётся открытой. Без opt-in действует M638 visual LOD. Реальные LOD1 не обязательны. См. M639_MNPC_RUNTIME_DEMAND_RU.md.
