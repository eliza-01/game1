# Eyesland / Game1 — ТЗ: Runtime LOD Streaming

**Решение владельца после M626 · следующий этап:** функциональная загрузка окружения принята («загрузка работает»); полная A03/A06, стресс-тесты и Profiler отложены, Incremental Studio Preview отложен. Socket & Door Optimization отложена до новой системы взаимодействий с корректным выбором этажа. Следующая задача — [MNPC Visual LOD (ТЗ)](MNPC_LOD_SPEC_RU.md), KBN-0037-T08/A07: FULL / LOD1 / UNLOADED, один цельный статический mesh на визуальный вариант, без клиентского визуального Animator/скелета начиная с LOD1, движение сохранено. Серверная AI/боевые Bone-based hitboxes независимы от LOD наблюдателя; сначала архитектурный аудит и engine pilot разделения authoritative pose и visual rig. Существующие Location/House contracts не меняются. MNPC пока не реализован.

**Карточка:** KBN-0037 (клиентская производительность), связанные KBN-0007 / KBN-0017.
**Рабочая база:** диагностический срез M613 от 27.11.2026 + подтверждённая последовательность M614–M623; M624 — диагностика и подготовка приёмки. Патчи M619–M624 code/oracle checked в восстановленной sandbox-копии, Roblox Studio/DEV/Mobile и профильная приёмка не выполнены.
**Статус:** этапы 0–5 реализованы в Runtime; этап 6 IN_PROGRESS. M625: event-driven composite effects реализованы; порционный Studio Preview отложен владельцем как необязательный. Реальная приёмка открыта. В этапе 1 выбрано дерево 3D influence bounds (BVH) вместо сетки.

## 1. Цель

Масштабировать клиентский визуальный стриминг мира: убрать глобальные обходы и сортировки в стационарном состоянии, сократить повторные проверки прототипов, распределять реальную работу сборки и удаления по кадрам. Сохранить действующие правила LOD и серверные механики. Не заменять Roblox StreamingEnabled собственным движком стриминга. Не обещать снижение FPS/CPU/RAM до замеров.

## 2. Исходное состояние (статический аудит M613)

- `src/client/world/LocationWorldStreamer.luau`: один Heartbeat; Location tick 0,25 с, tagged visuals / House Resolve — 1 с. Location records пересчитываются и сортируются целиком; приоритет сначала выгрузка, затем близость. `MAX_CHANGES_PER_TICK = 8`, стоимость большой сборки ограничивается этим же значением. Отдельная доля общего бюджета выделяется домам.
- `src/shared/world/LocationLodDistancePolicy.luau`: `Resolve` для режимов full/lod1/lod2; `ResolveHouse` для full/lod1; `VisualWithin` для отдельных tagged MeshParts. Существующие пороги и гистерезис, включая равенство на границе, являются эталоном. Location использует 3D-дистанцию до snapshot pivot; House — `SurfaceDistance` до ориентированных bounds каждой части; tagged visual — до текущих bounds.
- `LocationLodAssembly`: валидация числа MeshPart и published pivot, bounds, единый масштаб по доминирующей оси, выравнивание основания, имена для appearance; синхронное создание всей сборки. Поддержка многочастного LOD (2–64 MeshPart по действующему контракту).
- `LocationCompositeVisual`: FULL привязан Weld к существующим серверным proxy; эффекты и rig остаются серверными, локальная видимость следует фактическому состоянию. Отложенное появление technical root допустимо.
- `HouseVisualAdapter`: независимый LOD частей, static FULL через `InsertService.CreateMeshPartAsync`, максимум 4 pending, повтор после ошибки 15 с; moving требует proxy. LOD1 из общего cache. `Resolve`, `Step` и `FollowMoving` перебирают записи; `Step` сортирует дома. Generation уже защищает часть асинхронного FULL. Текущий переход может удалить старую деталь до готовности новой — устранение этого визуального зазора является явной задачей ТЗ, а не сохранением дефекта.
- `StudioLodPreviewAdapter`: отдельный авторский preview через существующий scheduler; не включать Runtime-логику без manifest. Сохранить самостоятельность Studio preview и tagged distance visuals.
- Патчи M614–M618 не изменяют перечисленные клиентские LOD-модули; M616 затрагивает серверные HouseElevator/HouseSocket — их актуальные контракты сохранить.

## 3. Защищённые контракты

