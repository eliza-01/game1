# M103 — декомпозиция атаки и анимаций Monster AI

> **Исторический документ.** Фиксирует состояние на момент указанного этапа; отдельные механизмы могли быть заменены. Действующие контракты: [актуальное ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).


**База:** `game1_diag_2026-10-16_13-23-03.zip` + применённый M102. Изменение только архитектурное; нет новой навигации.

## Ответственность

| Компонент | Владеет | Не владеет |
| --- | --- | --- |
| `MonsterAIService` | Привязка и жизненный цикл агентов, AI-цикл, выбор действия через `MonsterCombatState.Decide`, существующие `MoveTo` и Pathfinding | Timeline Hit, урон, загрузка/управление AnimationTrack |
| `MonsterTargetPolicy` (M102) | Выбор цели, геометрия попадания, дистанции, line-of-sight | Атака и анимации |
| `MonsterCombatState` (M102) | Цель, переходы и регистрация в `HostilePursuitRegistry` | Атака и анимации |
| `MonsterAttackExecutor` (M103) | Разрешение Attack Timeline, запуск атаки, Hit callback, finish callback, сериализация и активное преследование `ActorAttackPursuit` | Общий навигационный маршрут, выбор цели, загрузка треков |
| `MonsterCombatPresentation` (M103) | Опубликованные ряды анимаций, выбор с весами, треки, скорость/приоритет, анимационные атрибуты, startup-параметры run | Урон, решения AI, Pathfinding |

## Сохранённое поведение

- Тот же `Random.new()` обслуживает задержку AI, весовой выбор атак и стартовую фазу Run. Новые экземпляры RNG не создаются.
- Начало и завершение атаки, Hit time, `attackSerial`, `nextAttackAt`, получение реального положения цели и `TargetPolicy.AttackStillConnects` сохраняют прежние условия.
- Hit проверяется **после** проверки активной сессии/цели и **перед** `DamageService.Apply`; эффекты и атрибуты `LastMonsterAttackDamage`, `MonsterAttackPhase` сохраняются.
- `ActorFacingTracker`, `ActorAttackPursuit`, движение во время анимации и публикация `MonsterAttackPursuitActive / MonsterAttackPursuitPlaybackSpeed` продолжают действовать по прежним алгоритмам.
- `MonsterAIService` передаёт исполнителю только `StopNavigation` и `RunSpeedStuds` как интерфейс движения, без доступа исполнителя к общему Pathfinding.
- При смерти, потере цели или выходе из боя `attackSerial` по-прежнему инвалидирует отложенные Hit и finish события, а `HostilePursuitRegistry` очищается в `MonsterCombatState`.
- Нет изменений в `PathfindingService:CreatePath`, `Humanoid:MoveTo`, геометрии, конфигурациях публикации, AI NPC и WeaponBounce.

## Проверки

`verify.py`, полный `unittest`, установка и обратный откат патча на независимой копии версии после M102. Новые source-level тесты проверяют границы модулей, сохранение Timeline Hit, сериализацию, очистку и связи с движением.

**Ограничение:** статические проверки не заменяют Roblox Studio. Там нужны проверки старта атак, Hit/Miss, движения при незавершённой атаке, смерти на Windup и продолжения Chase после Attack.
