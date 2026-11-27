# M615 · Actor AI Scheduler — этап фиксированной частоты

База: свежий диагностический архив M613 + M614. Задача KBN-0038-T02 (частично): сначала закрепить поведение, затем заменить периодические циклы без AI LOD. KBN-0032/0033 остаются защищёнными контрактами навигации и популяции.

## Владение

- ActorAIScheduler: один серверный Heartbeat для периодических решений; ActorAIScheduleQueue: индексированная min-heap дедлайнов, FIFO при равном дедлайне, O(log N) вставка/удаление. У агента один entry (в очереди или выполняется). Нет сканирования всех агентов на каждом кадре. Удаление из heap немедленное. Уже выполняющийся yielding callback не отменяется принудительно; после возврата не регистрируется снова. Существующие защиты lifecycle внутри навигаторов сохранены.
- MonsterAgentLifecycle: создание, регистрация, удаление; при terminal return/error освобождает ресурсы прежним путём. MonsterAIService.stepAgent: точное тело одной итерации M614 (continue → return, terminal break → return false); проверки времени, урона и навигации прежние.
- NpcCombatAIService: Bind/Unbind регистрируют/удаляют агента. Периодический tickAgent передан общей очереди, отдельный Heartbeat сопровождения атаки остаётся. Ошибка NPC логируется и допускает следующий шаг; ошибочный Monster освобождается как раньше. DamageSignals и attack timers не проходят через scheduler.
- Интервалы: Monster первый шаг 0,1–0,2 с; последующие 0,1 с после завершения, как раньше. NPC сохраняет общую фазу 0,1 с; пропущенные тики не догоняются. Дедлайны привязаны к Heartbeat, задержка до ближайшего доступного кадра; пропущенные шаги не догоняются. Aggro scan 0,3 с. Возможен сдвиг фактических тиков, особенно у NPC; проверять в Studio. Уменьшения частоты нет, при перегрузке жёсткий бюджет не вводится. Для безопасной поддержки yielding Legacy каждый due step запускается через task.spawn; возможный overhead надо измерить, не заявлять экономию CPU.

## Не изменено

MonsterNavigationDispatch, Experimental, Rescue Graph (вход 20/4, Foot Raycast, M582, переходы, выход), Collision Detour, Climb, BlockedRetreat/Wait, Reengage, Home Leash, Death Chase, StuckTimeout, Recall; Monster/NPC target policy, hit timing, DamageService, spawn records, Options, Runtime opt-in. Frame-rate pursuit и обработка получения урона независимы от scheduler. Rojo включает src/server целиком.

## Дальнейшие патчи

1. Локальная выборка игроков, строго XZ-эквивалентность, сохранение порядка равных дистанций, изоляции и удержания цели.
2. AI LOD после приёмки фиксированного scheduler: не замедлять ни одно активное состояние, включая Retry/BlockedWait/возврат; dormant только безопасный Idle, немедленное пробуждение от damage, обнаружение входа в Aggro не медленнее текущего scan. Options и частоты отдельно, OFF до приёмки.
3. ComputeAsync budget только Legacy/NPC: coalescing, отмена устаревших результатов, справедливость, ожидание не считается застреванием. Experimental Rescue Graph остаётся синхронным и неизменным.
4. Приёмка: MONNAV до/после, aggro/target lock, RescueRoute, прыжки, BlockedWait и damage wake, home recall, смерть/respawn, NPC, Studio/DEV. Профилирование под нагрузкой отложено по решению владельца M613; количественная приёмка обязательна.

## Проверки

Lua: deadline queue, 1000 registrations, FIFO, ошибки, yield, удаление и повторное планирование. Статическая сверка тела решений с M614. Реальная физика, время тиков, интеграция Roblox API и CPU не проверены в Studio/DEV.