1. Сохранять manifest validation, snapshot placement IDs, mode, distances, hysteresis, fallback LOD, профиль off/full/lod1/lod2 в рамках их действующих областей. Не добавлять LOD2 домам, если он не поддержан действующим контрактом. Ничего не перепубликовывать.
2. Отдельно хранить desired (по Policy), actual (реально показан), pending/job generation. Гистерезис считается по прежнему desired, а не actual или fallback. Начальное nil-состояние и точные условия >= / <= из Policy обязательны. Не смешивать отсутствие модели и желаемое UNLOADED.
3. Не менять метрику расстояний, pivot, масштаб, вращение, placement transform, имена частей, материал/цвет/atlas/alpha/double-sided и правила индивидуальной покраски.
4. Не менять Workspace StreamingEnabled, серверные коллайдеры, CanCollide/CanTouch/CanQuery серверных объектов, сокеты, дверные замки, лифты, эффекты, rig_carrier и серверные анимации. Клиентские клоны по существующим контрактам не создают физических коллизий; дверь сохраняет специальное взаимодействие через DoorInteractionRaycast и его Bind.
5. Не изменять Monster AI, NPC AI, Rescue Routes, AI Scheduler, Navigation Budget, combat M614 и их Options. Серверные лучи и движение не зависят от визуального LOD клиента. Проверить это на практике с двумя клиентами.
6. Сохранить существующий pipeline Authoring → Rojo Sync → Scan Place → Save to File → Preflight → Prepare Runtime → DEV. Runtime не требует дополнительного Rojo Sync после сборки. Схему данных и манифест менять только при доказанной необходимости и синхронно со всеми производителями и потребителями.
7. Один владелец визуального состояния, один существующий Heartbeat. Без нового фонового цикла на объект, Workspace:GetDescendants в кадре, глобального опроса всех объектов в steady state, новых RemoteEvents или дублирующих рабочих реализаций. Диагностика по умолчанию выключена.

## 4. Целевая архитектура

`LocationWorldStreamer` — координатор; `StaticPlacementIndex` — консервативная пространственная выборка; `LodTransitionQueue` — уникальные заявки, dirty/invalidation; `LodPrototypeCache` — shared readiness и immutable metadata; `LodWorkBudget` — учёт работы; `LocationLodAssembly` и `LocationCompositeVisual` — специализированные сборщики; `HouseVisualAdapter` — дома; `LocationLodDistancePolicy` — единственный источник решений о дистанции. Имена новых модулей предварительные, сначала найти существующие переиспользуемые хелперы. Общие механизмы не должны знать подробностей дверей, домов или деревьев.

## 5. Этап 0 — Behavior Contract Tests

До изменения исполнения создать эталонные тесты старого Policy и трассы desired/actual: полное сканирование по исходным правилам; фиксированные camera paths, точные пороги, гистерезис, разные modes, первоначальное состояние, отсутствие LOD1, fallback и восстановление. Различать эквивалентность desired и допустимое изменение времени actual из-за бюджета. Отдельно зафиксировать существующий порядок выбора ближайших заявок, исключить голодание. Проверить реальные имена тестов, существующие ошибки и состав диагностического архива. Не ослаблять регрессии. Этап можно включить в первый патч.

## 6. Этап 1 — Static Placement Index

- Построить индекс один раз по валидному Runtime Manifest. Для обычных Location — по 3D pivot и максимальному радиусу перехода с запасом hysteresis; для домов позднее — консервативные bounds частей. Индекс не определяет LOD, только отбирает кандидатов. Учитывать разные hide per asset, включая большие радиусы, отрицательные координаты, высоту, повёрнутые bounds, крупные сборки.
- Каждая выборка включает объекты новой области, уже видимые, pending, dirty, а также объекты, которые требуется выгрузить при выходе из области. Не отбрасывать pending из-за отсутствия модели. Телепортация сразу перестраивает локальный набор без прохода по всей карте. Пустые ячейки/разреженные карты не должны приводить к перебору огромного куба пустых клеток; размер ячеек определить по геометрии текущего манифеста, не добавлять пользовательские Options без нужды.
- При первом resolve сохранить nil semantics для записей в потенциально видимой области; остальные можно считать desired UNLOADED лишь если гарантированно за пределами исходных порогов. При последующем входе в область сохранять историю hysteresis, включая предыдущий UNLOADED. Сравнивать с эталоном на последовательностях кадров, а не только отдельных точках.
- Убрать сортировку всех placements; сортировать только фактические pending transitions на этом этапе, сохранив приоритет выгрузки и ближайших загрузок. Не менять 0,25 с Location и 1 с House на первом этапе.
- Приёмка: ноль пропущенных кандидатов относительно полного перебора; камера на месте не вызывает глобальную пересортировку; дальние и высокие объекты корректны, телепорт освобождает старую область; нет изменений серверного кода.

