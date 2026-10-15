# M92 — Monster Idle / Combat Animation Presentation

**База:** M91 из `game1_diag_2026-10-15_12-57-22.zip` плюс применённый хотфикс `game1_hf_m91_headshot_character_no_sink.patch` (Headshot и отсутствие sink у Character). M92 накладывается поверх уже установленной пользователем версии M91 + hotfix. Предыдущие изменения системы экипировки и FBX не трогаем.

## Суть изменения

`MonsterSpawnerService` больше не реализует `playBaseIdle`, `playCombatIdleState`, выбор `idle_special`, управление скоростью и завершение idle-клипов. Всё это вынесено в `MonsterIdlePresentation.luau`.

| Модуль | Владеет | Не владеет |
| --- | --- | --- |
| `MonsterIdlePresentation` (новый) | `idle` / `combat_idle` / `idle_special`, weighted выбор, `Play` / `Stop` / `AdjustSpeed`, выставление анимационных атрибутов, callbacks `DidLoop` / `Ended` | Создание и удаление монстра, NPC, спавн, самостоятельные соединения с Roblox-сигналами, AI, locomotion, death или respawn |
| `MonsterSpawnerService` | Порядок спавна, экземпляры, общий RNG, `entry.connections`, переключения состояния боя, delegating presentation | Внутренняя реализация выбора/воспроизведения idle |
| `MonsterWanderController` | Продвижение к точке, Walk/Run, текущая логика пауз/торможения | Алгоритм выбора idle_special |
| `MonsterDeathLifecycle` | Dying, terminal pose, handoff в DeathIdle | Idle policy; получает callback `stopIdleState` и `stopTrack` |

Зависимости: `Spawner → IdlePresentation`, `Spawner → Wander/Death` и `Wander/Death → presentation callbacks` (только dependency injection). Циклических `require` и новых фоновых задач нет. Файлы `MonsterWanderController` и `MonsterDeathLifecycle` в M92 **не изменяются**.

## Контракты, сохранённые по отношению к M91

- Используется **тот же объект `spawnRandom`**, передаваемый `MonsterIdlePresentation.new(spawnRandom)`, `MonsterSpawnGeometry` и `MonsterWanderController`. `weightedIdleChoice` вызывается только из прежнего `idleTrack.DidLoop`, без дополнительных вызовов RNG.
- Веса `math.max(1, finite(weight, 100))`, диапазон `NextNumber(0, total)`, fallback в последний вариант и формат `special_%02d` сохранены.
- Для `idle` / `combat_idle` сохранены `fadeTime` 0.12 / 0.1, для special — 0.08, остановка треков — 0.08. Разрешение скорости по `AnimationSpeedScaling.ResolveForAnimation` сохранено; `track:AdjustSpeed` вызывается для уже воспроизводимого клипа.
- Условия, при которых special не запускается (`dying`, `wandering`, `activeIdleSpecial`, `InCombat`, `MonsterCombatActive`), сохранены. Событие `special.Ended` возвращает к base idle только для актуального живого entry и соответствующего active special.
- Ранний приоритет AI/атаки (сигнал `MonsterCombatActive`) остаётся в Spawner. При выходе из боя проверяется `InCombat`, при возвращении из Wander вызывается тот же базовый/combat idle.
- Подписки `DidLoop` / `Ended` создаются из presentation, но **регистрируются только через callback `watch(entry, ...)` Spawner** в `entry.connections`. При release M91 отключает все соединения. Presentation не создает собственных неконтролируемых `:Connect`.
- Порядок после загрузки треков: установка `state.instances` → подписка на idle-треки → первый `playBaseIdle` → запуск Wander → подписка на combat/debug/death/Destroying; это тот же порядок, что и в M91.
- Death/DeathIdle/sink/respawn, hitboxes, атрибуты персонажей, headshot, экипировка, Host Agent и Asset Manager без изменений. Не меняются реестры, миграции, HTTP API и Asset ID.

## Тестирование

```powershell
python .\system\verify\verify.py
python -W error::ResourceWarning -m unittest discover -s .\system\verify -p 'test_*.py' -q
```

Дополнен `test_monster_idle_presentation_m92.py` (5 контрактов: модульность, RNG, скорости/приоритеты, ownership подписок, DI из Wander/Death). Старые структурные проверки M81/M86/M90/M91 перенаправлены на новый модуль, вместо ошибочного требования, чтобы вся реализация осталась в Spawner. **Тесты проверяют структуру текста Luau**, а не запускают Roblox Animator / физику.

## Ручная проверка в Roblox Studio

1. Обычный idle, выход `idle_special`, несколько циклов выбора вариантов с учётом веса и возврат к `idle` после `Ended`.
2. Chase/Attack → combat idle → выход из боя → idle; во время боя special не должен срабатывать.
3. Wander Walk/Run, вмешательство агрессии во время перемещения, возврат к idle; новые рывки/перезапуски анимаций отсутствуют.
4. Применение Debug Animation Speed во время воспроизведения idle / combat idle / special и Walk/Run.
5. Death → hold последнего кадра → sink Monster → respawn. Несколько циклов не должны создавать повторных подписок `DidLoop` / `Ended`.
6. При удалении runtime Monster убедиться, что callbacks не исполняются после освобождения instance; Character death и `Headshot!` остаются как в hotfix.

## Откат и следующий этап

При регрессии остановить Play, выполнить `git apply -R --check <патч>`, затем `git apply -R <патч>` и перезапустить Play после Rojo-синхронизации.

**M93 (после подтверждения M92 в Studio):** вынесение учёта популяции/слотов и планировщика respawn из `MonsterSpawnerService`, не затрагивая death timing и AI. Не объединять с изменениями hitbox/weapon/import.
