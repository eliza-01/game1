# Архитектурный аудит game1 — 14 октября 2026

## Область проверки и достоверность

Основа — `game1_diag_2026-10-14_08-24-49.zip`, исходники **после M81**. Проверены исходники Rojo, Control Center/Host Agent, Asset Manager, Studio Bridge, миграции и тесты. Дамп не содержит исполняемое содержимое `place/game1.rbxl`, реальных FBX/RBXM, несинхронизированных Studio-скриптов и всех внешних установленных плагинов. Поэтому это аудит **доступного исходного проекта**, а не формальное подтверждение каждого объекта в текущем DataModel запущенной Studio.

### Срез исходников

Полный машинный перечень проверенных файлов с размерами, слоями и индикаторами зависимостей — `docs/ARCHITECTURE_SOURCE_INVENTORY_2026-10-14.csv`. Метрики не являются заменой анализа поведения.

- `src/shared`: 35 Luau-файлов, ~1 941 строк; `src/server`: 39, ~8 111 строк; `src/client`: 35, ~7 413 строк.
- `system/control-center`: 48 файлов Python/JS/HTML/CSS/SQL, ~11 702 строки; `system/studio-plugin`: 11 Luau-файлов, ~3 697 строк.
- `system/verify`: 16 Python-файлов, ~4 366 строк; `verify.py` в одиночку ~2 832 строки.
- `verify.py` проходит; все **74** текущих `unittest` проходят локально. Это сильный базовый набор, но многие регрессионные тесты проверяют строки исходников, а не Roblox API / сервер-клиентное поведение.

## Подтверждённые хорошие решения

1. Rojo явно разделяет `Game1Shared`, `Game1Server` и `Game1Client` (`default.project.json`); сцена не переписывается синхронизатором.
2. Есть повторно используемые actor-модули (`ActorChaseNavigator`, `ActorFacingTracker`, `ActorAttackPursuit`, `ActorCollisionPolicy`, `ActorCombatTargeting`) и отдельные адаптеры NPC/Monster.
3. У NPC разделены риг, экипировка, анимации, AI, популяция/респавн; есть общие `DamageService`, `DeathLifecycleService`, `EntityHitboxService`.
4. Боевая логика Character валидирует атакующие данные на сервере; отладочные mutating-сервисы проверяют `RunService:IsStudio()`.
5. SQLite-хранилища используют закрывающий соединение контекстный менеджер; миграции/регрессионные тесты уже учитывают жизненный цикл анимационных регистраций.
6. Источники/публикации и исходные материалы разделены; на публикацию ассетов есть версии и реестры.

## Выявленные проблемы и риски, по приоритету

| Приоритет | Где | Подтверждённая проблема | Рекомендуемая граница |
| --- | --- | --- | --- |
| P1 | `system/control-center/host_agent.py` (~1 237 строк) | HTTP Handler обслуживает чтение, модификацию, публикацию, запуск Studio Bridge и миграции для многих доменов. Магистраль транспорта и orchestration связаны. | Тонкий HTTP adapter + `api/routes/{characters,animations,weapons,actors,world,debug}` + application use cases; injectable repositories/bridge; единая сериализация ошибок и версионирование. |
| P1 | `src/server/monster/MonsterSpawnerService.luau` (~1 082) | Совмещает population, визуальный риг, анимации, wander/navigation, смерть, пол, таймеры и respawn. NPC уже разделён лучше. | `MonsterRigFactory`, `MonsterPopulation`, `MonsterAnimationPresentation`, `MonsterWander`, `MonsterDeathLifecycle` с тонким spawner; общие части переиспользовать через actor APIs, сохраняя monster policy. |
| P1 | `src/server/init.server.luau` | Жёсткая последовательность `Start()` без изоляции ошибок. Ошибка NPC ранее останавливала запуск debug remote и других поздних сервисов (наблюдалось в M79). | Явный Service Bootstrap с зависимостями, health state и fail-fast для критичных сервисов / изоляцией для необязательных; не просто `pcall` всего подряд. |
| P1 | `system/studio-plugin/Game1Bridge.server.luau` (~1 868) | Монолит coordinator + Studio HTTP bridge + модель/оружие/Timeline/UI; отдельно собранный `Game1Bridge.rbxmx` расходится с исходником (старая кнопка Control Center). | Разделить `BridgeTransport`, `ModelImportCommands`, `RigValidation`, `TimelineEditor`, `PluginUI`; единственный source-of-truth сборки. Кнопка убрана из исходника данным M83, legacy `checkAgent` оставлен по просьбе. |
| P1 | `system/control-center/web_server.py` | Файловый путь статического сервера строится прямым `STATIC / relative` без явного контроля принадлежности пути статической папке; потенциальный path traversal. Хотя порт Docker привязан к loopback, проверка пути обязательна. | Чистый `StaticFileResolver` с нормализацией/allowlist и тестами — **реализовано в M83**; полноценные HTTP-contract тесты остаются следующим этапом. |
| P2 | `src/server/combat/EntityHitboxService.luau` (~957) и `AttackService.luau` (~605) | Границы геометрии, кэша, query и намерений атак тесно связаны; сложно изолировать предрасчёт, server validation и damage resolution. | `HitboxGeometryCache`, `SpatialQuery`, `WeaponSweepValidator`, `AttackSession`; authority остаётся на сервере. |
| P2 | `src/server/monster/MonsterAIService.luau` (~619) | Цикл AI, навигация, презентация анимаций и выбор атаки смешаны. Часть уже вынесена в actor, но остаются локальные реализации. | Behaviour FSM + reusable targeting/navigation + monster-specific policy; отдельная animation presentation. |
| P2 | `src/shared/animation/AnimationSpeedScaling.luau` | Общий расчёт и доступ к `Workspace`/Studio debug-атрибутам смешаны в одном модуле. | Чистая `ScalingFormula` / `ScalingPolicyResolver` + runtime `ScalingOverrideProvider` вне математического ядра; единая схема Character/NPC/Monster. |
| P2 | `system/control-center/static/*.js` | Например, `npc-assets.js` 33 КБ / 161 физическая строка, другие JS почти в одну строку. Связь DOM, сетевых вызовов, модельного состояния и валидации затрудняет модульное тестирование. | API client, state store, view components, form validation и event binding отдельно; code formatting/lint. |
| P2 | `system/verify/verify.py` (~2 832) | Центральный проверяющий скрипт сам стал монолитом. Значительная часть остальных тестов — исходниковые assertions. | `verify/architecture`, `verify/registries`, `verify/publication`, `verify/runtime_contracts`; unit/state-transition/HTTP tests отдельно, Studio smoke suite отдельно. |
| P2 | Контракты NPC/Monster в `monster_*_store.py`, spawn payload `monsterSlug` для NPC | Реальное переиспользование есть, но общие модели данных названы по монстрам; NPC-контракты протекают через monster-термины. | Общие `ActorDefinitionStore`, `AnimationProfileStore`, `SpawnRecord` + явные Monster/NPC адаптеры; миграция только после версии схемы и тестов на сохранность ID. |
| P3 | Единый lifecycle/cleanup | Многие подписки управляются конкретными сервисами, но общего контракта `Start/Stop/Destroy` и управления задачами нет; усиливается риск при динамическом respawn. | Контракт owned connections/tasks; `Maid/Janitor` или локальные scope owners, без глобального механического внедрения. |