## 7. Этап 2 — Dirty / threshold transition queue

- Использовать запас до ближайшего действующего порога с учётом desired и hysteresis, а не просто фиксированный шаг движения камеры. Дистанция до фиксированного pivot или bounds меняется не больше, чем длина смещения камеры между проверками; консервативный запас позволяет безопасно пропустить resolve. На равенстве порогу перепроверять. Не считать только последний frame delta: использовать смещение от позиции последнего resolve, а также гарантировать повторную активацию объектов за границами кандидатов.
- Переходы по-прежнему определяются Policy в прежние интервалы наблюдения; не обещать обнаружение пересечения между двумя прежними samples. Камера неподвижна — distance work отсутствует при стабильном мире, но очередь, retries и события репликации продолжают обслуживаться.
- Одна заявка на placement/part, с desired generation, приоритетом, жизненным циклом. При изменении desired обновить заявку, отменить stale job; выгрузку обслуживать приоритетно, загрузки — близкие с aging/справедливостью. Нет повторного создания запроса при неизменном desired. Не считать отмену ошибкой шаблона.
- Смена CurrentCamera, teleport, появление/исчезновение proxy/root, изменение prototype readiness, изменение актуального цвета/материала — самостоятельные invalidation, даже при стоящей камере. Не пересканировать весь Workspace. Для динамических объектов отслеживать действующие связи, не заменять immutable distance semantics без отдельного решения.
- Приёмка: стационарный steady state — 0 глобальных сортировок, 0 повторных distance resolve для неизменных записей; пороги не пропускаются; отсутствие starvation и бесконечных retries; fallback не блокирует дальнейшую загрузку.

## 8. Этап 3 — Prototype Readiness Cache

- Кэш по identity экземпляра шаблона, generation и варианту, а при необходимости по контракту ожидаемых компонентов (не один Boolean на slug). Различать missing / incomplete / ready / invalid. Переиспользовать существующие Count, expected mesh count, published pivot и проверку имён компонент FULL; кэшировать immutable metadata / bounds, не живые placement transforms.
- Отслеживать ChildAdded/Removed, необходимые attributes и замену/удаление prototype. Позднее появление cache folder и Ready учитывать без бесконечного ожидания; не считать неполную репликацию постоянным отказом. Реактивно будить только зависимые заявки. Ограниченный retry для ошибок, которые не дают события. Локальный failedAssemblies сохраняет различие ошибки placement и ошибки общего прототипа.
- Сохранить существующий fallback: не показывать неполную сборку и не уничтожать пригодную визуализацию при временной недоступности desired. Проверить порядок fallback LOD1/FULL, LOD2, замена stale generation, существующее состояние без шаблонов. Не путать structural readiness с фактической загрузкой GPU-текстур/меша; не добавлять глобальный ContentProvider preload.
- Приёмка: много размещений одного прототипа не выполняют повторную структурную проверку на каждом тике; поздняя репликация и повторная публикация/замена шаблона будят правильные записи; соединения очищаются.

## 9. Этап 4 — Incremental Assembly & Real Work Budget

