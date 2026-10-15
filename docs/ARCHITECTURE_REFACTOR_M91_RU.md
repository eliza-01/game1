# M91 — Monster Wander / Death Lifecycle и владение runtime-подписками

**База:** фактический `game1_diag_2026-10-15_12-57-22.zip` (M90 уже применён, последующие регрессионные/Studio UI фиксы включены в дамп). Продолжение `ARCHITECTURE_REFACTOR_M90_RU.md`. В данном этапе изменены только `src/server/monster`, `system/verify` и эта документация.

## Что выделено

| Модуль | Владеет | Не владеет |
| --- | --- | --- |
| `MonsterSpawnerService` | Популяция, запись spawn, создание экземпляра, слоты `maxAlive`, обратный вызов `state.fill`, период `respawnSeconds`, idle presentation и привязка событий | Алгоритм Wander / RunSpeed, terminal death frame |
| `MonsterWanderController` | Время пауз, выбор цели через `MonsterSpawnGeometry`, `Humanoid:MoveTo`, обновление walk/run при debug-атрибутах, подключение MoveToFinished, остановка/Dispose задачи блуждания | Решение о respawn, собственный генератор RNG, изменение поведения преследования AI |
| `MonsterDeathLifecycle` | Начало Dying, запуск death track, terminal hold в `PreAnimation`, handoff к `DeathLifecycleService.BeginDeathIdle` | Spawn slot, уничтожение модели, срок респавна |
| `DeathLifecycleService` (существующий) | DeathIdle, sink/tween, финальный callback | Monster-specific animation choice, население |

Граф зависимостей: Spawner → Wander/Death; Wander → Geometry + shared CharacterMovementConfig; Death → общие AnimationSpeedScaling / DeathAnimationPolicy + DeathLifecycleService. Wander и Death **не требуют** Spawner; зависимости presentation и release передаются через конструкторы, циклов `require` нет.

## Совместимость и состояние

- Сохранён **тот же `spawnRandom`**, порядок `NextNumber` / `NextInteger`, радиусы, `MoveTo` destination, паузы 0.35–1.35 и 3–10 секунд, refresh 1 секунду и arrival tolerance 1.25 studs.
- Сохранены `walk/run`, их fallback, `RunSpeed`, `MonsterLocomotionMode`, debug animation speed и приоритет AI (`MonsterCombatActive` / `InCombat`). Не менялись `MonsterAIService`, игровая боевая логика или скорость сетевой репликации.
- Сохранены `DeathAnimationPolicy.Start` и latch terminal frame в `RunService.PreAnimation`, поля `LifeState`, `DeathAnimationTerminalTime`, `DeathTerminalPoseHeld`, продолжительность и визуальное утопление тела. Dying/DeathIdle продолжают занимать слот `maxAlive` вплоть до вызова `releaseInstance`.
- Respawn по-прежнему назначает **только Spawner** после callback окончательного освобождения через `state.fill`, с прежним `respawnSeconds`.
- Новый ownership fix: подписки конкретного экземпляра (`AnimationTrack.Ended`, `DidLoop`, игровые атрибуты, `Destroying`) учитываются в `entry.connections` и отключаются при освобождении; wander task и активное `MoveToFinished` отключаются при Dispose. При переключении в бой Wander останавливается **без** отмены циклического задания — после выхода из боя блуждание возобновится.
- В период движения используется generation token, чтобы старый MoveTo не возобновился после переключения в бой/смерти. Это целевое исправление гонки (не изменение настроек locomotion).
- При внешнем `Model:Destroy()` проводится освобождение подписок и кэша хитбокса **без внеочередного respawn**, как и прежде.
- Не добавлены RemoteEvent, HTTP/Studio Bridge endpoints, ограничения Asset ID, миграции SQLite/реестров или новые фоновые циклы. Host Agent, Asset Manager и Studio UI не изменены.

## Применение

Патч `game1_m91_monster_wander_death_lifecycle.patch` применяется к корню `game1` на состоянии дампа от 15.10.2026 12:57. Перед применением выполнить `git apply --check`. Следом — `verify.py`, все Python unittest, затем синхронизация текущим Rojo и **перезапуск Play**. Для этого этапа Host Agent/Docker/Control Center/SQLite перезапускать не требуется.

**Откат:** если Studio Play выявит регрессию, остановить Play, выполнить `git apply -R` для того же патча после `--reverse --check`, затем вернуть синхронизацию Rojo/Play. Откат не затрагивает сохранённые данные.

## Контрактные и регрессионные проверки

Команды из корня проекта:

```
python system/verify/verify.py
python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q
```

`test_monster_lifecycle_m91.py` защищает структуру ownership, переходы death → hold → sink → respawn, контракт общего RNG, обслуживание debug-параметров, уникальность wander task и отключение соединений. Эти Python-проверки **структурные** и не являются запуском Luau внутри Roblox.

## Обязательная ручная проверка Studio Play

1. С одним опубликованным размещением Monster проверить idle, idle_special, случайные паузы/блуждание внутри радиуса и отсутствие ухода за границы.
2. Во время Wander переключить `MonsterLocomotionMode`, изменить `RunSpeed`; убедиться, что переключаются walk/run, затем AI Chase/Attack и возврат к обычному idle/wander.
3. Во время движения переключиться в бой несколько раз; исключить краткий рывок к старому wander waypoint после возврата.
4. Нанести смертельный урон: death один раз, видимая поза последнего кадра, DeathIdle, sink тела; **замена появляется после** освобождения слота и `respawnSeconds`.
5. Повторить несколько циклов respawn; убедиться, что анимационные подписки не дублируются (один special, одно начало death), `maxAlive` соблюдается.
6. Удалить вручную одну runtime-модель в Studio, пока она блуждает: не должно оставаться активного `MoveToFinished` или ошибок в Output. Внешнее удаление **не создаёт** внеочередной respawn.
7. Проверить Play и Run, обычный сервер и локальный Studio debug; побочные M90 хотфиксы оружия/UI не изменены.

**Ограничение:** в контейнере не запускались Roblox Studio physics, Animator или DeathLifecycle tween. До прохождения этих проверок поведение на живых монстрах следует считать неподтверждённым.

## Дальнейшие этапы

После ручного подтверждения M91: выделение idle/combat animation presentation из Spawner, затем отдельная популяция / state registry. Не объединять это с изменениями Attack AI, weapon hitbox и импорта моделей.
