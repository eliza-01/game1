# Eyesland Development Kanban — порядок работы

Рабочие документы: `cards/KBN-XXXX.json` + `specs/KBN-XXXX.md`. Постоянный ID карточки **не равен номеру будущего Git-патча**. Номера уже применённых патчей и их подробности сохраняются в `docs/workflows` как история; план не назначает номеров заранее.

## Текущий фокус · 27.11.2026 · Performance review M605

**Текущий порядок (заменяет предыдущий):** Решение владельца 27.11.2026 (M613): временно отложить новые измерения и общий Performance Profiler. Сначала точечный рефактор критических модулей по подтверждённым дефектам статического аудита. Профилирование и итоговая приёмка остаются открытыми; не требовать baseline как блокирующую предпосылку рефактора. M613 — [общий пул sampler NPC/Monster](../workflows/M613_ACTOR_SAMPLER_POOL_RU.md). M614: серверный Combat broad phase переведён на NativePartSpatialIndex (GetPartBoundsInBox по существующим RootCollider, без новых Parts/циклов); точные проверки и дальность лучей сохранены. 300 сравнений кандидатов с полным перебором в Lua mock; Studio/DEV и замеры открыты. Следующие потребители — LOD, AI и сокеты. M615: общий ActorAIScheduler для Monster/NPC с очередью deadlines; интервалы 0,1 с, Aggro 0,3 с и существующие боевые события сохранены. Experimental Navigation, Rescue Routes, BlockedWait и все таймеры не изменены. M616: локальный PlayerSpatialIndex (XZ, ячейка 32 studs, один ленивый снимок на пакет scheduler; порядок GetPlayers и точные policy сохранены). 1200 сравнений с полным обходом в Lua-модели; NPC остаются retaliation-only. AI LOD и ComputeAsync budget — следующие этапы; Studio/DEV и замеры открыты.