- Заменить clamp стоимости фактическим учётом: клонирование mesh, подготовка appearance/transform, weld, создание/удаление элементов, старт асинхронного запроса и commit. Не скрывать большой объём за стоимостью 8. Измерять стоимость в единицах работы и опциональном мягком времени кадра; числа выбираются на базе тестов и позднее профиля, не выдавать за оптимальные. Clone/Destroy/Parent отдельных экземпляров и завершение API не являются гарантированно прерываемыми; твёрдый CPU deadline обещать нельзя.
- Переработать существующие сборщики в единый пошаговый контракт jobs (prepare / advance / commit / cancel / cleanup), не держать отдельный старый синхронный Runtime путь. Studio preview сохраняет совместимый контракт через тот же сборщик, если применимо. Bounds подготовки также кэшировать или бюджетировать. Не клонировать весь Model одним вызовом ради обхода бюджета.
- Готовить новые части вне видимой сцены; сохранять прежнюю модель до полной готовности новой. Commit без yield, в том же клиентском кадре; отсутствует одновременно видимая FULL и LOD и поэлементное появление дома. Для composite отложить активное связывание Weld с Workspace до безопасной стадии commit, повторно подтвердить proxy и актуальные CFrames. Эффекты переключать по actual. При выгрузке сразу снять видимость/отсоединить нужный bundle по бюджету, затем порционно освобождать его содержимое; не уничтожать серверный root.
- При смене desired, телепорте, пропаже root/prototype или ошибке отменить устаревшую сборку, безопасно очистить staging. Не допустить накопления staging, ограничить активные сборки и суммарную подготовленную геометрию. Разделить бюджет между commit/unload/build и обеспечить прогресс всех категорий. Для async completion — проверка generation и proxy identity до публикации; не применять старый результат после смены режима.
- Приёмка: сборка 1/8/32/64 мешей и composite FULL укладывается в заданный лимит счётчика операций с переносом на следующие кадры; нет двойных визуалов, пустого перехода при готовой прежней модели, stale commit и утечек. Проверить реальную длительность неделимых операций позднее в MicroProfiler.

## 10. Этап 5 — Real Estate integration

- Подключить HouseVisualAdapter к общему индексу/dirty queue/бюджету; независимые записи частей по snapshot bounds, без whole-house render gate. Для отсутствующего LOD1 сохранить FULL → UNLOADED по собственному hide. Полностью сохранить масштаб, материал, атлас, alpha и proxy-owned color/material.
- Preserve `CreateMeshPartAsync` concurrency 4, retry 15 сек как начальные значения; результат async с generation guard и повторной проверкой живого proxy. Старый FULL/LOD сохранять до готовой замены, а не удалять в начале запроса. При ошибке загрузки старую визуализацию оставить, не создавать частично готовую замену. При UNLOADED старую модель действительно выгрузить.
- `FollowMoving` — только реестр реально активных подвижных частей, а не обход всех домов на Heartbeat. Привязка и очистка DoorRaycast, повторное появление proxy, изменение цвета/материала дома и движение двери/лифта не должны зависеть от перехода LOD. Использовать существующий механизм обновления/сигналы, не вводить отдельный кадр для каждой части.
- Не допускать голодания домов среди Location placements и наоборот. Сохранять действующее ownership интеракций; оптимизацию самих prompts/Raycast оставить будущему этапу House Interactions.
- Приёмка: частичная публикация LOD1 House5, переход каждой части, перекраска в разных LOD, двери/замки/лифт, отсутствующий proxy, proxy stream-out/in, камера неподвижна, отменённый async, no stale DoorRaycast. Сравнить отображение двух игроков с различными расстояниями до дома.

## 11. Этап 6 — Integration & Acceptance

Подтвердить Studio Authoring, Studio Runtime draft, опубликованный DEV PC и телефон. Самостоятельная Studio/Runtime проверка владельцем требуется, если среда разработки не запускает Roblox. Сценарии:

| Группа | Обязательные проверки |
|---|---|
| Distance | FULL/LOD1/LOD2/UNLOADED, full-only, off, точные пороги, hysteresis, неподвижность, zoom/camera switch, движение вдоль порогов |
| Space | разные высоты, отрицательные координаты, большие radii и bounds, поворот, масштаб, телепортация туда/обратно |
| Templates | поздний cache/attributes/children, fallback, template replacement, отказ API, recovery без движения камеры |
| Lifecycle | повторные циклы load/unload, отмена в середине сборки, удаление/появление root/proxy, stale async, очистка connections/staging |
| World | деревья, ограждения, multipart LOD, windmill, фонари/дым, rig_carrier, House5 с частичным LOD1, двери/замки/лифты |
| Server | коллизии, оружие/удары, Monster/NPC pursuit и Rescue Routes при выгруженной визуализации, два клиента с разным LOD |
| Delivery | manifest и Runtime Builder, Studio preview, отсутствие test hub в обычном Runtime, PC / Mobile DEV |

