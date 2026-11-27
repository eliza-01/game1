# M617 · Adaptive AI LOD

База M616. Только планирование периодических решений. `ActorActivityPolicy` определяет интервал после завершения прежнего шага, `ActorAIScheduleQueue` управляет deadline, `ActorAIScheduler` предоставляет Wake. M615/M616 алгоритмы выбора цели, поведения Monster и NPC, Experimental Navigation, Rescue Routes, Collision Detour, Climb, BlockedWait, HomeRecall и боевые таймеры не изменены. Урон, wandering, атаки, физика и репликация продолжают работать независимо.

## Options и режимы

AI Performance: `monsterAi.adaptiveLod.enabled` (false по умолчанию) и `dormantSeconds` (2, диапазон 0,3–2). Сохранение через обычный OptionsStore, Rojo Sync и новая сессия; для Runtime нужна пересборка. При OFF нет дополнительных подписок агентов и cadence callback, фиксированные сроки M616 сохраняются. Активные и неизвестные/переходные состояния всегда 0,1 с. Aggressive Idle: следующий дедлайн сканирования, не более 0,3 с; не используем distance-only Sleep, чтобы игрок не проходил агро между редкими проверками, в том числе на другом этаже или при wandering/телепорте. Passive Idle: редкий safety tick. NPC: только Idle, закреплённый root в домашней позиции, без боя и pending recovery; любой displacement/unanchor возвращает обычный интервал. Неподвижная дальняя популяция агрессивных монстров не получает глубокий сон в M617; это отдельная оптимизация после подтверждения безопасного пространственного пробуждения.

## Пробуждение и lifecycle

Monster: MonsterCombatActive, MonsterAggressive, MonsterSpawning, LifeState. NPC: InCombat, LifeState, Anchored, CFrame. Сигналы сокращают только уже отложенный deadline до `now + base interval`, не меняют состояние и не исполняют шаг синхронно. Повторное пробуждение не создаёт дубль; running/yielding step не запускается повторно. Активный агент не ускоряется; NPC после dormant использует новую фазу, активная частота сохраняется. При удалении подписки очищаются вместе с очередью. При ошибке cadence callback — лог и прежний интервал. Дополнительный Heartbeat или Raycast не создаются. Подписки имеют собственную стоимость; необходимо измерить в Studio.

## Приёмка

- Lua queue/policy: все protected states, дедлайн Aggro, safety tick, wake, удаление/yield, fallback при ошибке. Хэши M616 защищают существующие модули Monster и навигации. M615 hash tests проверяют прежние тела Monster/NPC решений.
- Options: миграция старых манифестов, генерация registry, сохранение экспериментальных параметров, валидация диапазона, UI.
- Studio A/B: Options OFF/ON; вход игрока в Aggro (XZ, разные этажи, wandering, teleport), реакция пассивного на удар, NPC удар/сдвиг/разморозка, смерть/respawn, возвращение, Rescue Route/Climb/BlockedWait/Recall. Сравнить MONNAV, таймеры и частоту кадров, не считать Lua mock физической приёмкой. В опубликованном DEV повторить с 2+ клиентами. Статусы NOT_RUN до фактического теста.
- Далее Navigation Budget: только PathfindingService Legacy/NPC, без переноса Graph.Find в очередь.
