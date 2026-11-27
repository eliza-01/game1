# Gameplay infrastructure · M570–M593

**Дата сверки Monster Navigation / Runtime:** 27.11.2026, M593 на базе `game1_diag_2026-11-27_06-32-10.zip` (M592). **Статус:** CURRENT SOURCE CONTRACT / STUDIO & RUNTIME VALIDATION OPEN. Остальные разделы сохраняют сверку M570/M571. См. [аудит M593](M593_MONSTER_RUNTIME_AUDIT_RU.md).

## 1. Database и GP

- Database всегда открывает Main: Monsters, Skills, Weapons, Levels, Character, Armor, Model bindings, Spawn Zones, Rescue Routes. Asset History и Logs отдельно. Monsters: drag колонок, сортировка по заголовку, поиск и сохранение порядка в браузере; не меняет порядок канонических записей. Options: drag секций вместо стрелок, раскрытие по имени/иконке. Monster Debug и Movement Debug удалены; остаются восемь пиктограмм TL/CS/HS/CD/HP/UI/GP/AG.
- Skills: общие Buff/Debuff без владельца, отдельные Monster/Character. Четыре D-баффа, шесть дебаффов; короткие Might/Haste и их два Skilled-профиля удалены. Индивидуальные навыки персонажей и масштабирование по грейду ещё не готовы. Восстановленный срез: Might +20% ATK, Earth +30% MaxHP, Life +1 HP/с, Wind +20 Speed (+2 studs/s), 600 с, Slow −40%. Источник чисел — Database, не этот текст.
- GP: 1000 Gold при первом входе, кошелёк слева внизу, сохраняется при смерти, телепорте и смене комплекта; Exit удаляет transient session. Buffer открывает магазин, покупка по иконке 5 Gold, повторный бафф обновляет срок, не складывает силу/длительность. Пять монет летят к NPC локально; HUD показывает иконку поверх магазина. База регена 1 HP/с целым секундным тиком; Guided без регена. Hub возвращает без потери денег и баффов; новый комплект снимает баффы. Spawn создаёт группу с портретом/именем/уровнем/красной звёздочкой для aggressive; overhead не блокирует атаку. GP только Studio, не постоянная экономика.
- ATK M552: база 5 + накопленный Levels.attackBonus; первый шаг +1, последующие растут по среднему относительному приросту стоковых оружий между грейдами / число переходов (4, затем 5), округление шага до сотых. HP компенсирован статически относительно M549, без зависимости от атакующего игрока. Проверка TTK и темпа 9–12 ч до B открыта. Оба варианта M551 отменены.
- AG: общий Aggressive/Aggro/Death Chase по виду, индивидуальные overrides спавна; тонкий контур агро текущей GP-зоны включён по умолчанию независимо от панели. EN/RU имена. Реальные модели требуют публикации; GP proxy не означает, что вид готов для игрового мира.

## 2. Spawn Zones — Studio и Database

1. Studio Edit, Control Center запущен → Plugins → game1 → Monster Spawns → вид и доступный уровень (balanceId) → параметры → Place spawn zone → Apply. Defaults: radius 15, count 3, respawn 10 s, home radius 150; aggressive/aggro/death chase из Database. Неопубликованные виды доступны для планирования, runtime ждёт готовую модель и анимации; не подменяет их Gremlin.
2. Database → Main → Spawn Zones: редактируются вид/уровень, radius, count, aggressive, aggro radius, pursuit mode, home radius, respawn, Enabled. Position, Place/map, ID read-only. Создание, перемещение, удаление только Studio. В Monsters → Registered monsters — портреты, все виды из Database, модель/текстура/готовность; старые формы авторинга удалены.
3. Save changes → POST `/api/monster-spawns/database-update`, проверка revision каждой строки и атомарная запись пачки спавнов. Черновик не теряется при смене вкладки; polling 3 с только без правок/активного поля. Если одновременно изменены баланс и спавны, сначала сохраняется баланс, затем пачка спавнов; ошибка второй операции оставляет её черновик (не единая транзакция двух реестров).
4. Источник runtime: `assets/manifests/monster-spawns.json` → `src/server/monster/MonsterSpawnRegistry.luau`. В Studio Refresh Database / restore markers, затем Rojo Sync → Restart Play. Старый Studio draft не должен перезаписать новую ревизию. NPC authoring отдельно.

## 3. Политика преследования (M568)

Home Leash: радиус от спавна + таймаут отсутствия урона (default 30 с). Death Chase: ни радиус, ни таймаут не применяются; при однозначной размеченной `Game1MonsterZone` действует её граница, без неё или при неоднозначности — неограниченная погоня. GP основные зоны используют свои границы. Смерть цели завершает погоню; возврат разрешён из-за пределов ограничения. Guided/group/Skilled/резервная калибровка сохраняет прежнюю политику. В записи сохраняется последнее числовое значение Home Leash для обратного переключения, в Death Chase оно неактивно и скрыто. AI, recovery и ranged retreat используют `MonsterDeathChasePolicy`, `MonsterPursuitMode` отражает фактический режим.

## 4. Experimental Navigation — M566/M569/M573/M574