Профильные тесты: `test_location_lod_distance_phase1.py`, `test_location_lod_manager.py`, `test_location_runtime_build.py`, `test_location_runtime_streaming_pilot.py`, `test_m388_house_runtime_integration.py`, `test_m390_location_composite_runtime.py`, `test_m411_shared_lod_reuse.py`, `test_m412_house_part_lod.py`, `test_m426_studio_lod_preview.py`, `test_m501_runtime_stabilization.py`, `test_m504_multipart_location_lod.py`, плюс связанные тесты manifest/physics/interaction/kanban и новые сценарии. Перед установкой проверить, что каждый выбранный pattern реально находит тесты; не включать известные baseline failures в блокирующую команду без их исправления или явного объяснения. Сравнить старые падения на чистой базе.

## 12. Метрики и критерии завершения

Диагностические счётчики (opt-in): placements total, local candidates, exact distance resolves, global/local sorts, queue size/age, prototype validations, pending async, staging jobs/parts, clone/destroy/weld/commit counts, stale/cancel/fail, latency desired→actual. Steady state без изменений: никаких глобальных обходов, сортировок, повторных проверок готовности или новых сборок; только необходимое сопровождение активных движущихся частей и дешёвый scheduler check. Сценарии нагрузки: фактическая текущая карта и синтетические 500/2000/10000 placements, разные плотности и большие сборки; оценить рост стоимости относительно локальной плотности, а не гарантировать O(1) при любой сцене. Профилирование позже по согласованному общему этапу: CPU/frame time p50/p95/p99, FPS, RAM, spikes, задержка LOD, сравнение на одинаковых сценах и устройствах. Никаких фиктивных чисел эффективности. Карточка остаётся IN_PROGRESS до игровой и нагрузочной приёмки.

## 13. Порядок выдачи патчей

1. M619: эталонные тесты + Static Placement Index.
2. M620: LodThresholdCache + LodTransitionQueue.
3. M621: Prototype Readiness Cache + immutable assembly metadata / bounds.
4. M622: Incremental Assembly & Real Work Budget — Runtime Location (static/multipart/composite FULL); общий House budget и порционный Studio Preview остаются открыты.
5. M623: Real Estate Integration — общий spatial index, queue, work budget и lifecycle.
6. M624: Integration & Acceptance — opt-in diagnostics и матрица проверок, teardown Studio Preview. Реальная приёмка и оставшиеся оптимизации открыты.

Перед каждым патчем восстановить актуальную базу из дампа + подтверждённых патчей. Проверить производителей и потребителей, Rojo/Runtime, применение/обратную проверку, профильные тесты, Luau preflight и verify.py. Обновить Mechanics (LOD / House), основное ТЗ, архитектуру, AGENTS/Read First при необходимости, KBN-0037 и связанные карточки только по реальному прогрессу. Выдать один проверенный .patch, краткий отчёт, один PowerShell-блок (нижний регистр команд; проверка → применение → тесты → при необходимости install plugin → строго control-center-stop.ps1 и control-center.ps1). Не менять пользовательские manifests, настройки или данные без необходимости; независимый откат каждого этапа через Git. Без нового дампа, если цепочка восстанавливается.

## 14. Вне объёма

LOD для персонажей/монстров, изменение AI, переработка collision, публикация новых ассетов, замена Roblox StreamingEnabled, occlusion/frustum culling, изменение радиусов/гистерезиса, глобальный preload, отдельная переработка House Interactions, Overhead UI, Hitbox Pipeline и Character Creation. Дополнительные настройки бюджета PC/Mobile — только при необходимости после оценки, действующие Options сохраняются.


## M620 · Реализация этапа 2

M620: Runtime LOD этап 2 — LodThresholdCache (запас до порогов ±h, смещение от последнего resolve, точные границы и смена камеры) и LodTransitionQueue (одна заявка на placement, отмена/замена, сортировка только при изменении приоритета). При неподвижной камере BVH и стабильные дистанции не пересчитываются; fallback/proxy/effects продолжают обслуживаться. Aging 8 ticks; тяжёлая просроченная Location-заявка может получить полный бюджет на чётном tick, нечётный сохраняет резерв House. Policy, интервал и визуальный контракт сохранены. Кэш готовности, порционная сборка, Real Estate и Studio/DEV/профиль открыты.

Lua oracle: 129212 сравнений desired, 2356 samples; стационарный cache и lifecycle очереди проверены. Переходы Actual могут обслуживаться в другом порядке вследствие aging. Event-driven prototype/root invalidation остаётся этапом 3; до него используется прежняя периодическая reconciliation, включая ошибки сборки и позднюю репликацию. Геометрия и серверный код не менялись.


## M621 · Реализация этапа 3 — Prototype Readiness Cache

