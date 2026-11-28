# M614 · Native Combat Spatial Index

База M613, диагностический архив 2026-11-27 23:08:51. KBN-0036 / KBN-0038 IN_PROGRESS. M613 отложил профилирование до рефакторинга.

EntityHitboxService владеет одним экземпляром NativePartSpatialIndex; отдельные экземпляры возможны для других потребителей. Register/Remove привязаны к Attach/Detach и Destroying модели/корня. RootCollider уже создаётся с CanQuery=true в CharacterRigService, MonsterRigBuilder и NpcRigFactory. Перемещение/телепорт обрабатывает сам Workspace; дополнительных Parts, сеток, Heartbeat и RemoteEvents нет. Фильтр и максимальный broadRadius пересчитываются только после изменения состава; снятые записи освобождаются, старый фильтр сбрасывается. GetPartBoundsInBox с Include, MaxParts=0, RespectCanCollide=false. Предусловие: root находится в Workspace, queryable и доступен Default collision group. При нарушении контракта регистрация не маскируется.

Box — исходный OBB, Arc — куб радиуса reach, Ray — ориентированный вдоль луча объём полной исходной длины (включая вертикальный луч); каждый объём расширен максимальным broadRadius + малым запасом. Это консервативная оболочка прежних sphere broad-phase проверок, а не новый хитбокс. Дополнительные кандидаты отбрасывает исходный narrow phase. Точные bone-local OBB, кэш кадров, multi-hit, ближайший луч, headshot, фильтры Damageable/exclusion, препятствия, DamageService и сетевые контракты не меняются. Одинаковая дистанция двух целей не имела гарантированного порядка и прежде.

Существующий broadRadius и его ограничения не меняются. Большой актор расширяет общий запрос, а частая смена состава требует пересборки фильтра; реальный выигрыш не измерен. Индекс записей без физических частей (например LOD) и AI/сокеты ещё не реализованы. Rojo включает src/shared/world в Runtime штатно.

Проверка: Lua mock выполняет production module, 300 сравнений с эталоном прежних sphere/box/ray условий (дедуп, вертикаль, большая цель, телепорт, detach/destroy, независимые экземпляры). Это не эмуляция физики Roblox. В Studio и published DEV требуется проверить многоцелевые melee, bow/headshot вне melee reach в пределах действующего лимита, заслоны, движущихся/телепортированных акторов, большие цели, respawn/death и Runtime script freshness. Сравнение CPU/количества кандидатов при 50/100/200 сущностях остаётся открытым. Откат — reverse patch до публикации нового Runtime; миграций данных нет.

M628 note: RootCollider creation for Monster/NPC moved to the shared `actor/MnpcVisualRig` attachment; existing M614 query/index contract unchanged. `CharacterRigService` unchanged.
