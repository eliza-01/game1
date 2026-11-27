"""Shared monster lifecycle and AI documentation, not per-asset script claims."""
from .house import card

ITEMS = [
    card('monster-spawn-lifecycle', 'Монстры · популяция, смерть, respawn', 'Сервер',
         'Авторские spawn records, maxAlive, индивидуальный цикл смерти и очередной respawn.',
         ['MonsterSpawnRegistry.records', 'MonsterRegistry.monsters'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'MonsterPopulationController резервирует места maxAlive и планирует respawn отдельно для каждого погибшего монстра.',
                 'MonsterSpawnerService собирает риг, hitbox, анимации, wandering и death lifecycle; ресурсы экземпляра очищаются при release.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Время смерти, очередь respawn, HP и положение живой популяции не сохраняются между серверами; при перезапуске популяция создаётся заново из spawn registry.',
                 'Проверить Runtime Place и StreamingEnabled: несколько одновременных смертей, maxAlive, задержки, исключение повторного рождения и cleanup.',
             ]},
         ], ['monster-spawner', 'monster-population', 'monster-death', 'monster-spawns', 'monster-registry']),
    card('monster-ai-pursuit', 'Монстры · aggro, pursuit, navigation, return', 'Сервер',
         'M593 · Home Leash / Death Chase, обход препятствий, прыжок до 1 с, Rescue Routes и аварийный телепорт домой.',
         ['MonsterAggressive', 'MonsterPursuitMode', 'MonsterNavigationBackend', 'MonsterRecoveryMode'], [
             {'title': 'Aggro и границы преследования', 'lines': [
                 'Home Leash: возврат при выходе за home radius от центра спавна или по таймеру без нанесения урона (по умолчанию 30 с, Options). Spawn radius задаёт появление/блуждание, не границу погони.',
                 'Death Chase: home radius и таймер без урона отключены. При однозначной зоне Game1MonsterZone применяется её граница; без зоны или при неоднозначности погоня не ограничена. Потеря цели завершает погоню.',
                 'Обычный Return выполняется пешком; полученный урон может снова запустить погоню. Настройки вида и индивидуальные overrides спавна доступны в Database → Spawn Zones.',
             ]},
             {'title': 'Experimental Navigation · область действия', 'lines': [
                 'Studio: обычные монстры, GP group и зоны 1–6; Guided, Skilled и резервная калибровка используют Legacy. M593: опубликованный Runtime может использовать Experimental для обычных монстров только при двух включённых настройках; по умолчанию Runtime использует Legacy. NPC не затронуты.',
                 'Options → Monster Navigation: Experimental navigation (default ON) и Enable in published Runtime (default OFF). Workspace.Game1ExperimentalMonsterNavigation — override только для Studio, nil наследует Options; compiled Draft также учитывает Runtime opt-in. Для Runtime сохранить Options → Rojo Sync → сохранить исходный Place → Preflight и новый Runtime Draft. Database Rescue Routes — зеркало; нужен Workspace.Game1RescueRoutes в сохранённом Place.',
                 'Direct: горизонтальный луч от головы в пределах радиуса атаки; при препятствии — нижний луч и поиск альтернативы. Приоритет низкого препятствия при свободном верхнем луче; Stuck: выборка движения 1 с, порог 50% (настраиваемо).',
                 'Collision: локальный поиск одного или двух углов коллайдера. Rescue Route конкурирует с Collision/Climb по полной стоимости. Возврат в Direct — свободный луч от головы к пяткам цели + полный горизонтальный луч. Retry при Return/неудаче локального движения сохраняет паузу 1,5 с. NoAccessiblePlan при Chase: один расчёт, затем BlockedRetreat → BlockedWait, без повторного поиска до входа цели в радиус лука или смены контекста.',
             ]},
             {'title': 'Climb · физический прыжок M578/M580', 'lines': [
                 'Обычный физический импульс с высотой Character (PlayerJumpSettings) и текущей горизонтальной скоростью; без CFrame-переноса и левитации. Импульс только на земле, направление фиксируется на одну попытку.',
                 'Весь цикл, включая ожидание отрыва, ограничен 1 секундой. Приземление может завершить попытку раньше; при таймауте план сбрасывается и цель переоценивается. Вертикальный импульс и физические коллизии не отключаются.',
             ]},
             {'title': 'Rescue Routes · авторинг и вход M590', 'lines': [
                 'Studio Edit → Plugins → game1 → Rescue Routes → New route → точки → Apply → сохранить Place. Runtime читает Workspace.Game1RescueRoutes; Database → Rescue Routes — read-only зеркало, не источник графа.',
                 'M590: на старте граф соединяет только свободные начало и конец целого маршрута с ближайшей произвольной точкой на отрезке другой линии, без порога длины, но с перепадом высоты не более значения Options → Monster Navigation → Route connection height (routeConnectionHeight, по умолчанию 2 studs, диапазон 0–100). Сохранить настройки, выполнить Rojo Sync и перезапустить Play: граф строится один раз за серверную сессию. Настройка касается только соединений, не входа/выхода. Уже соединённый конец не создаёт новый переход; внутренние вершины и замкнутые линии не создают мостов. На наклонном отрезке выбирается ближайшая точка в допустимой полосе высот. Переходы двусторонние, отдельные от авторских линий, с проверкой коллайдеров при поиске пути. Лимит 2048 авторских сегментов.',
                 'M586: сначала ранжируются целые авторские маршруты по минимальной 3D-дистанции от пяток цели до линии. Затем в радиусе searchDistance (по умолчанию 40 studs) ищется ближайшая доступная 3D-проекция монстра, без старого порога высоты 2 studs. При блокировке проекции — поиск по длине линии в обе стороны с шагом 20 studs; от найденной свободной точки уточнение к цели шагом 4 studs в пределах одного грубого интервала.',
                 'M588: вход — единственный луч от пяток монстра прямо до точки на линии. Любое попадание в учитываемый коллайдер отклоняет кандидата (FootBlocked), включая низкое препятствие; луч от головы для входа не используется. Это проверка линии, не всего объёма тела. Если входа нет, пробуется ближайший соседний маршрут по длине перехода, затем остальные связанные маршруты, каждый не более одного раза за поиск. ID входной и целевой линии остаются независимыми. Кэш входов, путей и переходов общий на один поиск.',
                 'Архитектура: MonsterRescueGraph — координация; Topology — граф; Connections — переходы; Sampling — шаги 20/4; Segments — геометрия; Routes — ранжирование; Entries/Exits — выбор входа/выхода; Paths — Dijkstra; Queries — кэш и диагностика. Вершины описывают геометрию, не имеют собственного приоритета.',
             ]},
             {'title': 'Rescue Routes · выбор выхода M582/M586', 'lines': [
                 'При выборе плана фиксируется исходная 3D-дистанция между ногами монстра и целью. Конечная точка маршрута допустима только если расстояние от неё до цели не превышает исходное. Равенство допустимо; промежуточные точки могут удалять монстра от цели.',
                 'На каждом достижимом сегменте вычисляется пересечение со сферой допустимых выходов вокруг цели. Проверяются ближайшая по высоте точка, 3D-проекция и границы допустимого интервала; M584: если все аналитические выходы отклонены, проверяются промежуточные точки допустимого интервала (до 32 интервалов на отрезок).',
                 'На выбранном маршруте приоритет среди доступных выходов: минимальный перепад высоты до пяток цели, затем 3D-дистанция до цели, затем расстояние до входа и полная длина пути. Радиус входа не ограничивает выход. Без допустимого доступного выхода Rescue Route отклоняется; остаются обычные альтернативы навигации.',
             ]},
             {'title': 'Blocked Pursuit · отступление M591', 'lines': [
                 'При NoAccessiblePlan монстр отходит от цели до горизонтальной дальности лука из Database + blockedRetreatBuffer (2 studs). M592: максимум по всем лукам (сейчас 40 studs), ограниченный боевыми лимитами, независимо от наличия или экипировки лука у игрока. Отступление — короткие проверяемые физические шаги, с учётом Terrain и границ преследования. Если дальше отойти физически нельзя, ожидание начинается в достигнутой точке.',
                 'BlockedRetreat: таймер застревания и Home Leash без урона не идут. BlockedWait: оба таймера начинают отсчёт заново, граф повторно не ищется. Если цель снова входит в радиус лука, монстр возобновляет сближение, заново проверяет доступность пути. Если ожидание началось внутри радиуса, повторное сближение требует выхода цели и нового входа в радиус, чтобы не создавать цикл.',
                 'Options → Monster Navigation: Blocked retreat buffer = 2 studs, Blocked retreat speed = ×1, Blocked reengage speed = ×1,5, Rescue Route speed = ×1,5 от обычной Run speed. Последний действует на подходе к входу, авторской линии, переходах и прыжках во время плана. Коэффициенты не перемножаются; Slow/Root/Stun применяются. Stuck return / No damage return остаются существующими настройками. Сохранение → Rojo Sync → перезапуск Play.',
                 'MonsterBlockedPursuit — политика фаз/таймер ожидания; MonsterBlockedRetreatGeometry — физические шаги; MonsterNavigationSpeed — общий множитель движения/анимации. MONNAV: BLOCKED_WAIT, BLOCKED_REENGAGE, MODE BlockedRetreat/BlockedWait.',
             ]},
             {'title': 'StuckTimeout · аварийный возврат M580', 'lines': [
                 'Независимый watchdog прогресса в Chase/Return: текущий Options stuckReturnSeconds — 20 с; выборка раз в 1 с, повторные прыжки в прежнем вертикальном диапазоне не сбрасывают таймер. Это не таймер прыжка и не таймер без урона. M591: после NoAccessiblePlan при Chase таймер запускается только в BlockedWait.',
                 'При StuckTimeout: остановка боя/движения, fade out 1,05 с → перенос той же модели на собственный home → fade in 1,05 с. ID и HP сохраняются; на время перехода модель неуязвима. Обычный Return остаётся пешим.',
                 'MonsterHomeRecallVisual отправляется игрокам в радиусе 160 studs: фиолетовый столб на обеих точках через общий BuffCastVisuals, высота не менее 10,4 studs. Видимость и прежнее состояние восстанавливаются после перехода.',
             ]},
             {'title': 'Диагностика Studio Play', 'lines': [
                 'Server Command Bar: workspace:SetAttribute("Game1MonsterNavTrace", true). Необязательный фильтр: workspace:SetAttribute("Game1MonsterNavTraceFilter", "gremlin"). Output → MONNAV; отключение trace через false.',
                 'M585: дополнительно workspace:SetAttribute("Game1MonsterNavRouteTrace", true) включает GRAPH_BEGIN / GRAPH_ROUTE / GRAPH_ENTRY / GRAPH_NODE / GRAPH_TRANSFER / GRAPH_EXIT_EDGE / GRAPH_EXIT / GRAPH_SELECTED_ENTRY / GRAPH_SELECTED_EXIT. ID исходного маршрута, сегмент, координаты, причина отказа и полный путь коллайдера из существующего Raycast; cached=true означает повторное использование результата. Выключить подробности через false.',
                 'BACKEND подтверждает Experimental/Legacy; GRAPH_SEARCH показывает entryCandidates, entries, entryChecks, reachableExits, exitChecks, transferChecks; GRAPH_ROUTE — ранжирование/отсев целой линии; CANDIDATES — routeId и entryRouteId, стоимость и ранг выхода; CLIMB_TIMEOUT, RETURN StuckTimeout и HOME_RECALL_OUT/IN/DONE — переходы восстановления.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Terrain исключён из навигационных лучей, но сохраняет физические коллизии. Авторские линии должны быть физически проходимыми; ограниченный Collision не гарантирует обход составных препятствий.',
                 'Threat, цель, фаза атаки, положение во время Return и таймеры живут только на одном сервере и не восстанавливаются.',
                 'Приёмка KBN-0032 открыта: Studio Play, Runtime Draft с двумя клиентами, профиль Legacy/Experimental 50/100/200 активных монстров (CPU, Raycast, физика, время построения графа). Доступность опции Runtime не означает разрешение публикации.',
                 'M593: свободная проекция без сетки 20/4, отсев линий вне радиуса, ранний отсев далёких игроков при aggro. BlockedWait без новых поисков и повторных записей таймера. Граф строится только при активном backend; периодические диагностические записи скорости/лучей и точки плана только в Studio. GP/Test Debug Hub не запускается в опубликованной игре; compiled Draft в Studio загружает его только при Start in Hub; общие безопасные контракты остаются в коде.',
             ]},
         ], ['monster-ai', 'actor-home', 'monster-target', 'monster-death-chase', 'monster-nav',
             'monster-nav-dispatch', 'monster-nav-experimental', 'monster-nav-config', 'monster-nav-options',
             'monster-recovery-geometry', 'monster-climb', 'monster-rescue-graph', 'monster-rescue-topology', 'monster-rescue-segments', 'monster-rescue-routes',
             'monster-rescue-connections', 'monster-rescue-sampling', 'monster-rescue-entries', 'monster-rescue-exits', 'monster-rescue-paths', 'monster-rescue-queries', 'monster-stuck-watchdog', 'monster-blocked-pursuit', 'monster-blocked-retreat-geometry', 'monster-navigation-speed',
             'monster-home-recall', 'monster-home-recall-visuals', 'monster-buff-visuals', 'monster-nav-trace',
             'monster-registry', 'monster-spawns', 'monster-gameplay-doc']),
    card('monster-attack-visuals', 'Монстры · атака, анимации, эффекты', 'Бой',
         'Серверная боевая механика и клиентская визуализация движения и hit feedback.',
         ['MonsterAnimationRegistry', 'EntityHitboxService'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'MonsterAttackExecutor исполняет атаку; общий DamageService и EntityHitboxService обрабатывают урон и боевые границы.',
                 'MonsterAttackLocomotionController визуализирует анимации, MonsterDeathLifecycle ведёт смерть и освобождение слота.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Боевой результат не создаёт подтверждённого постоянного loot/XP/quest transaction; выдача наград требует отдельного серверного контракта.',
                 'Нужна Studio Play проверка сетевой синхронизации атак, headshot/OBB, анимационных переходов и повторного появления.',
             ]},
         ], ['monster-attack', 'monster-client-attack', 'monster-death', 'damage-service', 'entity-hitbox']),
]