**Code complete:** `LodPrototypeCache.luau` event-driven cache по Instance identity, generation, variant и FULL component contract. Readiness состояния: missing / incomplete / ready / invalid. Слежение за поздним cache folder и Ready, prototype ChildAdded/Removed/Name, required attributes, direct child Name/Size/CFrame/MeshId и `Game1LodSourceName`. Неполные случаи получают максимум две bounded retries (1 с), missing template-folder scan ограничен двумя проверками до Ready; после Ready=true отсутствующие прототипы event-only.

Cache хранит frozen metadata: source MeshPart refs, relative transforms, count, published pivot, source bounds/base и FULL component map. `LocationLodAssembly.BuildMetadata` считает bounds один раз на prototype generation; `Assembly.Create` использует metadata. `LocationCompositeVisual.Create` использует FULL component map. Cache folder не блокирует streamer через WaitForChild(30): runtime продолжает manifest reconciliation, поздняя папка/Ready/children wake dependent records. Replacement generation форсирует атомарную замену старого visual. Placement-local `failedAssemblies` хранит prototype и generation; ошибка одной сборки снимает очередь этой заявки и переводит её к fallback, не инвалидируя shared prototype. `Streamer.Stop` очищает cache/queue ownership, connections, локальные визуалы и восстанавливает composite effects. House LOD1 использует shared cache и rebuild при stale prototype, но общий House index/queue/budget остаётся этапом 5.

**Checks:** M621 readiness/cache oracle passed: late folder, missing/incomplete/ready/invalid, component contract, bounded retries, replacement generation, metadata memoization, event cleanup. M619 and M620 profile tests passed. `validate_luau.py` passed. Roblox Studio, published DEV PC, physical phone, collision/navigation two-client and performance profile remain NOT_RUN. T03/A03 remains open.


## M622 · Этап 4 — Incremental Assembly & Real Work Budget (Runtime Location)

M622: Runtime Location stage 4 — `LodAssemblyJob` / `LodRuntimeWork`: detached incremental assembly (single mesh, multipart LOD, composite FULL); 12 build + 8 cleanup operation groups/frame, separate atomic commit reservation up to 132 groups, 16 queue checks/category/frame, one active job (≤64 visual meshes), at most two retired bundles. Commit revalidates proxy identity/current CFrames, preserves previous visual until swap and keeps effects tied to actual. Desired/prototype generation/root changes cancel staging; cleanup is incremental. Old Location cost clamp removed. House keeps independent 8/tick reservation pending stage 5; Studio Preview multipart drains the same job synchronously. Counts are not a hard CPU deadline; native streaming, effect traversal and Studio/DEV/Mobile profiling remain acceptance items. T03/A03 open.

## M623 · Real Estate Integration

M623: Real Estate stage 5 — every house part is a record in the common static BVH, threshold cache, aging transition queue and `LodRuntimeWork`. House influence uses a conservative sphere around scaled snapshot bounds; exact policy remains `ResolveHouse` with surface distance and per-part hide/LOD1. FULL acquisition (`HouseMeshRequests`) has four combined in-flight/ready slots, 15 s retry, generation and moving-proxy identity checks; async completion cannot publish. Detached result enters the common job, old actual survives until atomic commit, failure or absent preferred prototype preserves old actual; cold missing LOD1 can fall back to FULL. Missing unpublished part LOD1 retains FULL→UNLOADED. Shared unload/retirement handles committed geometry. Discard of a stale raw async MeshPart is immediate (bounded by four slots), outside the staged assembly counters. Only active moving parts are followed each frame; lost proxy detaches the owned mesh and removes DoorRaycast binding, stream-in rebinds using current CFrame and appearance. Static active parts refresh proxy color/material during local observation. Server physics, manifest, sockets and authority unchanged. Lua mocked lifecycle and mixed spatial/async oracles; actual Studio/DEV/Mobile, House5 interactions/two-client and profiling remain NOT_RUN. Preview still synchronous; T03/A03 open.

Сборка: `Prepare` создаёт job; `Advance` выполняет ограниченное число операций, включая вклад каждого target mesh в bounds, clone, configure/appearance, staging parent и weld. `BindForCommit` подтверждает все proxy до изменения CFrames и установки Part0; до commit weld не соединён с серверным proxy. `Release` передаёт готовый bundle placement; при отмене ownership list включает даже ещё не прикреплённые clones. Cleanup удаляет отдельные staged instances / retired direct meshes, не серверный root. Смена camera проверяется перед продолжением jobs даже между наблюдениями; очередь сохраняет поколение readiness. Независимые unload/build/cleanup lanes, большой atomic commit получает резерв при необходимости.