**P0 всего проекта (решение владельца 27.11.2026):** закрыть все пять карточек с фактической приёмкой до новых механик и расширения контента. P1 у KBN-0039 обозначает только порядок внутри обязательного цикла. Исключение — блокирующие дефекты и работы для приёмки. Старые карточки не отменяются. При продолжении работы начать с первой незакрытой задачи по зависимостям; CODE_COMPLETE не равен DONE. [Основное ТЗ](../spec/CURRENT_PROJECT_SPEC_RU.md#текущий-приоритет--performance-p0), [архитектура](../architecture/CURRENT_ARCHITECTURE_RU.md#текущий-приоритет--performance-p0). Все замечания статического ревью распределены по пяти карточкам; реальные показатели нагрузки пока не измерены. Исключение владельца: KBN-0037-T02 (M607, RigidConstraint) первым, затем profiler → spatial index → client → server → asset pipeline. Первый этап IN_PROGRESS и закреплён; KBN-0037 IN_PROGRESS (M607 и M608 отклонены; M609 функционально принят владельцем в Runtime и на телефоне, T02 выполнен; A02/T06 ожидают полную регрессию и замеры. Profiler KBN-0035 временно отложен по решению M613), KBN-0036 и KBN-0038 IN_PROGRESS с M614, KBN-0039 PROPOSED. Не считать номера карточек номерами патчей.

M610: KBN-0035 IN_PROGRESS, первый сценарий Network Motion реализован; запись Studio/DEV и остальные счётчики открыты. [Workflow](../workflows/M610_NETWORK_MOTION_RU.md).

M611: данные M610 зафиксированы в KBN-0035; автоматическая запись третьей точки, сравнение ещё открыто. [Workflow](../workflows/M611_NETWORK_MOTION_OWNER_RU.md).

| Карточка | Приоритет | Следующая работа |
| --- | --- | --- |
| [★ KBN-0035 · Performance Profiler](specs/KBN-0035.md) | P0 | Диагностика, воспроизводимый baseline |
| [KBN-0036 · Spatial Index](specs/KBN-0036.md) | P0 | Общая инфраструктура локальных запросов |
| [KBN-0037 · Client Performance](specs/KBN-0037.md) | P0 | Sampler, LOD, сокеты, Overhead UI; крепления T02 выполнены, A/B открыт |
| [KBN-0038 · Server Performance](specs/KBN-0038.md) | P0 | Combat broad phase, AI LOD, бюджет навигации |
| [KBN-0039 · Asset Pipeline](specs/KBN-0039.md) | P1 | Hitbox precompute, прогрев клипов и внешности |

Замеры переиспользуются в [KBN-0003](specs/KBN-0003.md) и [KBN-0010](specs/KBN-0010.md); текущие контракты World Streaming / Runtime Build и Monster Navigation сохраняются. Все прежние статусы и проверки неизменны.

## Предыдущий фокус · 27.11.2026 · M570 / M571 docs

| Карточка | Статус | Следующая проверка / задача |
| --- | --- | --- |
| [KBN-0034 · Character Roster](specs/KBN-0034.md) | IN_PROGRESS | M596: миграция, создание и удаление; Studio/DEV PC/Mobile и DataStore-приёмка открыты |
| [KBN-0032 · Monster Navigation & Rescue Routes](specs/KBN-0032.md) | IN_PROGRESS | M593: 20/4, переходы, Blocked Pursuit, Runtime opt-in; Studio/Runtime A/B и нагрузочная приёмка открыты |
| [KBN-0033 · Monster Spawn Authoring & Database](specs/KBN-0033.md) | IN_PROGRESS | Сквозная Studio/Database-приёмка, конфликт ревизии и runtime |
| [KBN-0025 · Combat Analytics](specs/KBN-0025.md) | CODE_COMPLETE | Guided: 41 бой, реальные male clips, headshot и полный отчёт; без XP/Gold |
| [KBN-0026 · Effects & Status System](specs/KBN-0026.md) | IN_PROGRESS | Общие эффекты, HUD, наблюдатели, серверные ограничения, правила повторного наложения |
| [KBN-0027 · Character Skills](specs/KBN-0027.md) | PROPOSED | Навыки без классов и правила оружия/грейда |
| [KBN-0028 · Monster Archetypes](specs/KBN-0028.md) | PROPOSED | Реальные роли, привязка моделей, боссы |
| [KBN-0029 · Progression & Economy](specs/KBN-0029.md) | PROPOSED | Замер XP/Gold, стоимость грейдов, лут/крафт и сохранение |
| [KBN-0030 · Test Suite Cleanup](specs/KBN-0030.md) | PROPOSED | Полный исторический прогон, устранение старых предупреждений/ошибок |
| [★ KBN-0031 · Design](specs/KBN-0031.md) | IN_PROGRESS | Шесть зон, 30 целей, бестиарий, хоррор второй зоны, 9–12 ч как цель; пройти серый прототип |

[M541 · Hub & World Progression](../workflows/M541_HUB_WORLD_PROGRESSION_RU.md) — код тестовой прокачки, ×3 только Hub, Start in Hub, расстановка. Это не завершение KBN-0029 или Design. M571: обновлены KBN-0026/0029/0031, добавлены KBN-0032/0033; SHA, ревизии и история синхронизированы. Новых PASS нет. [Текущий workflow M570](../workflows/M570_GAMEPLAY_INFRASTRUCTURE_RU.md).

## Новый фокус · 25.11.2026 · Balance (история)

[План баланса и прогрессии](BALANCE_PLAN_RU.md): KBN-0018–0024, новая ветка PROPOSED; начать с инвентаризации актуального боя. Старые 17 карточек и их приёмка остаются без изменения.

## Историческая сверка · 22.11.2026

Подробная сверка всех 17 карточек и их открытых проверок: **[M439 · Статус и ревизия](STATUS_2026-11-22_M439.md)**.

1. `KBN-0017` / `KBN-0007`: отдельный **Runtime Draft** и клиентский World Streaming реализованы в коде, а не являются только планом. Есть Studio Live Preview индивидуальных LOD-дистанций (M426–M429); `publishAllowed=false`, нет подтверждённого полевого теста с двумя клиентами.
2. `KBN-0014`, `KBN-0015`, `KBN-0016`: части Collision Blueprint, Instance Manager и LOD1 опубликованы/реализованы, но без завершённой Studio/Android-приёмки.
3. `KBN-0013` и `KBN-0005` остаются ON_HOLD по собственным задачам; при этом текущие House взаимодействия эволюционировали, включая M438a Fireplace.
4. `KBN-0003`/`KBN-0010`: нужны реальные Android baseline/последующие сравнения. Не переносить статические тесты на метрики FPS.
5. M439 восстанавливает целостность всех карточек; до исправления три SHA-соответствия были нарушены. Статусы и PASS не выставлялись автоматически.

**Важно:** исторические части отдельных спецификаций содержат замороженные планы прежних milestone. Первая секция «Текущая сверка» каждой карточки имеет приоритет при чтении, пока изменения не подтверждены пользовательской приёмкой.

## Сохранность документов

Старые версии переработанных спецификаций сохранены в `docs/history/kanban_previous_contracts/`. Актуальны только `docs/kanban/specs` и карточки. Архив не использовать как инструкцию к исполнению.

## Правила статусов

Реализовано в коде ≠ проверено в Roblox Studio/на телефоне. В карточках сохраняются `NOT_RUN` без выдуманных PASS. Если локальная база и Git отличаются, приоритет у фактического состояния проекта и подтверждённых оператором проверок. При изменении спецификации обновлять `specSha256`, ревизию карточки и историю принятого решения.

## M531 · следующий цикл

KBN-0025–0030: Combat Analytics, Effects & Status System, Character Skills, Monster Archetypes, Progression & Economy, Test Suite Cleanup. KBN-0025 — код готов, Studio-приёмка открыта; KBN-0026 — начат с процедурных кастов/VFX.

## M537 · Design и Favorites

[Design · KBN-0031](specs/KBN-0031.md) — закреплённая карточка продуктового плана: маршрут 1–30, Any, локации и цели каждого уровня, навыки без классов. Звезда в заголовке любой карточки переключает `favorite` (boolean, отсутствует = false); сохранение через revision/backup/history. Закреплённые показываются первыми среди результатов фильтра, затем ID; экспорт также учитывает закрепление.
