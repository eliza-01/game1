# M104 — выделение существующей навигации Chase из MonsterAIService

> **Исторический документ.** Фиксирует состояние на момент указанного этапа; отдельные механизмы могли быть заменены. Действующие контракты: [актуальное ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).


**База:** архив `game1_diag_2026-10-16_13-23-03.zip`, последовательно M102 и M103. Это рефакторинг без новой системы обхода препятствий.

## Границы ответственности

| Модуль | Ответственность |
| --- | --- |
| `MonsterAIService` | Владение агентами, цикл принятия решений, переключение Combat State, вызовы Attack/Navigation/Presentation, жизненный цикл сущностей |
| `MonsterChaseNavigation` (M104) | Текущие Chase Direct/Path, обновление `MoveTo`, `ComputeAsync`, `Path.Blocked`, таймеры и критерии застревания, состояние маршрута агента, остановка и очистка |
| `MonsterAttackExecutor` (M103) | Timeline-атака и **отдельное** движение во время атаки через `ActorAttackPursuit` |
| `MonsterWanderController` (M90+) | Мирное блуждание — не менялось |
| `MonsterTargetPolicy`, `MonsterCombatState` (M102) | Выбор целей и состояние боя — не менялись |

`MonsterChaseNavigation` принимает уже созданного агента и цель `Vector3`; выбор цели и переход в Chase остаются за `MonsterAIService`. Методы `Initialize / NavigateTo / StopNavigation / ClearPath / RunSpeedStuds` локальны для серверного Monster AI. `MonsterAttackExecutor.Begin` по-прежнему получает замороженный интерфейс `AttackMovement` только с `StopNavigation` и `RunSpeedStuds`.

## Совместимость поведения

- Значения `DIRECT_REFRESH_SECONDS=0.30`, `PATH_REFRESH_SECONDS=0.75`, `PATH_TARGET_MOVE_THRESHOLD=3`, `STUCK_CHECK_SECONDS=0.80`, `STUCK_PROGRESS_STUDS=0.35`, `WAYPOINT_TOLERANCE=1.25` перенесены без изменений.
- `AgentRadius=1`, `AgentHeight=4`, `AgentCanJump=false`, `WaypointSpacing=3`, порядок `ComputeAsync`, `Path.Blocked`, fallback Direct, `MoveTo`, скорости и индексы waypoint сохранены.
- Подписка `Path.Blocked` отсоединяется прежним `clearPath` при смене маршрута, выходе из боя, смерти или удалении модели. Параметры и начальные значения состояния совпадают с прежними.
- При активной атаке общий цикл не вызывает Chase-навигацию; продолжает работать прежний `ActorAttackPursuit`. Переход к атаке останавливает Chase.
- Не внедряется M95, новая система маршрутов, телепортация, изменения NPC, урона, анимаций или спавна.

## Проверки

`verify.py`, исходные 237 тестов, новые M104 source-level контракты, установка и reverse на базе M103. Эти тесты проверяют структуру и исходные ветви, **не** работоспособность Roblox Pathfinding на препятствиях. В Studio требуется проверить Chase перед стеной, возврат Chase после атаки, прерывание при смерти и удаление монстра во время Pathfinding.