Studio: обычные монстры, GP group и зоны 1–6; Legacy для Guided/Skilled/резерва. M593: `MonsterNavigationDispatch` разрешает Experimental вне Studio только при `enabled=true` и `runtimeEnabled=true` (новая настройка Enable in published Runtime, default OFF). NPC неизменны. Workspace attribute `Game1ExperimentalMonsterNavigation` имеет приоритет только в Studio; nil наследует Options; compiled Draft также учитывает runtimeEnabled. Граф не строится при выключенном backend. Runtime Draft требует свежих Rojo scripts и сохранённой папки Game1RescueRoutes; публикация до приёмки запрещена.

| Состояние | Поведение |
| --- | --- |
| Direct | Сразу и раз в 1 с горизонтальный луч с верха RootCollider − 0,05 studs в сторону цели, длина min(attack radius, горизонтальная дистанция). При попадании — нижний луч (ноги +0,25), поиск альтернативы без ожидания застревания. |
| Stuck | Замер 3D-перемещения / ожидаемая дистанция, 1 с, порог 50%; учитывать реальные паузы/скорость. При свободной голове и скорости ниже порога — немедленный прыжок. |
| Climb (M578/M580) | При свободном верхнем луче и скорости ниже порога — обычный прыжок с вертикальным импульсом как у Character и текущей горизонтальной скоростью монстра. Без levitation, CFrame и Climb speed. Повторный импульс только на земле. Максимум 1 с на попытку, затем сброс плана и переоценка цели; раннее приземление завершает попытку. |
| Collision | Тонкий слой поиска 0,2 × 60 × 40 studs на уровне головы; ограниченный обход через один или два угла. Не Wall Follow. |
| RescueRoute | Доступный вход и выход по графу, сравнение полной длины с обходом/подъёмом. |
| Recovery exit | Раз в 1 с луч от головы к пяткам цели +0,1; если свободен — горизонтальный луч до цели целиком (M574), а не только в радиусе атаки. Только оба свободны разрешают Direct. Эта же пара проверяет выходы Collision и Rescue Route. Не ждать первой точки или двух подтверждений. |
| Retry / Blocked Pursuit M591 | Chase NoAccessiblePlan — отойти до дальности лука из Database (M592: максимум по лукам, сейчас 40 studs, независимо от экипировки) + 2 studs, ждать; если прохода для отступления нет, ждать в достигнутой точке. Таймеры стартуют в BlockedWait. При повторном входе цели в радиус — сблизиться с ×1,5 Run. Rescue Route также ×1,5 Run, подход/переходы включены. Options: blockedRetreatBuffer, blockedRetreatSpeedMultiplier, blockedReengageSpeedMultiplier, rescueRouteSpeedMultiplier. Return сохраняет Retry и watchdog. |
| StuckTimeout (M580) | Глобальный таймер без прогресса в Chase/Return: 1,05 с fade out, телепорт на собственный spawn, 1,05 с fade in. HP/ID сохраняются. Высокий столб бафа на обеих точках; неуязвимость на время перехода. |

Terrain исключён из навигационных запросов, но сохраняет физику. Резервные Blockcast для щелей и двойной коридор удалены M566; остаются отдельные melee/Hit; прыжок сохраняет обычные физические коллизии. Атаки/спецкасты не прерывают recovery; активная анимация атаки не переписывается новым навигатором. Не добавлять новую систему вместо диагностики фактического сбоя.

## 5. Rescue Routes

Studio Edit → Plugins → game1 → Rescue Routes: New route, клики по поверхности, Close loop при необходимости, Apply и сохранить Place. Имена и каталоги, Unsorted для прежних линий. Синие — сохранённые, жёлтые — выбранные в списке, зелёные — черновик. Explorer не выбирает объект удаления. Delete только выбранного, с подтверждением; отмена черновика не меняет сохранённые данные; Undo last deletion восстанавливает ID; Resume drawing продолжает приостановленный черновик. После Studio Undo/Redo — Sync Database.

Граф: `Workspace.Game1RescueRoutes` (Folder/Vector3Value), максимум 2048 авторских сегментов. M590: при старте только свободные начало и конец целого маршрута соединяются с ближайшей произвольной точкой на отрезке другого маршрута, без порога длины, но с перепадом высоты не более Options → Monster Navigation → Route connection height (routeConnectionHeight, по умолчанию 2 studs, диапазон 0–100). После сохранения выполнить Rojo Sync и перезапустить Play; настройка касается только соединений. Существующие стыки учитываются первыми, внутренние вершины и замкнутые линии не инициируют мосты. Переходы двусторонние, отдельно от авторских линий; ненулевые переходы проверяются лучом при поиске пути, результат кэшируется. Исходные линии и ID не меняются. Database → Rescue Routes — read-only зеркало `assets/manifests/rescue-routes.json`, не резервная копия Place и не источник runtime-графа. При ошибке HTTP локальный маршрут сохраняется.

