# M93 — Monster Population / Spawn Slots / Respawn Scheduler

> **Исторический документ.** Фиксирует состояние на момент указанного этапа; отдельные механизмы могли быть заменены. Действующие контракты: [актуальное ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).


**Основание:** M92 после M91 и хотфикса `game1_hf_m91_headshot_character_no_sink.patch`. Исходная диагностическая база — `game1_diag_2026-10-15_12-57-22.zip`. Никакие файлы боевой системы и экипировки на данном этапе не меняются.

## Цель

Продолжение архитектурного разделения M90 → M91 → M92: вынести из `MonsterSpawnerService` учёт живых экземпляров и слотов `maxAlive`, фильтрацию записей текущей Place и постановку отложенных респавнов. Не менять поведение монстров, тайминги или порядок операций.

## Контракт модулей

| Модуль | Отвечает | Не отвечает |
| --- | --- | --- |
| `MonsterPopulationController` (новый) | Фильтрация `MonsterSpawnRegistry.records`, `placeId`/`enabled`, создание `state`, `state.instances`, `state.fill`, `maxAlive`, `respawnSeconds` и отложенный `task.delay` | Построение рига, Animator, уничтожение моделей, AI, физика, выбор точки на карте |
| `MonsterSpawnerService` | Создание монстра, привязка анимаций и событий, очистка при удалении, запуск `PreAnimation`; вызывает `population:RegisterInstance`, `UnregisterInstance` и `ScheduleRespawn` | Выбор лимита популяции, счёт занятых слотов, планирование задержки, перечисление spawn-записей |
| `MonsterDeathLifecycle` | `Dying`, удержание последней позы и вызов DeathIdle; в конце — `releaseInstance(state, model, true)` | Создание нового экземпляра или запуск таймера респавна |
| `MonsterWanderController` / `MonsterIdlePresentation` | Блуждание, locomotion, idle/combat presentation | Лимит популяции и учёт слотов |

Нет циклических `require`: `MonsterSpawnerService` внедряет в `MonsterPopulationController.new(spawnOne)` callback создания экземпляра, а контроллер не импортирует Spawner. `States()` возвращает тот же внутренний словарь для `PreAnimation` и проверки актуальности `state.instances[model]`.

## Сохранённая семантика (важно для регрессии)

1. **Начальный спавн:** `Start` сначала подписывается на `RunService.PreAnimation`, затем последовательно обходит `SpawnRegistry.records`, пропуская записи с `enabled == false` и записи чужого Place, создаёт state и вызывает первичное заполнение до увеличения счётчика. Строковый ключ `spawnId or count + 1` сохранён.
2. **Слоты:** целевой лимит `math.max(1, math.floor(finite(record.maxAlive, 1)))` неизменён; учитываются `model.Parent`, а не `Health > 0`. Монстр с `LifeState = Dying` и `DeathIdle` занимает слот, пока его тело реально не освобождено.
3. **Удаление:** сначала `state.instances[model] = nil` (через `UnregisterInstance`), затем `DeathLifecycleService.Cancel`, `wanderController:Dispose`, отключение `entry.connections`, остановка треков, отсоединение хитбоксов и уничтожение модели. Порядок важен для подавления повторного `Destroying`.
4. **Респавн:** только при штатном завершении `DeathLifecycleService.BeginDeathIdle` вызывается `releaseInstance(..., true)`, и **только после очистки** планируется `task.delay(max(0, finite(respawnSeconds, 10)))`. По истечении задержки проверяется `state.enabled`, затем вызывается `state.fill()`, где повторно проверяется лимит. Если модель извне удалена с `Destroying`, вызывается `releaseInstance(..., false, true)` — нового респавна не планируется.
5. **Без изменений RNG:** новый контроллер не создаёт `Random.new()` и не вызывает `NextInteger` / `NextNumber`. Один и тот же `spawnRandom` обслуживает идентификаторы, геометрию, yaw, Wander и Idle. Нет новых Heartbeat/таймерных циклов или попыток повторного spawn при ошибке создания.
6. **API/совместимость:** не меняются Lua API Spawner (`Start`), порядок построения Visual/NavRig, MonsterAIService, боевые hitboxes, Character death/headshot, Asset IDs, реестры, Studio Bridge, Host Agent, Asset Manager или SQLite. Миграции не нужны.

## Проверки

```
python .\system\verify\verify.py
python -W error::ResourceWarning -m unittest discover -s .\system\verify -p 'test_*.py' -q
```

Добавлен `test_monster_population_m93.py` с шестью контрактами: независимость модуля и DI; Place-фильтр и последовательность Start; `maxAlive` и занятость слота трупом; порядок очистки и внешнее `Destroying`; поздний респавн; сохранение RNG и порядка построения экземпляра. Обновлены структурные ожидания M91/M92 и `verify.py` (только новая граница ответственности).

**Ограничение:** Python-тесты проверяют текстовые контракты Luau. Они не запускают Roblox Studio, Animator или tween-погружение. Ручной Play необходим.

## Ручная проверка Roblox Studio

1. `maxAlive = 1`: один монстр, убийство → полная анимация death → DeathIdle/sink → задержка `respawnSeconds` → один новый монстр. Во время смерти второго экземпляра быть не должно.
2. `maxAlive > 1`: изначально заданное количество, затем убить двух подряд; количество не превышает лимит ни при одном респавне.
3. Разные spawnId: монстры респавнятся в своих точках; записи другой Place и выключенные записи не активируются.
4. Внешнее удаление runtime-модели в Explorer: очистка без внеочередного респавна и без ошибок в Output.
5. Повторить несколько циклов: idle_special, wander → chase → attack → return, death, hold последней позы, sink и respawn. Убедиться, что подписки не накапливаются, а Character death/headshot не изменились.

## Установка и откат

Применить M93 **после M92**, остановив Play и затем синхронизировав Rojo. `git apply --check`, `git apply`, `verify.py` и `unittest`. Host Agent / Docker не перезапускаются. Откат: остановить Play, `git apply -R --check <M93.patch>`, `git apply -R <M93.patch>`, затем Play.

## Дальше

После проверки M93 в Studio можно рассмотреть дополнительное уменьшение размера Spawner — отделить связывание runtime-подписок (`MonsterRuntimeBindings`), не трогая MonsterAI, death/respawn timing и правила игрового боя.
