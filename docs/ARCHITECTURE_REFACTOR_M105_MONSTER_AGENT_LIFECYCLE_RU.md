# M105 — жизненный цикл агентов Monster AI

**База:** архив `game1_diag_2026-10-16_13-23-03.zip` + M102 → M103 → M104. Патч накладывается непосредственно после M104.

## Ответственность

| Модуль | Владелец обязанностей |
| --- | --- |
| `MonsterAIService` | AI-цикл 0.10 c, поиск цели 0.30 c, переходы Aggro/Chase/Attack и делегирование существующих движения/атак |
| `MonsterAgentLifecycle` | Подписка на папки `Workspace.Monsters`, ожидание готовности runtime, создание агента, регистрация, `LifeState`/`Destroying`/`AncestryChanged`, высвобождение и защита от повторной привязки |
| `MonsterCombatState` | Состояние, авторитетный реестр преследователей и боевые атрибуты |
| `MonsterChaseNavigation` | Исходный Chase Direct/Path/Blocked и очистка маршрута |
| `MonsterAttackExecutor` / `MonsterCombatPresentation` | Выполнение удара и его анимация |

### Контракт жизненного цикла

1. `Lifecycle.Start` подписывает существующую папку `Monsters` и последующие одноимённые папки в корне Workspace; папка наблюдается однократно.
2. `registerModel` сначала помещает модель в `pending`, ждёт `Game1MonsterRuntime`, навигационный Root/Humanoid и Animator. Неуспех очищает `pending`. Ошибки создания агента логируются и не оставляют полусобранного агента в реестре.
3. Навигационное состояние (`Navigation.Initialize`) готовится **до** публикации `agents[model]`, затем подключаются `LifeState`, `Destroying` и `AncestryChanged`. Запускается один прежний AI-цикл на агента.
4. Смерть немедленно инвалидирует `attackSerial`, останавливает AttackPursuit, Chase, анимации и очищает `HostilePursuitRegistry`; AI-цикл завершает работу.
5. `Release` идемпотентно отменяет поздние callback через `agent.active=false` и `attackSerial`, отключает все per-model подписки, очищает маршрут `Path.Blocked` и реестр цели. `Release` срабатывает при Destroying, уходе модели из Workspace и завершении (в том числе аварийном) AI-цикла.
6. Если `ComputeAsync` завершился **после** освобождения агента, новый guard не даёт заново подключить `Path.Blocked` или начать движение удалённой моделью. Для активных агентов алгоритм не меняется.
7. При удалении папки `Monsters` снимаются её `ChildAdded`/`AncestryChanged`/`Destroying` listeners и высвобождаются дочерние агенты. Повторное добавление папки регистрирует новое наблюдение.

## Что не менялось

Pathfinding-конфигурация, алгоритм Direct/Path, MoveTo, тайминги агрессии, attackSerial-проверки в `MonsterAttackExecutor`, формулы урона, Weapon Volume, отскок, NPC, мирное блуждание и новые M95-маршруты не затрагивались. Нет изменений данных и миграций.

## Проверки

`python system/verify/verify.py` и `python -W error::ResourceWarning -m unittest discover -s system/verify -p test_*.py -q`. Архитектурные тесты исходников не исполняют Roblox runtime. В Studio вручную проверить появление/удаление 10+ монстров, смерть в момент атаки, удаление/возврат `Workspace.Monsters`, уход модели из Workspace и уничтожение во время `ComputeAsync`.
