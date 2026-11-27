# M618 · Navigation Budget

База M617. Только два прежних потребителя native PathfindingService: MonsterChaseNavigation (Legacy) и ActorChaseNavigator (NPC). MonsterNavigationDispatch, Experimental Navigation, Rescue Routes, 20/4, Collision Detour, Climb, BlockedWait, HomeRecall, выбор цели и тела решений Monster/NPC не меняются.

## Контракты

- NavigationRequestQueue: FIFO, один ticket на owner (queued/running/ready). O(1) удаление из очереди. Отмена native ComputeAsync не прерывает работу движка: slot удерживается до завершения; отменённый результат уничтожается. Ready результат забирается ровно один раз. Исключения освобождают слот. Никакого catch-up при задержке кадра.
- NavigationScheduler: единственное место CreatePath/ComputeAsync. Сохраняются AgentRadius=1, AgentHeight=4, AgentCanJump=false, WaypointSpacing=3. Начальная позиция читается при фактическом запуске; queued destination обновляется на каждом Chase без изменения места в FIFO. Worker не управляет Humanoid. Результат применяется при следующем действующем решении навигатора, не из callback. Смещение origin/goal на 3 studs и более ведёт к отбрасыванию. Stop/ClearPath, target change/return, death/destroy/backend switch освобождают ticket по контрактам существующих владельцев движения. Старый Path и Blocked connection очищаются вместе.
- Пока ждём, движение к препятствию приостанавливается и окно progress обновляется. Не считаем ожидание failed path/stuck; существующие боевые таймеры и глобальный Home Leash не приостанавливаем. После действительного native failure — прежний direct fallback. Движение Legacy/NPC может задерживаться при заполненной очереди или быстром движении цели; FIFO гарантирует порядок допущенных, а не успешный путь при бесконечном движении цели. Нативный вызов, зависший в движке, удерживает слот, искусственно освобождать его нельзя.
- Pump на существующем ActorAIScheduler после EndBatch; дополнительный Heartbeat, Raycast, RemoteEvent не вводится. Пустая очередь — постоянная проверка head. Experimental не подаёт запросы.

## Options

AI Performance: `monsterAi.navigationBudget.concurrent` default 2 (integer 1–8), `startsPerSecond` default 8 (integer 1–30). Включено для native path; отдельной legacy-реализации нет. Сохранение, Rojo Sync, новая Play сессия; опубликованный Runtime пересобирается. Значения предварительные, подлежат профилированию. Adaptive AI LOD независимо OFF по умолчанию.

## Приёмка

Lua: конкурентные yielding запросы, FIFO 1000 owners, лимит старта, отмена queued/running/ready, освобождение после исключения, dedup и cleanup. Сверка protected hashes M616 (кроме двух изменённых native адаптеров) и decision bodies M614. Studio: одновременно 50/100/200 агентов Legacy/NPC, быстрый движущийся target, attack/stop/return/death/backend switch во время очереди и ComputeAsync; нет stale MoveTo, starvation статичных заявок, утечек Path/Blocked. A/B Experimental — прежние MONNAV, таймеры, маршруты и физика. DEV 2+ клиента. MicroProfiler CPU и native ComputeAsync latency/queue wait измеряются отдельно. KBN-0038 остаётся IN_PROGRESS до игровой приёмки.