Начальные лимиты — группы операций, не гарантия миллисекунд и не оптимальные значения PC/Mobile; `Clone`, `Destroy`, `Parent`, поиск proxy и batch commit неделимы. Эффекты и native-stream-out reconciliation не входят в build/cleanup счётчик. House adapter пока выполняется в observation tick; его async и единый бюджет относятся к этапу 5. Studio Authoring использует тот же multipart builder через `Finish`, но пока не распределяет работу по кадрам.

Engine-independent Lua oracle: 1/8/32/64 parts static/composite, budget counters, swap, desired/generation cancellation, failed staging, proxy mismatch, concurrent unload and cleanup. Реальные Roblox meshes/welds, physics, PC/mobile и MicroProfiler NOT_RUN.

## M624 · Integration & Acceptance (IN_PROGRESS)

M624: opt-in Runtime LOD diagnostics (authorized Studio/DEV debug dock, PC/mobile), bounded capture with heartbeat/callback elapsed, queue/desired→actual latency, local candidates, sorts/cache/async/work counters, peaks and client memory at boundaries; no telemetry or new scheduler. Studio Preview teardown now disconnects Workspace subscriptions, restores authored visibility and destroys local folder. Authoring assembly remains synchronous; composite/tagged passes are measured, not eliminated. Actual Studio/DEV/PC/Mobile, two-client and A/B acceptance NOT_RUN; T03/A03/A06 remain open. See docs/workflows/M624_RUNTIME_LOD_ACCEPTANCE_RU.md.

[Инструкция приёмки и чтения отчёта](M624_RUNTIME_LOD_ACCEPTANCE_RU.md).

## M625 · Event-driven Composite Effects

M625: `LocationCompositeEffects` replaces the periodic global composite pass with shared manifest-path prefix subscriptions (`ChildAdded/Removed`) and scoped root `DescendantAdded/Removing`. Initial discovery once per resident root; actual LOD commit/native detach controls cached effects, not desired. Hidden authored Enabled state is restored on show, stream-out and Stop; late descendants and replacement roots are handled. Compiled paths are static (runtime rename unsupported). Observable external Enabled=true while hidden is suppressed and retained; false writes indistinguishable from the local false cannot be observed without an authoritative separate state, so dynamic server-controlled effects are not newly opted in. No new Heartbeat/remotes/manifest changes; doors, rotors, House effects and tagged visual pass unchanged. Owner deferred incremental Studio Preview as optional tooling. Real Studio/DEV/physical Mobile and A/B acceptance remain NOT_RUN; T03/A03/A06 open.

## M626 · Near-first Runtime LOD

M626 · Near-first Runtime LOD: после публикации M625 владелец подтвердил обычную работу без заметного ухудшения, но на слабом телефоне ближние ограждения догружались позже дальних домов. `LodLoadPriority` использует позицию HumanoidRootPart игрового персонажа (камера в меню/при отсутствии root), минимальную surface distance по authored bounds Location/House, кольца по 32 studs. Camera-based visibility/LOD thresholds и пространственный индекс не меняются. В общей очереди: unload отдельно, затем ближайшее кольцо, cold перед upgrade, aging только внутри класса и кольца. Ближайшее незавершённое кольцо ограничивает admission сборок даже при ещё отсутствующем template/proxy; 4 секунды без прогресса разрешают следующие кольца, поздний ассет остаётся приоритетным. При respawn/телепорте порядок обновляется без ожидания очередного 0,25 s sample; активная недопустимая сборка отменяется. Четыре async FULL slots и прежние бюджеты сохранены; при нехватке слотов для ближнего FULL разрешено освободить один готовый дальний detached result, не отменяя in-flight вызов. Без новых Heartbeat, массового PreloadAsync, remotes, изменений серверной физики, манифеста и Preview. Порядок управляет клиентской сборкой/публикацией и house FULL requests, а не гарантирует порядок native Roblox replication, CDN fetch или GPU render. Профилирование/стресс-тесты отложены по решению владельца; ближайшая практическая проверка — обычный вход в игру на слабом телефоне. T03/A03/A06 формально открыты.
