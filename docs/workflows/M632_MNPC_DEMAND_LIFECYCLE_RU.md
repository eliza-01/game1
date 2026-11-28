# M632 · MNPC Demand-driven Lifecycle

> Исторический отчёт. Актуальный серверный режим и переключатель описаны в [M639](M639_MNPC_RUNTIME_DEMAND_RU.md); M632 pilot заменён.

## Реализовано

Единый `actor/MnpcDemandLifecycle` для Monster и NPC подключён к существующему `ActorAIScheduler` и `PlayerSpatialIndex`. Без нового Heartbeat, отдельного таймера на сущность, RemoteEvent или нового AI owner. Цикл `full → shell → loading → preparing → full` отделяет собственно риг от entity/root/HP/spawn slot/AI. На обычном FULL пути нет дополнительных пространственных запросов.

- Live release: выключить Damageable/readiness, освободить native pose binding и его подписки/треки, снять существующие OBB, освободить точный presentation lease. Navigation shell и его collider сохраняются. Monster idle events имеют отдельный owner поколения; wander owner не уничтожается. NPC motion intent сохраняется, при rebind воспроизводится его текущее состояние. NPC weapon set должен соответствовать существующей политике AI.
- Acquire: clone по актуальному root с M630 metadata, применить прежний Monster bridge / NPC equipment + rig alignment, восстановить существующий OBB binding и native tracks. Damageable включается после готовности pose. Не воспроизводить spawn FX при восстановлении. Общий один admission slot удерживается до pose readiness; retry 5 s, readiness timeout 15 s после возврата acquire. Нативный yielding acquire сам по себе не имеет безопасного принудительного timeout/cancel; слот удерживается до его завершения. При смерти/удалении stale ticket не публикует binding. При ошибке release состояние `fault`, предупреждение, дальнейшие переключения не выполняются; Studio pilot, не production fallback.
- Demand учитывает всех игроков (горизонтальная пространственная выборка), текущую цель, активную атаку/cast, возврат, recovery, spawn, статусные эффекты. Неподдержанные shell metadata, GP test monsters, отсутствие валидной начальной геометрии/позы и несовместимый NPC mount/alignment не переводятся в pilot.

## Граница M632

M632 — **выключенный по умолчанию Studio-only pilot**, не изменение опубликованного Runtime. Обычные спавнеры по-прежнему сразу создают FULL. В пилоте дальние существа могут исчезнуть полностью до готовности будущего клиентского LOD; поэтому production demand не включаем. Пилотные пороги 512 / 640 studs (включение / освобождение), 5 s непрерывно без потребности; не финальные пороги LOD и не доказанная граница боевой дистанции. На двух клиентах активная серверная pose по-прежнему может реплицироваться. Отдельные gates: combat reach/teleport/attack admission, strict per-client native isolation, initial shell-only spawn, бюджет client presentation, asset manager MNPC, FULL/LOD1/UNLOADED. Не считать их реализованными.

Опциональный Studio Play server Command Bar: `workspace:SetAttribute("Game1MnpcDemandPilot", true)`. Выключить: `workspace:SetAttribute("Game1MnpcDemandPilot", false)` (здоровые sleeping shell запрашивают FULL на следующих AI ticks; fault или недоступный ассет требуют перезапуска симуляции). `Game1MnpcDemandStage` показывает shell/loading/full у прошедших переход. Пилот не требует действий владельца до появления клиентского LOD, но native engine acceptance остаётся NOT_RUN. Не использовать на опубликованном сервере.

## Проверки

Общий Lua oracle M632: default off/no spatial queries, any-player proximity, hysteresis/hold, combat/effect pins, два домена и общий slot до readiness, failed acquire/retry, readiness timeout, remove during acquire, disable restores FULL. Source contracts проверяют порядок release и rebind. Профильные регрессии AI/OBB lifecycle/equipment/death/scheduler, чистое применение патча, verify.py и Luau leading-parenthesis guard. Это не Roblox engine test. Native shell motion, rig reattach, streamed client consumers, бой на границе, два клиента и нагрузка NOT_RUN; T08/A07 остаются открытыми.
