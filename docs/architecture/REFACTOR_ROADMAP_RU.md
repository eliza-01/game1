# game1 — незавершённый рефакторинг и план следующих этапов

**Обновлено:** 30.10.2026 · **База:** диагностический дамп `13-52-46` (M162).
**Характер документа:** план технического долга, не распоряжение на немедленное переписывание. Изменения выполняются только отдельными проверяемыми патчами.

## 1. Что завершено / что осталось

| Область | Статус | Обоснование / следующая граница |
| --- | --- | --- |
| M83 — правила, исходный аудит, безопасность static path | **Completed в исходниках** | `AGENTS.md`, static resolver и regression tests присутствуют |
| M85 — server bootstrap, HTTP read | **Completed (этап)** | `ServiceBootstrap`/`ServiceCatalog`, отдельные API reads; нет обязательств «весь bootstrap когда-либо» |
| M88–M89 — HTTP write / Host Agent composition | **Completed (этап)** | HTTP dispatch/services вынесены, root `host_agent.py` ~254 строки; wiring остаётся |
| M90–M93 — Monster Spawn/Population/Wander/Death | **Completed (этап)** | узкие runtime helpers, spawner ~304 строки |
| M94 — NPC locomotion recovery | **Completed (этап)** | существующие runtime и regression contracts; Studio behaviour — отдельно |
| M96 — AnimationSpeedScaling | **Completed (этап)** | pure scaling и override contracts; не означает полной декомпозиции animation stores |
| M97–M99 — Combat/session/hitbox | **Completed (этап), долг остаётся** | attack service и hitbox service теперь координаторы, есть session/spatial helpers |
| M100–M101 — Studio Bridge / Timeline | **Completed (этап)** | Game1Bridge thin coordinator и десятки модулей Studio; функциональная регрессия нужна при каждой правке |
| M102–M105 — Monster AI/attack/chase/lifecycle | **Completed (этап)** | MonsterAI small coordinator, отдельные lifecycle/attack/navigation |
| Актуальные registry / Real Estate / House Sockets до M162 | **Feature development, не весь рефакторинг** | новые границы существуют, но монолитные stores/debug и legacy contracts не устранены |
| Инвентаризация всех API и ownership state | **Partial / Pending** | исходный M83 audit устарел; нужна текущая карта по подсистемам |
| Сквозная проверка Studio Play/сетевых условий | **Pending для нового roadmap** | Python/Luau static regression не подтверждает Studio physics и client-server UX |

*«Completed (этап)» означает, что выделение модулей в данном milestone существует, а не что система завершена навсегда. Старые документы M85–M105 лежат в `docs/history/refactor-m85-m105`.*

## 2. Приоритеты следующего цикла

### R1 — защита границ и формальная спецификация (P1, без изменения gameplay)

**Задачи:** закрепить архитектурные инварианты, перечислить owner state/Remote schemas/cross-domain dependencies, обновлять проверяемую таблицу известных рисков. Зафиксировать тестовые сценарии существующих Character, NPC, Monster, House, Atlas flows.

**Приёмка:** `AGENTS.md`, current spec и service map согласованы; перечислены критичные и Studio-only флоу; базовые `verify.py`/`unittest` проходят; нет изменений ассетов и сериализованной БД.

### R2 — modular verify, сохранить единую CLI (P1)

**Состояние на M171:** `system/verify/verify.py` сокращён с **2986 до 187 строк**. M164 вынес M52/M53 source-only, M165 — project identity/Rojo/runtime inventory; M166 добавил три валидатора: `monsters.py` (Monster registry, animation, spawn), `actor_runtime.py` (M23/M25/M26 Monster AI, pursuit, lifecycle/Options) и `combat_contact.py` (M27–M33 weapon contact, hitboxes и headshot ray). M167 вынес Character manifest/rig/publication/identity/stats, Character Animation/Scaling/manual reimport и Weapon registration/attack movement в `characters.py`, `animations.py`, `weapons.py`. M168 дополнительно выделил `studio_debug.py` (Test Loadout / Movement Debug), `death_runtime.py` (terminal death pose / hit effects), `attack_timelines.py` (m35/m38 Timeline authoring / HitStart–HitEnd) и `authoring_tooling.py` (Rojo Workspace isolation / Animation Speed UI). M169 добавил семь разделённых валидаторов: `location_authoring.py` (M41/M42), `location_assets.py` (M43 registry/DecoManager), `deco_studio.py` (M45 Studio save), `location_asset_variants.py` (M44/M46–M49), `environment_bounce.py` (M50 collision/bounce), `location_texture_sync.py` (M51 Image ID/refresh) и `location_asset_categories.py` (M54/M55/M128). Данные междоменных проверок передаются неизменяемым `LocationAssetSources` вместо глобальных переменных. M170 вынес четыре финальных блока: `combat_foundation.py` (урон, серверный Attack и конфигурация Timeline), `hitbox_runtime.py` (M99 hitbox и head resolver), `studio_character_bridge.py` (Studio import, canonical authored basis, sync) и `registered_attack_clips.py` (соответствие зарегистрированных атак runtime Timeline). В фасаде сохранены места вызовов и историческая граница проверки ошибок. **R2 завершён после M171:** все категории проверяются до единственного `if errors`, CLI возвращает код `1` при нарушениях M54/M55/M128; исправлена устаревшая проверка HTML-примера описания Location Asset без изменения интерфейса.