## Предлагаемая целевая архитектура

```text
Authoring: Asset Manager UI → API transport → Application Use Cases → Repositories / Studio Bridge
                                                 ↓
                                         versioned manifests
                                                 ↓
Runtime Shared: Contracts / Policies / Pure Math / Registries
                  ↙                               ↘
Server: Actor lifecycle / Combat authority / AI / Navigation / Spawning
Client: Input / Animation presentation / Visual effects / Debug UI
```

Запрещённые зависимости: Shared → Server/Client; Client → приватные server-модули; gameplay → Studio/plugin HTTP; сущность NPC → конкретный player/NPC slug. Контроль состояния — через явные контракты вместо «кто последний выставил атрибут».

## Порядок выполнения рефакторинга (без массового переписывания)

1. **M83 — аудит и правила, минимальная синхронизация плагина и защита статических файлов.** Добавить `AGENTS.md`, этот отчёт и архитектурные smoke/guardrail тесты; согласовать установленный Game1Bridge с исходниками. Без изменения gameplay. Готово в текущем патче.
2. **Следующий этап: contract/bootstrap.** Вынести реестр старта сервисов, разграничить critical/optional. Добавить HTTP/Studio Bridge contract tests и статус инициализации. Должны сохраниться все существующие Remote names и API endpoints. Test: намеренный отказ в NPC не блокирует *необязательные* debug сервисы (и обратно), critical failure видимая и управляемая.
3. **Следующий этап: Host Agent и UI.** Вынести transport/routing с отдельными маршрутизаторами, внедрить зависимости, изолировать Studio commands. Тестировать HTTP GET/POST/DELETE на копии базы и все ошибочные ответы. Статическая выдача от обхода директорий закрыта в M83; добавить HTTP-contract тесты для proxy/agent.
4. **Следующий этап: Monster lifecycle.** Постепенно извлечь визуал/анимацию/wander/respawn из `MonsterSpawnerService`. Сравнивать runtime snapshots по анимациям, смерти, бою, популяции, путям и сетевой плавности NPC/Monster.
5. **Следующий этап: Battle / Animation.** Разделить хранилище hitbox, валидацию атаки, timing и presentation; добавить тесты на повторный Hit, lag/speed scaling и смену состояний. Не менять достигнутую механику боёв и анимаций ради косметического кода.
6. **Постоянно:** CI с Python, JS, Luau type/lint + отдельные Studio Play tests (десятки AI сущностей, respawn, failover, сеть). Регрессионные тесты на состояние и взаимодействия, а не только поиск строк.

## Контроль качества после каждого этапа

- `verify.py` и полная регрессия `unittest` проходят.
- Количество публичных endpoint/remote и их payload-контракты неизменны либо документирована версия/миграция.
- Фактическая настройка Asset Manager, публикации и SQLite данные не меняются незаметно; migration tested on copied DB.
- Нет новых God Modules и циклических зависимостей; новые модули имеют одну ответственность и тестируются изолированно.
- Gameplay фактически проверен в Roblox Studio (особенно attack loops, interpolation, idle special, weapon visibility, collision); результат отмечен отдельно от статических тестов.
- Для каждого этапа зафиксирована точка восстановления/rollback.

## Ограничения текущего результата

M83 **не означает**, что все перечисленные монолиты уже переработаны. Их одномоментная декомпозиция нарушила бы требование о стабильной регрессии. Это реальная карта долгов и технический контракт для поэтапного исправления. Данные аккаунтной Memory из этого проекта автоматически не изменяются.