`MonsterRescueGraph` (M588): ранжирование по ближайшей 3D-проекции цели. На выбранной линии проверяется ближайшая проекция пяток монстра; при блокировке пробуем ±20 studs вдоль линии, затем уточняем свободную грубую пробу к цели шагом 4 studs в пределах одного интервала. Радиус searchDistance сохраняется. M587: единственный луч от пяток до точки, любой учитываемый коллайдер отклоняет вход (FootBlocked). Если входа или полного плана нет, пробуем соседние линии по длине переходов, не повторяя поиск входа на одной линии. Выход M582: только точки не дальше от цели, чем исходная 3D-дистанция между ногами монстра и цели; промежуточные точки не ограничены этой сферой. Среди достижимых выходов выбранного маршрута приоритет высоты, затем дистанции; при равенстве — ближайший вход и полная стоимость. Аналитические точки выхода и резервная сетка (до 32 интервалов на сегмент) сохранены. Нужен свободный выход к цели. Кэш входов/выходов общий для одного поиска. Dijkstra и политика преследования сохранены. Сравнение с Collision/Climb по полной стоимости и досрочный сход не меняются. Конечный набор проб не гарантирует нахождение произвольной узкой щели и не доказывает физическую проходимость. Граф строится один раз за серверную сессию.

Модули Rescue: `MonsterRescueGraph` — оркестрация; `MonsterRescueTopology` — построение; `MonsterRescueConnections` — отдельные переходы; `MonsterRescueSampling` — шаги 20/4; `MonsterRescueSegments` — проекции, сферы и кандидаты; `MonsterRescueRoutes` — ранжирование и связность; `MonsterRescueEntries`/`MonsterRescueExits` — поиск входа/выхода; `MonsterRescuePaths` — Dijkstra и реконструкция; `MonsterRescueQueries` — per-search кэш, счётчики и observer. Физические проверки остаются в `MonsterRecoveryGeometry`.

## 6. Диагностика и подтверждённые наблюдения

Server Command Bar в Play:

```lua
workspace:SetAttribute("Game1ExperimentalMonsterNavigation", true)
workspace:SetAttribute("Game1MonsterNavTrace", true)
-- необязательно: workspace:SetAttribute("Game1MonsterNavTraceFilter", "gremlin")
```

M585: отдельный Studio-only атрибут `Game1MonsterNavRouteTrace=true` (при включённом основном trace и его фильтре) включает `GRAPH_BEGIN`, `GRAPH_ROUTE`, `GRAPH_ENTRY`, `GRAPH_NODE`, `GRAPH_EXIT_EDGE`, `GRAPH_EXIT`, `GRAPH_SELECTED_ENTRY/EXIT`, `GRAPH_PLAN_REJECTED`: исходные ID маршрутов и номера сегментов (у соединителей оба источника), координаты, расстояние, причины Leash/Cooldown/HeadBlocked/FootBlocked/HeelBlocked/ExitDistance/Unreachable, имя коллайдера и cached. `GRAPH_SELECTED_*` означает победителя поиска графа, не обязательно итоговый PLAN. Диагностика использует уже сделанные проверки, без дополнительных Raycast. По умолчанию выключена.

Output: фильтр MONNAV. BACKEND, BODY_GOAL, PRIMARY_HEAD, PROBE_FOOT, HEEL_RAY, SAMPLE, CANDIDATES (exitHeightDelta/exitDistance), GRAPH_SEARCH (entryCandidates/entries/entryChecks/reachableExits/exitChecks), PLAN, MOVE_TO, EXIT_ROUTE, STOPNAVIGATION, RETURN, AI_ACTION. Не добавляет кастов. Выключить trace через false; в Edit удалить override для наследования Options, если нужно.

Факты пользовательского теста до M568/M569: сначала BACKEND Legacy при config=true/override=false, затем Experimental; верхний/нижний лучи обнаружили стену, CANDIDATES nil → NoAccessiblePlan, NoDamageTimeout встречался. Позднее пользователь подтвердил успешный проход по маршруту из другой точки ещё до последнего патча. Это частичная положительная проверка, не доказательство исправления всех входов или производительности. Не считать M568–M570 принятыми по этому наблюдению.

## 7. Открытая приёмка

- [KBN-0032](../kanban/specs/KBN-0032.md): несколько стартовых точек одной стены, кольцо с лестницей, разная высота выхода, низкая ограда, движущаяся цель, Root/Stun, смерть и возврат, Death Chase >30 с и за пределами 150 studs, размеченная граница. Профиль серверной нагрузки с 50/100/200 активными монстрами и сравнение с Legacy; без вымышленных CPU/FPS.
- [KBN-0033](../kanban/specs/KBN-0033.md): Studio → Database → редактирование → Refresh/restore → Rojo → Play, устаревшая ревизия, отмена/удаление, независимость NPC, непубликованные модели.
- [KBN-0026](../kanban/specs/KBN-0026.md): покупка/повтор/истечение, золото, реген, HUD и второй клиент. [Design](../kanban/specs/KBN-0031.md) и [Economy](../kanban/specs/KBN-0029.md) остаются открытыми.
- M570: ранее сообщено 284 профильных теста и Chromium с тестовым API; это не Studio/production. Для M571 проверяются только изменённые документы и Kanban. Откат docs-only патча не меняет Place, JSON gameplay или runtime.