**Целевые компоненты:** фасад `verify.py` + независимые domain validators (character, npc/monster, world/estate, manifests/atlas, tools/bridge), явная схема ошибок без побочных эффектов.

**Приёмка:** та же точка запуска и не менее строгий набор проверок; compare before/after на snapshot; нет automatic writes/migrations. Выносить независимые доменные группы в один патч допустимо только при строгой проверке каждого и неизменной очередности сообщений. Для M164 проверены совпадение вывода `verify.py` до/после, отдельные тесты source-only и общий набор; для M165 — тот же вывод, сценарии неправильных namespace/ports/legacy paths/runtime inventory; для M166 — тот же вывод, 9 дополнительных тестов Monster/Actor/Combat, включая негативные проверки и контроль отсутствия записей; для M167 — тот же вывод, 10 дополнительных тестов Character/Animation/Weapon с негативными сценариями и проверкой read-only; для M168 — 12 тестов Studio/Death/Timeline/Authoring, сравнение stdout/exit code до/после и проверка исправления ошибок без записи в файлы; для M169 — 13 тестов Location/Deco/Environment, проверка исходного stdout и негативных сценариев без записи в файлы; для M170 — 13 тестов Combat/Hitbox/Studio/registered clips, контроль read-only и сравнение stdout/exit code до/после. **M171 (Completed):** выполнен перенос M54/M55/M128 перед единственным завершением CLI, добавлены end-to-end тесты ошибок M54/M55/M128, порядка диагностики и кода завершения. Исправлен устаревший HTML contract для `description` (проверяется фактическое поле и подсказка вместо устаревшего примера); данные и UI не менялись. Размер фасада ~187 строк соответствует цели R2. **Следующая область — R3 (Control Center / Asset Manager).**

### R3 — boundaries Control Center / Asset Manager (P1/P2; Next)

**Состояние:** `monster_animation_store.py` 946; `character_store.py` 806; `real_estate/store.py` 822; `location_asset_store.py` 691; `weapon_store.py` 647. `host_agent.py` уже вынесен, повторно не расщеплять без цели.

**Цель:** сохранение identity, SQL/migrations, dependency resolution, authoring validation, publication orchestration и export registry живут в явных модулях с контрактами. Общий `Atlas Registry` — единственный ID публикации варианта; consumers и legacy `texture_reference_slug` читают через адаптер без копии ID.

**Первым** логично провести чтение/разрешение shared atlas и статус Studio Sync (M162), затем отделять write paths и publication jobs. **Приёмка:** на копии реальной DB те же slugs/IDs, `PUBLISHED/UPDATE_AVAILABLE`, отсутствие дублирующего upload; old API contracts сохраняются; no schema rewrite without migration+rollback.

### R4 — общие UI-примитивы и controllers (P2)

**Состояние:** `TestLoadoutController.luau` ~987, `MovementDebugController.luau` ~1009. В `HouseSocketDebugController` отдельно от UI должна остаться только Studio-only debug state/config.

**Цель:** повторно используемые UI primitives (action row, toggle, input key badge, scroll list, range control) и самостоятельные feature controllers. Не смешивать настройку UI и серверные права действия.

**Приёмка:** визуальное и keyboard поведение прежние; `E/F` на замке/двери не перехватываются лишним debug UI; размер панели, KEY OWN/LOST, USE/AIM и refresh переживают реальные Play scenarios.

### R5 — house runtime separation (P2)

**Цель:** вытянуть socket discovery/eligibility/client AIM/door lock/elevator move/effects в узкие слои. Не возвращать восстановление Bone в Studio и не дублировать серверную авторизацию на клиенте.

**Приёмка:** обе стороны двери, состояния lock, независимый chest/elevator USE/AIM, occlusion, этажные spawn, отсутствие query collisions с headshot, cleanup на destroy; non-Studio не принимает debug mutation.

### R6 — общие Actor contracts и animation lifecycle (P2/P3)

**Состояние:** NPC использует `MonsterStore(kind="npc")` и `monsterSlug` в некоторых маршрутах. Это совместимый текущий факт, но не долговременная предметная модель.

**Цель:** внутренний `ActorDefinition/Spawn` контракт с adapters Monster/NPC; отдельный versioned migration публичных payload когда это понадобится; animation ownership and cleanup при смерти, повторном spawn, смене экипировки.

**Приёмка:** те же регистрации, UUID/slug/asset IDs, type-specific AI policies, детерминированные изменения Remotes; сохранено боевое поведение персонажей/NPC/Monster, нет hidden fallback по имени.

## 3. Порядок работы

1. **Сначала R1**, затем R2 и R3 по маленьким внутренним модулям; UI/House и Actor — независимые следующие дорожки после защитных тестов.
2. Для каждого PR/патча отделять **behavior-preserving extraction** от product feature change.
3. Снимать baseline списка API/attributes, manifests/DB hashes и конкретные tests; после — сравнивать.
4. Запускать Python, verify, Luau, JS/Blender по необходимости; отдельно Studio Edit/Play для фактического поведения. Отсутствие Studio Play — открытая проверка, не `PASS`.
5. Ни один этап не должен менять публичные IDs/открытые данные просто потому, что это архитектурно удобнее.

## 4. Не цели

Нет задачи «сделать каждый файл меньше X строк», переписать завершённые M85–M105, автоматически переименовать все RPC или реорганизовать SQLite без пользовательской необходимости. Не вводить новые абстракции, если нет двух реальных consumers и понятного контракта.
